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


def format_analysis(entries):
    """Lines showing relevance and cumulative completeness for one submitted answer."""
    from interview_gap_detection.config import PASS_THRESHOLD
    lines = []
    for entry in entries:
        if entry['kind'] == 'analysis':
            score = entry['relevance']['relevance_score']
            scores = entry['gap']['scores']
            lines.append(f"【本題分析】相關度 {score:.2f}（{entry['relevance_status']}）")
            rel = entry['relevance']
            if 'vector_score' in rel:
                parts = [f"雙塔向量 {rel['vector_score']:.2f}", f"交叉注意力 {rel['cross_score']:.2f}",
                         f"模型混合 {rel.get('model_score', score):.2f}"]
                if rel.get('copied_question'):
                    parts.append('疑似照抄題目')
                if rel.get('llm_label'):
                    names = {'relevant': '切題', 'partial': '部分', 'off_topic': '離題'}
                    parts.append(f"LLM 判斷 {names[rel['llm_label']]}：{rel.get('llm_reason', '')}")
                lines.append('  └ ' + '、'.join(parts))
            items = '、'.join(f"{name} {scores[key]:.0f}% {'通過' if scores[key] >= PASS_THRESHOLD else '未通過'}"
                             for key, name in (('trait', '個人特質'), ('depth', '深度邏輯'), ('exp', '經驗內容')))
            lines.append(f"本主題累計完整度：{items}")
            na = entry['gap'].get('not_applicable')
            if na:
                names = {'why_score': '動機', 'how_score': '過程', 'what_score': '結果', 'role_score': '角色',
                         'action_score': '行動', 'skill_score': '能力', 'attitude_score': '態度',
                         'knowledge_score': '知識', 'reflection_score': '反思', 'challenge_score': '挑戰'}
                lines.append(f"  └ 不適用、不計分的細項：{'、'.join(names.get(k, k) for k in na)}")
            overall = '通過' if all(v >= PASS_THRESHOLD for v in scores.values()) else '未通過'
            lines.append(f"完整度整體：{overall}（三項皆需 ≥ {PASS_THRESHOLD:g}%）")
            if entry['gap'].get('hidden_items'):
                from interview_gap_detection.gap_detection import ITEM_INFO, gap_field
                names = '、'.join(f"{gap_field(h['field'])['name']}›{ITEM_INFO[h['item']][0]}"
                                  for h in entry['gap']['hidden_items'])
                lines.append(f"→ 若追問，一題暗藏的缺口：{names}")
        elif entry['kind'] == 'no_answer':
            lines.append('【本題分析】未作答，相關度視為 0.00')
        elif entry['kind'] == 'topic_end' and entry.get('reason'):
            if not any(e['kind'] in ('analysis', 'no_answer') for e in entries):
                lines.append('【本題分析】未送出分析')
            lines.append(f"→ 結束本主題：{entry['reason']}")
    return lines


def format_relevance_summary(summary):
    kind_names = {'main': '主問題', 'followup': '追問', 'restate': '重述'}
    lines = ['\n【最終相關度】']
    for topic in summary['topics']:
        name = '自我介紹' if topic['topic_index'] == 0 else f"主題 {topic['topic_index']}（{topic['type']}）"
        lines.append(f"{name}：平均 {topic['relevance_score']:.2f}")
        for i, q in enumerate(topic.get('questions', []), 1):
            lines.append(f"  {i}. {kind_names.get(q['question_kind'], '題目')}：{q['relevance_score']:.2f}")
    if summary['overall'] is None:
        lines.append('整場相關度：無（沒有任何已分析的回答）')
    else:
        lines.append(f"整場相關度：{summary['overall']:.2f}（每題個別計算 → 各主題平均 → 主題平均，未作答以 0 計）")
    portfolio_topics = [t for t in summary['topics'] if t['topic_index'] > 0]
    if portfolio_topics:
        from interview_gap_detection.config import PASS_THRESHOLD
        lines.append('\n【最終完整度】')
        for topic in portfolio_topics:
            name = f"主題 {topic['topic_index']}（{topic['type']}）"
            scores = topic.get('completeness')
            if not scores:
                lines.append(f"{name}：無（沒有已分析的回答）")
                continue
            items = '、'.join(f"{label} {scores[key]:.0f}% {'通過' if scores[key] >= PASS_THRESHOLD else '未通過'}"
                             for key, label in (('trait', '個人特質'), ('depth', '深度邏輯'), ('exp', '經驗內容')))
            overall = '通過' if all(v >= PASS_THRESHOLD for v in scores.values()) else '未通過'
            lines.append(f"{name}：{items}（整體{overall}）")
    return lines


def save_session(session, output):
    path = Path(output)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(session.snapshot(), ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def load_session(prepared_dir, output):
    """Build a not-yet-started live session from a prepare output folder (shared by CLI and web UI)."""
    from ai_services import LiveServices
    from interview_gap_detection.llm_client import get_model, get_client
    get_model()
    get_client()
    folder = Path(prepared_dir)
    if Path(output).exists():
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
    return InterviewSession(topics, services)


def main():
    parser = argparse.ArgumentParser(description='流程 2-12，文字回答，不含常見問題或分析報告')
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('check', help='Send one short structured request without PDF or model downloads')
    check.add_argument('--timeout', type=float, help='Gemini request timeout in seconds (maximum 300)')
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
        session = load_session(args.prepared_dir, args.output)
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
                log_start = len(session.log)
                event = session.submit(answer, timed_out=expired)
                save_session(session, args.output)
                for line in format_analysis(session.log[log_start:]):
                    print(line, flush=True)
            print(event['reason'])
            for line in format_relevance_summary(session.relevance_summary()):
                print(line)
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
