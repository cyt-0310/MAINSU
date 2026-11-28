"""Store interview questions and answers in the existing PostgreSQL tables."""
from hashlib import md5
from uuid import UUID
from datetime import datetime
from statistics import mean

from interview_gap_detection.answer_content import no_content_reason


def detail_id(session_id, kind, number):
    # Matches the identifiers used to backfill previously completed interviews.
    return UUID(md5(f'{session_id}:{kind}:{number}'.encode()).hexdigest())


def milliseconds(seconds):
    return max(0, round((seconds or 0) * 1000))


def answer_analyses(events):
    analyses = {}
    number = 0
    for event in events:
        if event['kind'] == 'question':
            number += 1
        elif event['kind'] == 'analysis':
            analyses[number] = event
    return analyses


def save_evaluation_items(conn, session_id, number, evaluation_id, event):
    assessment = event.get('assessment', {})
    best = event.get('gap', {}).get('details', {})
    dimensions = {'star': 'exp', 'ask': 'trait', 'gibbs': 'depth'}
    for framework, items in assessment.get('details', {}).items():
        for name, score in items.items():
            conn.execute(
                'INSERT INTO public.completeness_items '
                '(id,evaluation_id,dimension,item_name,current_score,best_score,applicability) '
                'VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING',
                (detail_id(session_id, 'completeness', f'{number}:{framework}:{name}'), evaluation_id,
                 dimensions[framework], name, score, best.get(framework, {}).get(name, score), 'applicable'),
            )
    for index, issue in enumerate(assessment.get('consistency_issues', []), 1):
        conn.execute(
            'INSERT INTO public.consistency_findings '
            '(id,evaluation_id,portfolio_quote,answer_quote,answer_turn_no,discrepancy_type,confirmation_status,deduction) '
            'VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING',
            (detail_id(session_id, 'consistency', f'{number}:{index}'), evaluation_id,
             issue.get('portfolio_evidence'), issue.get('answer_evidence'),
             next((source['turn'] for source in issue.get('answer_sources', []) if source.get('turn')), None),
             issue.get('issue_type') or 'unclassified', 'difference_needs_review', 0),
        )


def oral_score(answer):
    metrics = answer.get('metrics') or {}
    rate = metrics.get('rate')
    duration = answer['duration']
    if answer.get('mode') != 'voice' or not metrics.get('sufficient') or rate is None or duration <= 0:
        return None
    count = sum(c.isalnum() for c in answer['text'])
    fillers = sum(metrics.get('fillers', {}).values())
    pauses = sum(max(0, p['duration'] - 2) for p in metrics.get('pauses', []))
    return (
        .3 * max(0, 100 - max(0, 100 - rate, rate - 260) * .7)
        + .3 * max(0, 100 - max(0, fillers / max(1, count) * 100 - 3) * 5)
        + .2 * max(0, 100 - max(0, pauses / duration * 100 - 10) * 2)
        + .2 * (60 if answer.get('timedOut') else 100)
    )


def available_mean(values):
    present = [value for value in values if value is not None]
    return mean(present) if present else None


