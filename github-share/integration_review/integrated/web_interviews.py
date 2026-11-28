"""Web adapter for the existing interview state machine; separate durable session files."""
import math
import re
import web_postgres as pg
from datetime import datetime, timezone
from interview_gap_detection.answer_content import no_content_reason
from interview_gap_detection.api_retry import TemporaryServiceError, retry_progress
from uuid import UUID, uuid4
from threading import Lock
from starlette.routing import Route
from starlette.concurrency import run_in_threadpool
from web_accounts import workspace
from web_portfolios import path_for, school_id, clean_target, read_json, write_json, response, portfolio_record
from interview_gap_detection.config import QUESTION_BANK_CONFIG
from interview_session import InterviewSession
from evidence import EvidenceIndex, SentenceEmbedder
from ai_services import LiveServices
from report_review import question_details, evaluate
from question_rotation import portfolio_identity, recent_sessions, rotate_questions

LOCK = Lock()
PROGRESS = {}

def session_root():
    return workspace.get() / 'voice_sessions'

def file_for(key):
    return session_root() / (str(UUID(key)) + '.json')


def load_session(key):
    user = pg.owner.get()
    if user is not None:
        return pg.load_interview(user, key)['record']
    return read_json(file_for(key))


def save_session(record):
    user = pg.owner.get()
    if user is not None:
        with pg.connect() as conn:
            pg.save_interview(conn, user, record)
        return
    session_root().mkdir(parents=True, exist_ok=True)
    write_json(file_for(record['id']), record)


def session_records(finished=None):
    user = pg.owner.get()
    if user is not None:
        for row in pg.interviews(user, finished):
            yield row['record'], row['updated_at'].timestamp()
        return
    for path in session_root().glob('*.json'):
        try:
            record = read_json(path)
            if finished is None or bool(record['snapshot']['runtime']['finished']) == finished:
                yield record, path.stat().st_mtime
        except (OSError, ValueError, KeyError, TypeError):
            continue

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
    estimated = bool(record.get('estimatedCompletedAt'))
    completed_at = completed_at or record.get('estimatedCompletedAt')
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


def saved_sessions(finished):
    records = []
    for record, modified in session_records(finished):
        try:
            if 'snapshot' in record:
                records.append((modified, view(record)))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return [info for _, info in sorted(records, key=lambda row: row[0], reverse=True)]


def resume_or_start(payload):
    target = {'school': clean_target(payload.get('school')), 'department': clean_target(payload.get('department'))}
    with LOCK:
        for info in saved_sessions(False):
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
        recent = recent_sessions(session_records(), target, identity, lambda t: path_for(school_id(**t)))
        topics = rotate_questions(topics, recent, target['department'])
    session = InterviewSession(topics, None)
    session.start()
    record = {'id': str(uuid4()), 'target': target, 'mode': mode, 'noPortfolio': no_portfolio, 'portfolioIdentity': identity, 'createdAt': datetime.now(timezone.utc).isoformat(), 'answers': [], 'snapshot': session.snapshot()}
    save_session(record)
    return view(record)

def turn(key, payload):
    with LOCK:
        path = file_for(key)
        record = load_session(key)
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
            save_session(record)
        try:
            PROGRESS[path] = {'state': 'preparing'}
            with retry_progress(lambda event: PROGRESS.__setitem__(path, event)):
                # Silence and placeholders can be handled without loading the model or evidence index.
                if not no_content_reason(session.pending_answer['answer']):
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
            save_session(record)
            PROGRESS[path] = {'state': 'paused'}
            return view(record)
        record.pop('error', None)
        if session.snapshot()['runtime']['finished'] and not record.get('completedAt'):
            record['completedAt'] = datetime.now(timezone.utc).isoformat()
        record['snapshot'] = session.snapshot()
        save_session(record)
        PROGRESS.pop(path, None)
        return view(record)

async def endpoint(request):
    try:
        if request.method == 'GET':
            record = await run_in_threadpool(load_session, request.path_params['session_id'])
            return response(view(record))
        payload = await request.json()
        if 'session_id' in request.path_params:
            return response(await run_in_threadpool(turn, request.path_params['session_id'], payload))
        return response(await run_in_threadpool(resume_or_start, payload))
    except (ValueError, FileNotFoundError) as exc:
        return response({'error': str(exc)}, 400)
    except Exception:
        return response({'error': '面試服務暫時無法使用，請重試。'}, 503)

async def active_endpoint(request):
    sessions = await run_in_threadpool(saved_sessions, False)
    return response([{k: info[k] for k in ('id','target','topicIndex','topicCount','topicType','questionNumber','awaitingRetry')} for info in sessions])


async def progress_endpoint(request):
    try:
        path = file_for(request.path_params['session_id'])
        await run_in_threadpool(load_session, request.path_params['session_id'])
    except (ValueError, FileNotFoundError):
        return response({'error': '找不到面試紀錄。'}, 404)
    return response(PROGRESS.get(path, {'state': 'idle'}))


async def history_endpoint(request):
    user = pg.owner.get()
    if user is not None:
        rows = await run_in_threadpool(pg.interviews, user, True)
        return response([view(row['record']) if 'snapshot' in row['record'] else row['record'] for row in rows])
    reports = await run_in_threadpool(saved_sessions, True)
    for path in (request.state.workspace / 'free_reports').glob('*.json'):
        try:
            reports.append(read_json(path))
        except (OSError, ValueError):
            continue
    return response(reports)


async def free_report_endpoint(request):
    try:
        raw = await request.body()
        if len(raw) > 400_000:
            return response({'error': '面試紀錄超過儲存上限。'}, 413)
        report = await request.json()
        if not isinstance(report, dict):
            raise ValueError
        key = report.get('id', '')
        answers = report.get('answers')
        if (not isinstance(key, str) or not re.fullmatch(r'free-[\da-f-]{36}', key)
                or report.get('finished') is not True or not isinstance(answers, list) or len(answers) > 15
                or not all(isinstance(a, dict) and isinstance(a.get('question'), str)
                           and isinstance(a.get('text'), str) and isinstance(a.get('duration'), (int, float))
                           and math.isfinite(a['duration']) for a in answers)):
            raise ValueError
        if pg.owner.get() is not None:
            await run_in_threadpool(save_session, report)
        else:
            directory = request.state.workspace / 'free_reports'
            directory.mkdir(parents=True, exist_ok=True)
            write_json(directory / f'{key}.json', report)
        return response({'ok': True})
    except (ValueError, TypeError):
        return response({'error': '免費面試紀錄格式不正確。'}, 400)


REPORT_LOCK = Lock()


def review_report(key):
    with REPORT_LOCK:
        record = load_session(key)
        if not record['snapshot']['finished']:
            raise ValueError('Interview not finished')
        prior = record.get('report_review')
        if not prior or prior.get('version') != 2 or not prior.get('complete'):
            def checkpoint(partial):
                record['report_review'] = partial
                save_session(record)
            record['report_review'] = evaluate(record, prior if prior and prior.get('version')==2 else None, checkpoint)
            save_session(record)
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
          Route('/api/voice-interviews/history', history_endpoint, methods=['GET']),
          Route('/api/voice-interviews/free-report', free_report_endpoint, methods=['POST']),
          Route('/api/voice-interviews/active', active_endpoint, methods=['GET']),
          Route('/api/voice-interviews/{session_id}/review', review_endpoint, methods=['POST']),
          Route('/api/voice-interviews/{session_id}/progress', progress_endpoint, methods=['GET']),
          Route('/api/voice-interviews/{session_id}', endpoint, methods=['GET', 'POST'])]
