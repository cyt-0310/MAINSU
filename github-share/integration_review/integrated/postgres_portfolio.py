"""Relational storage for parsed portfolio evidence."""
import json
from uuid import UUID

from postgres_interview_details import detail_id


def save_parsed_portfolio(conn, user_id, portfolio_id, manifest, parsed, prepared, jsonb):
    skills = json.loads((prepared / 'skills.candidate.json').read_text(encoding='utf-8'))
    conn.execute(
        'UPDATE public.portfolios SET candidate_skill_tree=%s,parse_status=%s WHERE id=%s AND user_id=%s',
        (jsonb(skills), 'completed', portfolio_id, user_id),
    )
    blocks = {}
    for number, (document, data) in enumerate(zip(manifest['files'], parsed, strict=True), 1):
        document_id = detail_id(portfolio_id, 'document', number)
        source = document.get('source') or {'portfolio': manifest['id'], 'file': document['id']}
        storage_key = f"{UUID(str(user_id))}:{source['portfolio']}/{source['file']}.pdf"
        conn.execute(
            'INSERT INTO public.documents (id,portfolio_id,document_type,file_name,storage_key,size_bytes) '
            'VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING',
            (document_id, portfolio_id, document['category'], document['name'], storage_key, document['size']),
        )
        for unit in data['reading_units']:
            if not isinstance(unit.get('page'), int):
                continue
            key = (number, unit['id'])
            block_id = blocks[key] = detail_id(document_id, 'block', unit['id'])
            conn.execute(
                'INSERT INTO public.document_blocks (id,document_id,block_type,page_number,bbox,'
                'original_text,cleaned_text,extraction_method) '
                'VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING',
                (block_id, document_id, unit.get('type') or 'text', unit['page'], jsonb(unit.get('bbox')),
                 unit.get('original_text'), unit['text'], unit.get('extraction_method') or 'docling'),
            )
    events = json.loads((prepared / 'events.structured.json').read_text(encoding='utf-8'))
    event_ids = {event['event_id']: detail_id(portfolio_id, 'event', event['event_id']) for event in events}
    fields = {'動機': 'motivation', '角色': 'personal_role', '行動': 'actions',
              '成果': 'result', '反思': 'reflection', '能力': 'abilities'}
    for event in events:
        event_key = event['event_id']
        event_id = event_ids[event_key]
        aspects = event.get('aspects', {})
        values = ['\n'.join(c['text'] for c in aspects.get(label, [])) or None
                  for label in list(fields)[:-1]]
        conn.execute(
            'INSERT INTO public.events (id,portfolio_id,title,event_type,motivation,personal_role,actions,result,'
            'reflection,abilities,department_relevance) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) '
            'ON CONFLICT (id) DO NOTHING',
            (event_id, portfolio_id, event['title'], event.get('category') or '其他', *values,
             jsonb(aspects.get('能力', [])), jsonb(event.get('department_relevance'))),
        )
        number = int(event_key.split(':', 1)[0].removeprefix('doc'))
        for label, claims in aspects.items():
            for i, claim in enumerate(claims):
                unit_id = claim['source_unit_id']
                block_id = blocks.get((number, unit_id))
                if block_id is None:
                    continue
                unit = next(u for u in event['evidence'] if u['id'] == unit_id)
                quote = claim['quote']
                offset = unit['text'].find(quote)
                if offset < 0:
                    continue
                conn.execute(
                    'INSERT INTO public.event_sources (id,event_id,field_name,block_id,quote,char_start,char_end,'
                    'verification_status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING',
                    (detail_id(event_id, 'source', f'{label}:{i}'), event_id, fields[label], block_id,
                     quote, offset, offset + len(quote), 'verified'),
                )
    for event in events:
        parent_id = event_ids.get(event.get('parent_event_id'))
        if parent_id:
            conn.execute('UPDATE public.events SET parent_event_id=%s WHERE id=%s',
                         (parent_id, event_ids[event['event_id']]))
    index = json.loads((prepared / 'evidence.index.json').read_text(encoding='utf-8'))
    for chunk, vector in zip(index['chunks'], index['vectors'], strict=True):
        conn.execute(
            'INSERT INTO public.retrieval_chunks (id,portfolio_id,event_id,chunk_text,embedding,metadata) '
            'VALUES (%s,%s,%s,%s,%s::vector,%s) ON CONFLICT (id) DO NOTHING',
            (detail_id(portfolio_id, 'chunk', chunk['chunk_id']), portfolio_id, event_ids[chunk['event_id']],
             chunk['text'], json.dumps(vector), jsonb(chunk)),
        )


class PostgresEvidence:
    def __init__(self, connect, portfolio_id, embedder):
        self.connect, self.portfolio_id, self.embedder = connect, portfolio_id, embedder

    def search(self, query, event_ids=(), limit=6):
        vector = json.dumps(self.embedder.encode([query])[0])
        with self.connect() as conn:
            statement = (
                'SELECT metadata,1-(embedding <=> %s::vector) AS similarity FROM public.retrieval_chunks '
                'WHERE portfolio_id=%s '
            )
            preferred = conn.execute(
                statement + "AND metadata->>'event_id'=ANY(%s) ORDER BY similarity DESC,id LIMIT %s",
                (vector, self.portfolio_id, list(event_ids), max(1, limit // 2)),
            ).fetchall() if event_ids else []
            ranked = conn.execute(
                statement + 'ORDER BY similarity DESC,id LIMIT %s', (vector, self.portfolio_id, limit),
            ).fetchall()
        selected = {row['metadata']['chunk_id']: row for row in preferred}
        for row in ranked:
            selected.setdefault(row['metadata']['chunk_id'], row)
        return [dict(row['metadata'], similarity=round(row['similarity'], 5))
                for row in list(selected.values())[:limit]]