def save_report(conn, session_id, record, questions, analyses, jsonb):
    snapshot, answers = record.get('snapshot'), record['answers']
    summary = snapshot['summary'] if snapshot else {}
    free = snapshot is None or record.get('noPortfolio')
    review = record.get('report_review') or {}
    rows = {row['number']: row for row in review.get('questions', [])}
    text_mode = record.get('mode') == 'text' or (
        bool(answers) and all(answer.get('mode') == 'text' for answer in answers)
    )
    categories = {'completeness': .45, 'relevance': .25, 'consistency': .20, 'oral': .10}
    components, weights, total, grade = {}, [], None, None
    totals = []
    if not free:
        groups = []
        for index, topic in enumerate(summary.get('topics', [])):
            examples = [(n, answer) for n, (question, answer) in enumerate(zip(questions, answers), 1)
                        if question['topic_index'] == index]
            group = {
                'completeness': available_mean((topic.get('scores') or {}).values()),
                'relevance': available_mean(rows.get(n, {}).get('relevance') for n, _ in examples),
                'consistency': available_mean(rows.get(n, {}).get('consistency') for n, _ in examples),
                'oral': None if text_mode else available_mean(oral_score(answer) for _, answer in examples),
            }
            groups.append(group)
            denominator = sum(categories[key] for key, value in group.items() if value is not None)
            weights.append({key: categories[key] / denominator for key, value in group.items()
                            if value is not None})
            totals.append(sum(group[key] * weight for key, weight in weights[-1].items())
                          if denominator else None)
        components = {key: available_mean(group[key] for group in groups) for key in categories}
        if review.get('complete') and components['relevance'] is not None:
            total = available_mean(totals)
        if total is not None:
            grade = next(label for minimum, label in [(90, 'A'), (80, 'B'), (70, 'C'), (60, 'D'), (0, 'E')]
                         if total >= minimum)
    columns = {
        'time_summary': jsonb({'elapsed_seconds': summary.get('elapsed_seconds')}),
        'relevance_summary': jsonb([{'number': n, 'score': e['relevance'].get('relevance_score'),
                                     'label': e.get('relevance_status')} for n, e in analyses.items()]),
        'completeness_summary': jsonb(summary.get('topics')),
        'speech_summary': jsonb([oral_score(answer) for answer in answers]),
        'answer_status_summary': jsonb([{'number': n, 'timeout': bool(a.get('timedOut')),
                                         'substantive': not no_content_reason(a['text'])}
                                        for n, a in enumerate(answers, 1)]),
        'decision_summary': jsonb([{'number': n, 'decision': e.get('gap', {}).get('decision'),
                                    'reason': e.get('gap', {}).get('reason')} for n, e in analyses.items()]),
        'improvement_suggestions': jsonb([row['advice'] for row in rows.values() if row.get('advice')]),
        'consistency_summary': jsonb([issue for event in analyses.values()
                                      for issue in event.get('assessment', {}).get('consistency_issues', [])])
        if not free else None,
        'component_scores': jsonb(components) if not free else None,
        'effective_weights': jsonb(weights) if not free else None,
        'total_score': total,
        'grade': grade,
    }
    names = ','.join(columns)
    placeholders = ','.join('%s' for _ in columns)
    updates = ','.join(f'{name}=EXCLUDED.{name}' for name in columns)
    conn.execute(
        f'INSERT INTO public.reports (id,session_id,report_type,{names}) VALUES (%s,%s,%s,{placeholders}) '
        f'ON CONFLICT (id) DO UPDATE SET {updates}',
        (detail_id(session_id, 'report', 1), session_id, 'free_basic' if free else 'personalized_full',
         *columns.values()),
    )


