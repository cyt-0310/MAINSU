"""Display existing analysis; no extra model calls or invented overall grade."""
from interview_gap_detection.config import PASS_THRESHOLD

NAMES = {'trait': '個人特質', 'depth': '深度邏輯', 'exp': '經驗內容'}


def build_summary(snapshot):
    log = snapshot.get('log', [])
    final = next((e for e in reversed(log) if e.get('kind') == 'interview_end'), {})
    rows = []
    for index, topic in enumerate(snapshot.get('topics', [])):
        events = [e for e in log if e.get('topic_index') == index]
        analyses = [e for e in events if e.get('kind') == 'analysis']
        answers = [e for e in events if e.get('kind') == 'answer']
        questions = [e for e in events if e.get('kind') == 'question']
        last = analyses[-1] if analyses else {}
        gap = last.get('gap', {})
        scores = gap.get('scores')
        assessment = last.get('assessment', {})
        issues = assessment.get('consistency_issues', [])
        end = next((e for e in reversed(events) if e.get('kind') == 'topic_end'), {})
        reason = end.get('reason')
        if not reason and questions and snapshot.get('finished'):
            reason = final.get('reason')
        rows.append({
            'topic_index': index, 'event_id': topic.get('event_id'),
            'title': topic.get('event', topic.get('type', str(index + 1))),
            'status': 'assessed' if analyses else ('not_assessed' if questions else 'not_started'),
            'scores': scores,
            'is_all_passed': all(scores.get(k, -1) >= PASS_THRESHOLD for k in NAMES) if scores else None,
            'details': gap.get('details'), 'reasoning': assessment.get('reasoning'),
            'relevance_score': last.get('relevance', {}).get('relevance_score'),
            'relevance_status': last.get('relevance_status'),
            'gaps': gap.get('gaps', []),
            'followup_count': sum(q.get('question_kind') == 'followup' for q in questions),
            'restate_count': sum(q.get('question_kind') == 'restate' for q in questions),
            'answer_seconds': round(sum(a.get('answer_elapsed', 0) for a in answers), 3),
            'timed_out_answers': sum(bool(a.get('timed_out')) for a in answers),
            'consistency_issues': issues,
            'source_verified_issue_count': sum(issue.get('source_verified') is True for issue in issues),
            'termination_reason': reason,
        })
    return {'schema_version': 1, 'pass_threshold': PASS_THRESHOLD,
            'finished': bool(snapshot.get('finished')), 'total_questions': snapshot.get('total_questions', 0),
            'elapsed_seconds': snapshot.get('elapsed', 0), 'termination_reason': final.get('reason'),
            'assessed_topic_count': sum(r['status'] == 'assessed' for r in rows), 'topics': rows,
            'note': '每主題採最後一次累積評估；未評估不算零分。一致性差異待核對，不代表已確認不實。'}


def render_summary(snapshot):
    summary = build_summary(snapshot)
    lines = ['面試結果摘要',
             f"狀態：{'已結束' if summary['finished'] else '尚未結束／已中斷'}；提問 {summary['total_questions']} 題；總時間 {summary['elapsed_seconds']:.1f} 秒",
             f"完整度門檻：三項各 >= {summary['pass_threshold']:g}%（沒有換算整體評分）"]
    for row in summary['topics']:
        title = str(row['title']).replace('\n', ' ')
        lines.append(f"\n主題 {row['topic_index'] + 1}：{title}")
        if row['scores']:
            lines.append('；'.join(f"{label} {row['scores'][key]:g}%" for key, label in NAMES.items()))
            lines.append('完整度：' + ('三項皆達標' if row['is_all_passed'] else '尚未全部達標'))
            lines.append('優先缺口：' + (' → '.join(NAMES[k] for k in row['gaps'] if k in NAMES) or '無'))
        else:
            lines.append('完整度：未評估' + ('（尚未進入本主題）' if row['status'] == 'not_started' else '（沒有成功評估結果）'))
        score = row['relevance_score']
        lines.append('相關度：' + (f"{score:.3f}（{row['relevance_status'] or '未分類'}）" if score is not None else '未評估'))
        lines.append(f"追問 {row['followup_count']} 次；重述 {row['restate_count']} 次；作答 {row['answer_seconds']:g} 秒；超時 {row['timed_out_answers']} 次")
        lines.append(f"待核對一致性差異：{len(row['consistency_issues'])} 項；其中 {row['source_verified_issue_count']} 項可核對雙方引文來源")
        for issue in row['consistency_issues']:
            pages = sorted({c['page'] for c in issue.get('portfolio_sources', []) if c.get('page') is not None})
            turns = sorted({c['turn'] for c in issue.get('answer_sources', []) if c.get('turn') is not None})
            lines.append(f"  - {issue.get('issue_type', '差異')}：{issue.get('note', '')}")
            lines.append(f"    備審：{issue.get('portfolio_evidence', '未提供')}（PDF頁 {pages or '未驗證'}）")
            lines.append(f"    回答：{issue.get('answer_evidence', '未提供')}（輪次 {turns or '未驗證'}）")
        if row['reasoning']:
            lines.append('評估說明：' + row['reasoning'])
        lines.append('結束原因：' + (row['termination_reason'] or '尚未結束／未記錄'))
    lines.extend(['', summary['note']])
    return '\n'.join(lines)
