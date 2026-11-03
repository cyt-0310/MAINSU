"""Step 5: source-linked event records and persistent semantic evidence retrieval."""
import hashlib
import json
import math
from pathlib import Path


class SentenceEmbedder:
    def __init__(self, model_name='shibing624/text2vec-base-chinese'):
        self.model_name = model_name
        self._model = None

    def encode(self, texts):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model.encode(texts, normalize_embeddings=True).tolist()


def event_records(portfolio):
    units = {u['id']: u for u in portfolio['reading_units']}
    records = []
    for event in portfolio['events']:
        refs = [units[i] for i in event.get('source_unit_ids', []) if i in units]
        if not refs:
            continue
        records.append({
            'event_id': event['id'], 'title': event['title'],
            'parent_event_id': event.get('parent_event_id'),
            'child_event_ids': event.get('child_event_ids', []),
            'status': 'candidate_needs_review',
            'source_file': portfolio['source_events_json'],
            'text': '\n'.join(u['text'] for u in refs),
            'evidence': [{k: u.get(k) for k in ('id', 'page', 'bbox', 'locations', 'text', 'block_ids', 'review_required')} for u in refs],
            'explicit_role_mentions': event.get('role_mentions', []),
            'subsections': event.get('subsections', []),
        })
    if not records:
        raise ValueError('No source-linked candidate events; review event segmentation first')
    return records


def chunks_for(records, max_chars=1000):
    chunks = []
    for event in records:
        for unit in event['evidence']:
            for start in range(0, len(unit['text']), max_chars):
                chunks.append({
                    'chunk_id': f"{event['event_id']}:{unit['id']}:{start}",
                    'event_id': event['event_id'], 'title': event['title'],
                    'unit_id': unit['id'], 'page': unit['page'], 'bbox': unit['bbox'],
                    'source_file': event['source_file'], 'char_start': start,
                    'text': unit['text'][start:start + max_chars],
                })
    return chunks


class EvidenceIndex:
    def __init__(self, chunks, embedder, vectors=None):
        self.chunks, self.embedder = chunks, embedder
        self.vectors = vectors if vectors is not None else embedder.encode([c['text'] for c in chunks])
        if len(self.vectors) != len(chunks) or not chunks:
            raise ValueError('Empty or inconsistent evidence index')
        size = len(self.vectors[0])
        if not size or any(len(v) != size or any(not math.isfinite(x) for x in v) for v in self.vectors):
            raise ValueError('Invalid embedding vectors')

    def search(self, query, event_ids=(), limit=6):
        vector = self.embedder.encode([query])[0]
        if len(vector) != len(self.vectors[0]):
            raise ValueError('Embedding dimension mismatch')
        def cosine(other):
            denom = math.sqrt(sum(x*x for x in vector) * sum(x*x for x in other))
            return sum(a*b for a, b in zip(vector, other)) / denom if denom else 0
        ranked = sorted(range(len(self.chunks)), key=lambda i: cosine(self.vectors[i]), reverse=True)
        # Reserve evidence for the selected event, then retrieve from the whole portfolio.
        selected = [i for i in ranked if self.chunks[i]['event_id'] in event_ids][:max(1, limit//2)] if event_ids else []
        selected += [i for i in ranked if i not in selected][:limit-len(selected)]
        return [dict(self.chunks[i], similarity=round(cosine(self.vectors[i]), 5)) for i in selected]

    def save(self, path):
        payload = {'schema_version': 1, 'model': self.embedder.model_name,
                   'chunks': self.chunks, 'vectors': self.vectors}
        payload['content_sha256'] = hashlib.sha256(json.dumps(self.chunks, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    @classmethod
    def load(cls, path, embedder):
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        digest = hashlib.sha256(json.dumps(data['chunks'], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        if data['model'] != embedder.model_name or digest != data['content_sha256']:
            raise ValueError('Index model or source metadata mismatch; rebuild index')
        return cls(data['chunks'], embedder, data['vectors'])