def save_details(conn, session_id, record, jsonb, portfolio_id):
    snapshot = record.get('snapshot')
    answers = record['answers']
    if snapshot is None:
        topics = [{'type': '自我介紹' if i == 0 else '常見問題'} for i in range(len(answers))]
        questions = [{'topic_index': i, 'text': a['question'], 'question_kind': 'main'}
                     for i, a in enumerate(answers)]
        events = []
        finished, current, pending = True, None, False
    else:
        runtime = snapshot['runtime']
        events = snapshot['log']
        topics = snapshot['topics']
        questions = [event for event in events if event['kind'] == 'question']
        finished, current = runtime['finished'], runtime['index']
        pending = runtime['pending_answer'] is not None
    if len(answers) > len(questions) or any(a['question'] != q['text'] for a, q in zip(answers, questions)):
        raise ValueError('作答與面試題目順序不符。')

    ended = {event['topic_index']: event for event in events if event['kind'] == 'topic_end'}
    analyses = answer_analyses(events)
    followups = {}
    reason = None
    asked_number = 0
    for event in events:
        if event['kind'] == 'followup_reason':
            reason = event
        elif event['kind'] == 'question':
            asked_number += 1
            if event['question_kind'] == 'followup' and reason:
                followups[asked_number] = reason
            reason = None
    active = snapshot['runtime'].get('active') if snapshot else None
    sequence = {}
    parents = {}
    context_answers = {}
    for number, question in enumerate(questions, 1):
        index = question['topic_index']
        if index not in sequence:
            sequence[index] = 0
            parents[index] = detail_id(session_id, 'question', number)
            topic = topics[index]
            topic_end = ended.get(index, {})
            progress = active if index == current and active else {}
            event_id = detail_id(portfolio_id, 'event', topic['event_id']) if portfolio_id and topic.get('event_id') else None
            conn.execute(
                'INSERT INTO public.interview_units (id,session_id,topic_type,sequence_no,elapsed_ms,'
                'followup_count,followup_limit,restatement_used,status,termination_reason,event_id,question_bank_id) '
                'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'
                '(SELECT id FROM public.events WHERE id=%s AND portfolio_id=%s),%s) '
                'ON CONFLICT (id) DO UPDATE SET '
                'elapsed_ms=EXCLUDED.elapsed_ms,followup_count=EXCLUDED.followup_count,'
                'restatement_used=EXCLUDED.restatement_used,status=EXCLUDED.status,'
                'termination_reason=EXCLUDED.termination_reason',
                (detail_id(session_id, 'unit', index + 1), session_id, topic['type'], index + 1,
                 milliseconds(topic_end.get('topic_elapsed', progress.get('elapsed'))),
                 sum(q['topic_index'] == index and q['question_kind'] == 'followup' for q in questions),
                 1 if index == 0 else 2,
                 any(q['topic_index'] == index and q['question_kind'] == 'restate' for q in questions),
                 'completed' if finished or topic_end else 'active', topic_end.get('reason'),
                 event_id, portfolio_id, topic.get('question_bank_id')),
            )
        sequence[index] += 1
        question_id = detail_id(session_id, 'question', number)
        kind = question['question_kind']
        followup = followups.get(number, {})
        source = 'fixed' if index == 0 else (
            'question_bank' if topics[index]['type'] == '常見問題' else 'portfolio')
        conn.execute(
            'INSERT INTO public.interview_questions (id,unit_id,sequence_no,question_kind,'
            'parent_question_id,question_text,question_source,answer_limit_seconds,followup_reason,'
            'question_framework,is_outside_portfolio,asked_at,event_id,question_bank_id) '
            'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'
            '(SELECT event_id FROM public.interview_units WHERE id=%s AND %s),%s) ON CONFLICT (id) DO NOTHING',
            (question_id, detail_id(session_id, 'unit', index + 1), sequence[index],
             'rephrase' if kind == 'restate' else kind, parents[index] if sequence[index] > 1 else None,
             question['text'], source, topics[index].get('answer_limit', 90 if index == 0 else 120),
             followup.get('follow_up_reason'), followup.get('method') or followup.get('framework'),
             followup.get('targets_outside_portfolio'),
             datetime.fromisoformat(question['asked_at']) if question.get('asked_at') else None,
             detail_id(session_id, 'unit', index + 1), kind == 'main',
             topics[index].get('question_bank_id') if kind == 'main' else None),
        )
        if number > len(answers):
            continue
        answer = answers[number - 1]
        answer_id = detail_id(session_id, 'answer', number)
        waiting = pending and number == len(answers)
        substantive = not no_content_reason(answer['text'])
        event = analyses.get(number)
        analysis = 'failed' if waiting and record.get('error') else (
            'pending' if waiting else 'completed' if event else 'skipped')
        conn.execute(
            'INSERT INTO public.answers (id,question_id,transcript,duration_ms,answer_status,'
            'is_substantive,included_in_context,analysis_status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) '
            'ON CONFLICT (id) DO UPDATE SET transcript=EXCLUDED.transcript,duration_ms=EXCLUDED.duration_ms,'
            'answer_status=EXCLUDED.answer_status,is_substantive=EXCLUDED.is_substantive,'
            'included_in_context=EXCLUDED.included_in_context,analysis_status=EXCLUDED.analysis_status',
            (answer_id, question_id, answer['text'],
             milliseconds(answer['duration']), 'timeout' if answer.get('timedOut') else 'submitted',
             substantive, bool(event), analysis),
        )
        if event:
            evaluation_id = detail_id(session_id, 'evaluation', number)
            history = context_answers.setdefault(index, [])
            history.append(answer_id)
            relevance, gap = event.get('relevance', {}), event.get('gap', {})
            conn.execute(
                'INSERT INTO public.evaluations (id,unit_id,answer_id,completeness_answer_ids,'
                'compared_question_id,cosine_similarity,bi_encoder_score,cross_encoder_score,'
                'relevance_score,relevance_label,completeness_scores,next_action,decision_reason) '
                'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING',
                (evaluation_id, detail_id(session_id, 'unit', index + 1),
                 answer_id, list(history),
                 question_id if event.get('relevance_scope') == 'current_question' else parents[index],
                 relevance.get('vector_score'),
                 relevance.get('bi_encoder_score'), relevance.get('cross_score'),
                 relevance.get('relevance_score'), event.get('relevance_status'), jsonb(gap.get('scores')),
                 gap.get('decision'), gap.get('reason')),
            )
            save_evaluation_items(conn, session_id, number, evaluation_id, event)
        metrics = answer.get('metrics')
        if isinstance(metrics, dict):
            conn.execute(
                'INSERT INTO public.speech_metrics (id,answer_id,speech_rate,filler_stats,pause_stats,data_sufficient,'
                'speech_score,time_management) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING',
                (detail_id(session_id, 'speech', number), answer_id,
                 metrics.get('rate'), jsonb(metrics.get('fillers')), jsonb(metrics.get('pauses')),
                 bool(metrics.get('sufficient')),
                 oral_score(answer) if snapshot and not record.get('noPortfolio') else None,
                 'timeout' if answer.get('timedOut') else 'within_limit'),
            )
    conn.execute(
        'UPDATE public.interview_sessions SET current_unit_id=%s,pending_answer_id=%s WHERE id=%s',
        (detail_id(session_id, 'unit', current + 1) if not finished and current in sequence else None,
         detail_id(session_id, 'answer', len(answers)) if pending and answers else None, session_id),
    )
    if finished:
        save_report(conn, session_id, record, questions, analyses, jsonb)
