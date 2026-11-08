"""Fake LLM/embeddings verify orchestration only; no live API/model accuracy claims."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ai_services import Claim, EventExtraction, EventPlan, EventQuestion, LiveServices, prepare, plan_from_profile
from test_text_pipeline import FakeEmbedder, details


def portfolio():
    return {'source_events_json': 'example.events.json', 'pdf_name': 'example.pdf',
            'reading_units': [{'id': 'u1', 'text': '我擔任組員，負責撰寫程式。', 'page': 2, 'bbox': [0, 0, 10, 10]}],
            'events': [{'id': 'e1', 'title': '程式專題', 'source_unit_ids': ['u1'], 'parent_event_id': None}]}


class AIContractTests(unittest.TestCase):
    def test_prepare_rejects_fabricated_citation_and_disambiguates_documents(self):
        def fake_call(prompt, schema):
            if schema is EventExtraction:
                return EventExtraction(category='專業相關', claims=[
                    Claim(aspect='角色', text='組員', quote='擔任組員', source_unit_id='u1'),
                    Claim(aspect='能力', text='領導能力', quote='統籌全案', source_unit_id='u1')])
            return EventPlan(questions=[EventQuestion(event_id=f'doc{i}:e1', question='請說明你的工作？', check_aspects=['行動']) for i in (1, 2)])
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            target = Path(folder)/'prepared'
            with patch('ai_services.call_llm', side_effect=fake_call):
                bank = prepare([portfolio(), portfolio()], FakeEmbedder(), target)
            self.assertEqual([t['type'] for t in bank], ['自我介紹', '學習歷程', '學習歷程'])
            records = json.loads((target/'events.structured.json').read_text(encoding='utf-8'))
            self.assertEqual(records[0]['event_id'], 'doc1:e1')
            self.assertEqual(records[1]['event_id'], 'doc2:e1')
            self.assertEqual(len(records[0]['aspects']['角色']), 1)
            self.assertEqual(records[0]['aspects']['能力'], [])
            self.assertEqual(len(records[0]['rejected_claims']), 1)
            self.assertTrue((target/'skills.candidate.json').exists())
            profile = json.loads((target/'student.profile.json').read_text(encoding='utf-8'))
            plan = json.loads((target/'question.plan.json').read_text(encoding='utf-8'))
            self.assertEqual(plan['questions'], bank)
            self.assertEqual(len(profile['events']), 2)
            self.assertEqual(profile['target_department'], plan['target_department'])
            from evidence import EvidenceIndex
            index = EvidenceIndex.load(target/'evidence.index.json', FakeEmbedder())
            with patch('ai_services.call_llm', side_effect=fake_call):
                regenerated = plan_from_profile(profile, index, Path(folder)/'replanned', create_dir=True)
            self.assertEqual(regenerated, bank)
            profile['events'][0]['evidence'][0]['text'] = '另一位學生的內容'
            with self.assertRaisesRegex(ValueError, 'source text'):
                plan_from_profile(profile, index, Path(folder)/'badplan', create_dir=True)
            self.assertFalse((Path(folder)/'badplan').exists())

    def test_consistency_keeps_both_sources_and_flags_unverified(self):
        class Index:
            def search(self, query, event_ids):
                return [{'event_id': 'e1', 'unit_id': 'u1', 'page': 2, 'text': '我擔任組員', 'source_file': 'example.events.json'}]
        services = LiveServices(Index(), portfolio())
        assessment = {'details': details(.5), 'mentions_outside_portfolio': False,
                      'consistency_issues': [
                          {'portfolio_evidence': '擔任組員', 'answer_evidence': '統籌全案'},
                          {'portfolio_evidence': '未出現的引文', 'answer_evidence': '統籌全案'}]}
        topic = {'question': '你的工作？', 'event_id': 'e1'}
        with patch('ai_services.assess_answer', return_value=assessment):
            result = services.assess(topic, [('你的工作？', '我統籌全案')])
        self.assertTrue(result['consistency_issues'][0]['source_verified'])
        self.assertFalse(result['consistency_issues'][1]['source_verified'])
        self.assertEqual(result['consistency_issues'][0]['answer_sources'][0]['turn'], 1)


if __name__ == '__main__':
    unittest.main()
