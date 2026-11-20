"""Docling events JSON -> existing interview API; no implicit sample fallback."""
import argparse
import json
from pathlib import Path


def load_portfolio_events(path, student_name=None):
    path = Path(path)
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    units = data.get('reading_units')
    if not isinstance(units, list):
        raise ValueError('Expected Docling events JSON with reading_units')
    selected = [u for u in units if not u.get('exclude_from_events')
                and u.get('type') not in ('page_header', 'page_footer', 'page_navigation')
                and isinstance(u.get('text'), str) and u['text'].strip()]
    if not selected:
        raise ValueError('No usable PDF text; check parsing/OCR before interviewing')
    return {
        'student_name': student_name or '未提供',
        'pdf_name': path.name.removesuffix('.events.json') + '.pdf',
        'full_text': '\n\n'.join(f"[PDF頁 {u.get('page', '?')} / {u.get('id', '?')}]\n{u['text']}" for u in selected),
        'source_events_json': str(path.resolve()),
        'reading_units': selected,
        'events': data.get('events', []),
    }


FIELDS = {
    'star': ('why_score', 'how_score', 'what_score', 'role_score', 'action_score'),
    'ask': ('skill_score', 'attitude_score', 'knowledge_score'),
    'gibbs': ('reflection_score', 'challenge_score'),
}


def validate_details(details):
    if not isinstance(details, dict) or set(details) != set(FIELDS):
        raise ValueError('Expected star, ask, gibbs')
    for group, keys in FIELDS.items():
        if not isinstance(details[group], dict) or set(details[group]) != set(keys):
            raise ValueError(f'Invalid fields in {group}')
        for value in details[group].values():
            if type(value) not in (int, float) or value not in (0, 0.5, 1):
                raise ValueError('Scores must be 0, 0.5 or 1')


def evaluate(request, portfolio):
    from interview_gap_detection.gap_detection import detect_gap
    if 'details' in request:
        assessment = {'details': request['details'], 'mode': 'provided_scores'}
    else:
        from interview_gap_detection.assessment import assess_answer
        assessment = assess_answer(request['topic'], request['qa_history'], portfolio)
    validate_details(assessment['details'])
    previous = request.get('previous_details')
    if previous is not None:
        validate_details(previous)
    state = request['state']
    for key in ('followup_count', 'max_followups', 'total_questions', 'interview_elapsed', 'topic_elapsed'):
        value = state[key]
        if type(value) not in (int, float) or not 0 <= value < float('inf'):
            raise ValueError(f'Invalid state: {key}')
    gap = detect_gap(assessment['details'], previous, **state)
    return {'assessment': assessment, 'gap': gap}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('events_json')
    parser.add_argument('--request', help='Omit to only convert PDF output; details = offline; topic/qa_history = OpenAI')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    portfolio = load_portfolio_events(args.events_json)
    result = {'portfolio': portfolio}
    if args.request:
        request = json.loads(Path(args.request).read_text(encoding='utf-8-sig'))
        result.update(evaluate(request, portfolio))
    with Path(args.output).open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
