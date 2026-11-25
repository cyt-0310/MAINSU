"""Web adapter for the existing interview state machine; separate durable session files."""
import math
from datetime import datetime, timezone
from interview_gap_detection.api_retry import TemporaryServiceError, retry_progress
from uuid import uuid4
from threading import Lock
from starlette.routing import Route
from starlette.concurrency import run_in_threadpool
from web_portfolios import DATA, path_for, school_id, clean_target, read_json, write_json, response, portfolio_record
from interview_gap_detection.config import QUESTION_BANK_CONFIG
from interview_session import InterviewSession
from evidence import EvidenceIndex, SentenceEmbedder
from ai_services import LiveServices
from report_review import question_details, evaluate
from question_rotation import portfolio_identity, recent_sessions, rotate_questions

LOCK = Lock()
ROOT = DATA / 'voice_sessions'
PROGRESS = {}

def file_for(key):
    from uuid import UUID
    return ROOT / (str(UUID(key)) + '.json')

class WebSession(InterviewSession):
    # The web clock advances only during the recorded answer; retry waits are already excluded.
    def exclude_time(self, seconds):
        pass

def services(folder):
    if folder is None:
        class EmptyEvidence:
            def search(self, *args):
                return []
        return LiveServices(EmptyEvidence(), {'pdf_name': '無備審資料'})
    meta = read_json(folder / 'evidence.index.json')
    index = EvidenceIndex.load(folder / 'evidence.index.json', SentenceEmbedder(meta['model']))
    return LiveServices(index, {'pdf_name': '、'.join(dict.fromkeys(c['source_file'] for c in index.chunks))})

def view(record):
    runtime = record['snapshot']['runtime']
    pending = runtime['pending']
    remaining = 0 if not pending else max(0, min((90 if runtime['index'] == 0 else 120) - pending.get('elapsed', 0),
        240 - runtime['active']['elapsed'], 1200 - runtime['elapsed']))
    topics = record['snapshot']['topics']
    index = runtime['index']
    topic = topics[index] if 0 <= index < len(topics) else {}
    rows = question_details(record)
    answers = [{**answer, **{k: rows[i][k] for k in ('topicIndex','kind','gaps','analysisScores','targetGap','followupReason') if k in rows[i]}} if i < len(rows) else answer for i, answer in enumerate(record['answers'])]
    completed_at = record.get('completedAt')
    estimated = False
    if runtime['finished'] and not completed_at:
        path = file_for(record['id'])
        if path.is_file():
            completed_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
            estimated = True
    return {'completedAt': completed_at, 'dateEstimated': estimated, 'id': record['id'], 'target': record['target'], 'mode': record.get('mode'), 'noPortfolio': record.get('noPortfolio', False), 'pending': pending,
            'remaining': remaining, 'finished': runtime['finished'],
            'topicIndex': index, 'topicCount': len(topics), 'topicType': topic.get('type'),
            'topicTitle': topic.get('title') or (topic.get('event') if index > 0 else None), 'questionNumber': runtime['total_questions'],
            'awaitingRetry': runtime['pending_answer'] is not None,
            'answers': answers, 'error': record.get('error'), 'summary': record['snapshot']['summary'], 'reportReview': record.get('report_review')}


def active_sessions():
    records = []
    if ROOT.exists():
        for path in ROOT.glob('*.json'):
            try:
                record = read_json(path)
                info = view(record)
                if not info['finished']:
                    records.append((path.stat().st_mtime, info))
            except (OSError, ValueError, KeyError, TypeError):
                continue
    return [info for _, info in sorted(records, key=lambda row: row[0], reverse=True)]


def resume_or_start(payload):
    target = {'school': clean_target(payload.get('school')), 'department': clean_target(payload.get('department'))}
    with LOCK:
        for info in active_sessions():
            if info['target'] == target and info.get('mode') in (None, payload.get('mode', 'voice')) and info.get('noPortfolio') == bool(payload.get('noPortfolio')):
                return info
        return start(payload)

def start(payload):
    target = {'school': clean_target(payload.get('school')), 'department': clean_target(payload.get('department'))}
    directory = path_for(school_id(**target))
    folder = directory / 'prepared'
    no_portfolio = not (directory / 'submission.json').is_file()
    mode = payload.get('mode', 'voice')
    if mode not in ('voice', 'text'):
        raise ValueError('面試模式不正確。')
    if no_portfolio:
        if not payload.get('noPortfolio'):
            raise ValueError('此校系尚未上傳備審資料，請先確認是否繼續。')
        department = target['department']
        intro = dict(QUESTION_BANK_CONFIG['intro'])
        intro.update(question=intro['question'].format(department=department), answer_limit=90, max_followups=1, event_id=None)
        topics = [intro] + [
            {'type': '常見問題', 'event': title, 'event_id': None, 'source': '校系常見題庫',
             'portfolio_role': '未提及', 'question': question, 'check_aspects': ['具體說明', '理由', '反思'],
             'max_followups': 2, 'answer_limit': 120}
            for item in QUESTION_BANK_CONFIG['common_questions']
            for title, question in [(item['title'], item['question'].format(department=department))]
        ]
    else:
        if portfolio_record(directory)['status'] != 'ready' or not (folder / 'topics.json').is_file():
            raise ValueError('此校系尚未完成備審分析，請先完成備審分析。')
        topics = read_json(folder / 'topics.json')
    identity = None
    if not no_portfolio:
        identity = portfolio_identity(directory)
        recent = recent_sessions(ROOT, target, identity, lambda t: path_for(school_id(**t)))
        topics = rotate_questions(topics, recent, target['department'])
    session = InterviewSession(topics, None)
    session.start()
    record = {'id': str(uuid4()), 'target': target, 'mode': mode, 'noPortfolio': no_portfolio, 'portfolioIdentity': identity, 'createdAt': datetime.now(timezone.utc).isoformat(), 'answers': [], 'snapshot': session.snapshot()}
    ROOT.mkdir(parents=True, exist_ok=True)
    write_json(file_for(record['id']), record)
    return view(record)

