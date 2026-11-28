"""Store interview questions and answers in the existing PostgreSQL tables."""
from hashlib import md5
from uuid import UUID

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


def save_details(conn, session_id, record, jsonb):
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
            conn.execute(
                'INSERT INTO public.interview_units (id,session_id,topic_type,sequence_no,elapsed_ms,'
                'followup_count,followup_limit,restatement_used,status,termination_reason) '
                'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO UPDATE SET '
                'elapsed_ms=EXCLUDED.elapsed_ms,followup_count=EXCLUDED.followup_count,'
                'restatement_used=EXCLUDED.restatement_used,status=EXCLUDED.status,'
                'termination_reason=EXCLUDED.termination_reason',
                (detail_id(session_id, 'unit', index + 1), session_id, topic['type'], index + 1,
                 milliseconds(topic_end.get('topic_elapsed', progress.get('elapsed'))),
                 sum(q['topic_index'] == index and q['question_kind'] == 'followup' for q in questions),
                 1 if index == 0 else 2,
                 any(q['topic_index'] == index and q['question_kind'] == 'restate' for q in questions),
                 'completed' if finished or topic_end else 'active', topic_end.get('reason')),
            )
        sequence[index] += 1
        question_id = detail_id(session_id, 'question', number)
        kind = question['question_kind']
        source = 'fixed' if index == 0 else (
            'question_bank' if topics[index]['type'] == '常見問題' else 'portfolio')
        conn.execute(
            'INSERT INTO public.interview_questions (id,unit_id,sequence_no,question_kind,'
            'parent_question_id,question_text,question_source,answer_limit_seconds) '
            'VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING',
            (question_id, detail_id(session_id, 'unit', index + 1), sequence[index],
             'rephrase' if kind == 'restate' else kind, parents[index] if sequence[index] > 1 else None,
             question['text'], source, topics[index].get('answer_limit', 90 if index == 0 else 120)),
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
            history = context_answers.setdefault(index, [])
            history.append(answer_id)
            relevance, gap = event.get('relevance', {}), event.get('gap', {})
            conn.execute(
                'INSERT INTO public.evaluations (id,unit_id,answer_id,completeness_answer_ids,'
                'compared_question_id,cosine_similarity,bi_encoder_score,cross_encoder_score,'
                'relevance_score,relevance_label,completeness_scores,next_action,decision_reason) '
                'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING',
                (detail_id(session_id, 'evaluation', number), detail_id(session_id, 'unit', index + 1),
                 answer_id, list(history), parents[index], relevance.get('cosine_similarity'),
                 relevance.get('bi_encoder_score'), relevance.get('cross_encoder_score'),
                 relevance.get('relevance_score'), event.get('relevance_status'), jsonb(gap.get('scores')),
                 gap.get('decision'), gap.get('reason')),
            )
        metrics = answer.get('metrics')
        if isinstance(metrics, dict):
            conn.execute(
                'INSERT INTO public.speech_metrics (id,answer_id,speech_rate,filler_stats,pause_stats,data_sufficient) '
                'VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING',
                (detail_id(session_id, 'speech', number), answer_id,
                 metrics.get('rate'), jsonb(metrics.get('fillers')), jsonb(metrics.get('pauses')),
                 bool(metrics.get('sufficient'))),
            )
    conn.execute(
        'UPDATE public.interview_sessions SET current_unit_id=%s,pending_answer_id=%s WHERE id=%s',
        (detail_id(session_id, 'unit', current + 1) if not finished and current in sequence else None,
         detail_id(session_id, 'answer', len(answers)) if pending and answers else None, session_id),
    )
    if finished:
        summary = snapshot['summary'] if snapshot else {}
        conn.execute(
            'INSERT INTO public.reports (id,session_id,report_type,time_summary,completeness_summary,decision_summary) '
            'VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO UPDATE SET '
            'time_summary=EXCLUDED.time_summary,completeness_summary=EXCLUDED.completeness_summary,'
            'decision_summary=EXCLUDED.decision_summary',
            (detail_id(session_id, 'report', 1), session_id,
             'free_basic' if snapshot is None else 'personalized_full',
             jsonb({'elapsed_seconds': summary.get('elapsed_seconds')}),
             jsonb(summary.get('topics')), jsonb(record.get('report_review'))),
        )
