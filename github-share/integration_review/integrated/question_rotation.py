"""Rotate learning-history main questions across the previous three sessions."""
import hashlib
import re
import unicodedata

from web_portfolios import document_path, read_json

# Each angle asks for a different kind of evidence, rather than paraphrasing.
ANGLES = {
    'action': ('你在「{event}」中具體採取了哪些行動？請說明你的做法及理由。', ['具體行動', '方法', '理由']),
    'challenge': ('你在「{event}」中遇到最具挑戰性的問題是什麼？你如何克服它？', ['困難', '解決策略', '結果']),
    'reflection': ('回顧「{event}」，你最大的成長是什麼？如果重來一次，你會怎麼改善？', ['學習收穫', '反思', '改善']),
    'outcome': ('在「{event}」中，你如何判斷自己的行動是否有效？請具體說明成果或觀察依據。', ['成果', '評估依據', '個人貢獻']),
    'motivation': ('你為什麼投入「{event}」？當時的目標與選擇背後有哪些考量？', ['動機', '目標', '決策理由']),
    'transfer': ('「{event}」培養了你哪些能力？請舉例說明你會如何將它運用在{department}的學習。', ['能力', '具體例證', '科系連結']),
    'collaboration': ('在「{event}」中，你如何安排自己的責任、溝通或協調資源？請說明一個具體例子。', ['角色責任', '協調方式', '具體例證']),
}
LEGACY_HINTS = {
    'challenge': ('困難', '挫折', '挑戰', '克服'),
    'reflection': ('反思', '重來', '重新', '成長', '收穫', '學到'),
    'outcome': ('成果', '成效', '評估', '效果', '改善了'),
    'motivation': ('動機', '為什麼', '選擇', '原因'),
    'transfer': ('科系', '資管', '資訊管理', '未來', '運用在'),
    'collaboration': ('協調', '溝通', '團隊', '分工', '合作'),
    'action': ('方法', '如何', '怎麼', '採取', '運用', '做法'),
}

def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFKC', str(value or '')).casefold()
                   if c.isalnum())

def portfolio_identity(directory):
    """Identical PDF content shares history even if submitted to another department."""
    try:
        files = read_json(directory / 'submission.json').get('files', [])
        if not files:
            return None
        digests = sorted({hashlib.sha256(document_path(directory, entry).read_bytes()).hexdigest()
                          for entry in files})
        return hashlib.sha256('|'.join(digests).encode()).hexdigest()
    except (OSError, ValueError, KeyError, TypeError):
        return None

def angle_of(topic):
    if topic.get('question_angle') in ANGLES:
        return topic['question_angle']
    question = topic.get('question', '')
    return next((angle for angle, hints in LEGACY_HINTS.items()
                 if any(hint in question for hint in hints)), None)

def recent_sessions(root, target, identity, directory_for):
    candidates = []
    for path in root.glob('*.json'):
        try:
            record = read_json(path)
            if record.get('noPortfolio'):
                continue
            prior_target = record['target']
            prior_identity = record.get('portfolioIdentity')
            if not prior_identity and identity:
                prior_identity = portfolio_identity(directory_for(prior_target))
            same = (prior_identity == identity) if identity and prior_identity else prior_target == target
            if same:
                candidates.append((record.get('createdAt') or '', path.stat().st_mtime, record))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    # Legacy files lack createdAt; their file timestamp gives the known record order.
    from datetime import datetime
    def order(item):
        try:
            return datetime.fromisoformat(item[0]).timestamp() if item[0] else item[1]
        except ValueError:
            return item[1]
    return [record for _, _, record in sorted(candidates, key=order, reverse=True)[:3]]

def rotate_questions(topics, history, department):
    old = [t for r in history for t in r.get('snapshot', {}).get('topics', [])
           if t.get('event_id') and t.get('type') == '學習歷程']
    used_questions = {norm(t.get('question')) for t in old}
    result = []
    for original in topics:
        topic = dict(original)
        if topic.get('event_id') and topic.get('type') == '學習歷程':
            event = topic.get('event') or topic.get('title') or '這段學習經歷'
            same_event = [t for t in old if norm(t.get('event') or t.get('title')) == norm(event)]
            used_angles = {angle_of(t) for t in same_event}
            # Stable rotation avoids dependence on an LLM call at interview start.
            for angle, (template, aspects) in ANGLES.items():
                question = template.format(event=event, department=department)
                if angle not in used_angles and norm(question) not in used_questions:
                    topic.update(question=question, question_angle=angle, check_aspects=aspects)
                    used_questions.add(norm(question))
                    break
            else:
                raise ValueError('近期面試題目已用完，請重新分析備審以建立更多題目。')
        result.append(topic)
    return result