def turn(key, payload):
    with LOCK:
        path = file_for(key)
        record = read_json(path)
        snapshot = record['snapshot']
        runtime = snapshot['runtime']
        if payload.get('retryOnly') and runtime['pending_answer'] is None:
            return view(record)
        if payload.get('requestId') and any(a.get('requestId') == payload['requestId'] for a in record['answers']) and runtime['pending_answer'] is None:
            return view(record)
        if runtime['finished']:
            return view(record)
        folder = path_for(school_id(**record['target'])) / 'prepared'
        # Restore clocks from the persisted question; count actual answer time, not HTTP idle time.
        clock = [0.0]
        session = WebSession.restore(snapshot, None, clock=lambda: clock[0])
        if session.pending_answer is None:
            if record.get('mode') and payload.get('mode') != record['mode']:
                raise ValueError('本場作答方式已確定，無法在面試中切換。')
            text = payload.get('text')
            duration = payload.get('duration')
            if not isinstance(text, str) or len(text) > 20000 or not isinstance(duration, (float, int)) or not math.isfinite(duration) or duration < 0:
                raise ValueError('回答格式不正確')
            duration = min(duration, session.remaining_answer_seconds())
            clock[0] += duration
            session.queue_answer(text, timed_out=bool(payload.get('timedOut')) or not text.strip())
            record['answers'].append({'question': session.pending['text'], 'text': text,
                'duration': duration, 'timedOut': bool(payload.get('timedOut')),
                'metrics': payload.get('metrics'), 'mode': payload.get('mode'), 'requestId': payload.get('requestId')})
            record['snapshot'] = session.snapshot()
            write_json(path, record)
        try:
            PROGRESS[key] = {'state': 'preparing'}
            with retry_progress(lambda event: PROGRESS.__setitem__(key, event)):
                session.services = services(None if record.get('noPortfolio') else folder)
                session.process_answer()
        except Exception as exc:
            record['snapshot'] = session.snapshot()
            code = getattr(exc, 'status_code', None)
            if isinstance(exc, TemporaryServiceError):
                message = str(exc)
            else:
                detail = f'HTTP {code}' if isinstance(code, int) else type(exc).__name__
                message = f'分析失敗（{detail}）。回答已保存，請重新連線或重試。'
            record['error'] = message
            print(f'Interview analysis failed: {type(exc).__name__}, HTTP {code}', flush=True)
            write_json(path, record)
            PROGRESS[key] = {'state': 'paused'}
            return view(record)
        record.pop('error', None)
        if session.snapshot()['runtime']['finished'] and not record.get('completedAt'):
            record['completedAt'] = datetime.now(timezone.utc).isoformat()
        record['snapshot'] = session.snapshot()
        write_json(path, record)
        PROGRESS[key] = {'state': 'idle'}
        return view(record)

async def endpoint(request):
    try:
        if request.method == 'GET':
            return response(view(read_json(file_for(request.path_params['session_id']))))
        payload = await request.json()
        if 'session_id' in request.path_params:
            return response(await run_in_threadpool(turn, request.path_params['session_id'], payload))
        return response(await run_in_threadpool(resume_or_start, payload))
    except (ValueError, FileNotFoundError) as exc:
        return response({'error': str(exc)}, 400)
    except Exception:
        return response({'error': '面試服務暫時無法使用，請重試。'}, 503)

async def active_endpoint(request):
    sessions = await run_in_threadpool(active_sessions)
    return response([{k: info[k] for k in ('id','target','topicIndex','topicCount','topicType','questionNumber','awaitingRetry')} for info in sessions])


async def progress_endpoint(request):
    key = request.path_params['session_id']
    return response(PROGRESS.get(key, {'state': 'idle'}))


REPORT_LOCK = Lock()


def review_report(key):
    with REPORT_LOCK:
        path = file_for(key)
        record = read_json(path)
        if not record['snapshot']['finished']:
            raise ValueError('Interview not finished')
        prior = record.get('report_review')
        if not prior or prior.get('version') != 2 or not prior.get('complete'):
            def checkpoint(partial):
                record['report_review'] = partial
                write_json(path, record)
            record['report_review'] = evaluate(record, prior if prior and prior.get('version')==2 else None, checkpoint)
            write_json(path, record)
        return view(record)


async def review_endpoint(request):
    try:
        return response(await run_in_threadpool(review_report, request.path_params['session_id']))
    except (ValueError, FileNotFoundError):
        return response({'error': '尚無可用的完整面試評分資料。'}, 400)
    except Exception as exc:
        code = getattr(exc, 'status_code', None)
        detail = f'HTTP {code}' if isinstance(code, int) else type(exc).__name__
        print(f'Report evaluation failed: {detail}', flush=True)
        return response({'error': f'AI 評分尚未完成（{detail}），已保留原始報告及成功評分的題目。'}, 503)


routes = [Route('/api/voice-interviews', endpoint, methods=['POST']),
          Route('/api/voice-interviews/active', active_endpoint, methods=['GET']),
          Route('/api/voice-interviews/{session_id}/review', review_endpoint, methods=['POST']),
          Route('/api/voice-interviews/{session_id}/progress', progress_endpoint, methods=['GET']),
          Route('/api/voice-interviews/{session_id}', endpoint, methods=['GET', 'POST'])]
