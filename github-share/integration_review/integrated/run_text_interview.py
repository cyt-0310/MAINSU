"""CLI for PDF processing, step-5 preparation, and text-only interview (2-12)."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from bridge import load_portfolio_events
from evidence import EvidenceIndex, SentenceEmbedder
from interview_session import InterviewSession


def timed_input(seconds):
    """Console deadline without orphaned background input readers."""
    deadline = time.monotonic() + seconds
    if not sys.stdin.isatty():
        raise RuntimeError('Live interview requires an interactive terminal')
    if os.name == 'nt':
        import msvcrt
        return windows_answer(deadline, msvcrt)
    import select
    while time.monotonic() < deadline:
        ready, _, _ = select.select([sys.stdin], [], [], max(0, deadline-time.monotonic()))
        if not ready:
            break
        text = sys.stdin.readline()
        if not text:
            raise EOFError('Input closed')
        if text.strip():
            return text.rstrip('\n'), False
        print('尚未輸入回答。輸入文字後，按 Enter 即可提前送出。', flush=True)
    return '', True


def windows_answer(deadline, console, clock=time.monotonic, sleep=time.sleep):
    """Enter immediately completes a nonempty answer without waiting for deadline."""
    chars = []
    while clock() < deadline:
        if not console.kbhit():
            sleep(.03)
            continue
        char = console.getwch()
        if char in ('\x00', '\xe0'):
            console.getwch()
        elif char == '\x03':
            raise KeyboardInterrupt
        elif char in ('\r', '\n'):
            print()
            if ''.join(chars).strip():
                return ''.join(chars), False
            print('尚未輸入回答。輸入文字後，按 Enter 即可提前送出。', flush=True)
        elif char == '\b':
            if chars:
                chars.pop()
                print('\b \b', end='', flush=True)
        else:
            chars.append(char)
            print(char, end='', flush=True)
    print('\n作答時間已到。')
    return ''.join(chars), True


def save_session(session, output):
    path = Path(output)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(session.snapshot(), ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def main():
    parser = argparse.ArgumentParser(description='流程 2-12，文字回答，不含常見問題或分析報告')
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('check', help='Send one short structured request without PDF or model downloads')
    check.add_argument('--timeout', type=float, help='Gemini request timeout in seconds (maximum 300)')
    summary = commands.add_parser('summary', help='Display saved interview analysis without API calls')
    summary.add_argument('session_json')
    summary.add_argument('--output', help='Optional new text/Markdown output file')
    plan = commands.add_parser('plan', help='Student Profile to Question Plan')
    plan.add_argument('profile_json')
    plan.add_argument('--index', required=True)
    plan.add_argument('--output', required=True)
    pdf = commands.add_parser('parse')
    pdf.add_argument('pdf')
    pdf.add_argument('--output', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('events_json', nargs='+')
    prep.add_argument('--output', required=True)
    prep.add_argument('--embedding-model', default='shibing624/text2vec-base-chinese')
    interview = commands.add_parser('interview')
    interview.add_argument('prepared_dir')
    interview.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.command == 'check':
        from pydantic import BaseModel
        from interview_gap_detection.llm_client import call_llm, get_provider, get_model
        if args.timeout is not None:
            os.environ['GEMINI_TIMEOUT_SECONDS'] = str(args.timeout)
        class ConnectionCheck(BaseModel):
            message: str
        print(f'測試服務：{get_provider()}，模型：{get_model()}')
        if get_provider() == 'gemini':
            from interview_gap_detection.llm_client import get_gemini_transport
            print(f'Gemini 連線方式：{get_gemini_transport()}')
        result = call_llm('這是連線測試，請在 message 回傳「連線成功」。', ConnectionCheck)
        print('API 結構化回覆已驗證：', result.message)
    elif args.command == 'summary':
        from results_summary import render_summary
        snapshot = json.loads(Path(args.session_json).read_text(encoding='utf-8-sig'))
        text = render_summary(snapshot)
        print(text)
        if args.output:
            with Path(args.output).open('x', encoding='utf-8') as stream:
                stream.write(text + '\n')
    elif args.command == 'plan':
        from ai_services import plan_from_profile
        from interview_gap_detection.llm_client import get_model, get_client
        get_model()
        get_client()
        profile = json.loads(Path(args.profile_json).read_text(encoding='utf-8-sig'))
        index_data = json.loads(Path(args.index).read_text(encoding='utf-8'))
        index = EvidenceIndex.load(args.index, SentenceEmbedder(index_data['model']))
        plan_from_profile(profile, index, args.output, create_dir=True)
        print('Student Profile → Question Plan 已完成。')
    elif args.command == 'parse':
        source = Path(__file__).resolve().parents[2] / 'docling_pdf' / 'parse_pdf.py'
        destination = Path(args.output).resolve()
        if destination.exists():
            raise FileExistsError('Choose a new parser output folder')
        subprocess.run([sys.executable, str(source), str(Path(args.pdf).resolve()), '--output', str(destination)], check=True)
    elif args.command == 'prepare':
        from ai_services import prepare
        from interview_gap_detection.llm_client import get_model, get_client
        get_model()
        get_client()
        paths = [Path(p).resolve() for p in args.events_json]
        if len(set(paths)) != len(paths):
            raise ValueError('The same PDF parsing output was supplied twice')
        prepare([load_portfolio_events(path) for path in paths], SentenceEmbedder(args.embedding_model), args.output)
        print('事件 JSON、RAG 索引、候選技能樹及題庫已建立；請先核對再開始面試。')
    else:
        from ai_services import LiveServices
        from interview_gap_detection.llm_client import get_model, get_client
        get_model()
        get_client()
        folder = Path(args.prepared_dir)
        if Path(args.output).exists():
            raise FileExistsError('Choose a new session output filename')
        index_data = json.loads((folder/'evidence.index.json').read_text(encoding='utf-8'))
        index = EvidenceIndex.load(folder/'evidence.index.json', SentenceEmbedder(index_data['model']))
        # Evidence includes original PDF name; context text is supplied by RAG on every turn.
        names = list(dict.fromkeys(Path(c['source_file']).name.removesuffix('.events.json') + '.pdf' for c in index.chunks))
        portfolio = {'pdf_name': '、'.join(names)}
        topics = json.loads((folder/'topics.json').read_text(encoding='utf-8'))
        services = LiveServices(index, portfolio)
        # Load models before starting the interview timer.
        from interview_gap_detection.relevance import load_models
        index.embedder.encode(['模型預熱'])
        load_models()
        session = InterviewSession(topics, services)
        try:
            event = session.start()
            save_session(session, args.output)
            while event['kind'] != 'finished':
                label = '重述（不增加題數）' if event['question_kind'] == 'restate' else f"第 {session.total_questions} 題"
                print(f"\n{label}：{event['text']}")
                print(f'請輸入文字回答，剩餘 {session.remaining_answer_seconds():.0f} 秒：')
                print('輸入完成後按 Enter，立即結束本題回答並送出；不必等時間到。', flush=True)
                answer, expired = timed_input(session.remaining_answer_seconds())
                print('已到作答期限，正在處理回答……' if expired else '回答已送出，正在分析……', flush=True)
                event = session.submit(answer, timed_out=expired)
                save_session(session, args.output)
            print(event['reason'])
            from results_summary import render_summary
            print('\n' + render_summary(session.snapshot()))
        except BaseException as error:
            session._log('interrupted', reason=type(error).__name__)
            save_session(session, args.output)
            raise


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as error:
        print(f'測試／流程中止：{error}', file=sys.stderr)
        sys.exit(1)
