import copy
import json
from pathlib import Path
import unittest
from bridge import evaluate, load_portfolio_events, validate_details

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


class IntegrationTests(unittest.TestCase):
    def test_four_real_parser_outputs(self):
        if not (ROOT / 'docling_pdf' / 'results').exists():
            self.skipTest('Private PDF results are intentionally excluded from shared source')
        for path in (ROOT / 'docling_pdf' / 'results').glob('*/*.events.json'):
            portfolio = load_portfolio_events(path)
            self.assertTrue(portfolio['full_text'])
            self.assertTrue(portfolio['events'])
            self.assertTrue(all(not u.get('exclude_from_events') for u in portfolio['reading_units']))
        self.assertEqual(len(list((ROOT / 'docling_pdf' / 'results').glob('*/*.events.json'))), 4)

    def test_decisions_and_accumulation(self):
        request = json.loads((HERE / 'request.example.json').read_text())
        result = evaluate(request, {})['gap']
        self.assertEqual(result['scores'], {'exp': 70.0, 'trait': 33.3, 'depth': 25.0})
        self.assertEqual(result['target_gap'], 'depth')
        request['previous_details'] = {g: {k: 1 for k in v} for g, v in request['details'].items()}
        self.assertEqual(evaluate(request, {})['gap']['decision'], 'switch_topic')
        request['state']['total_questions'] = 15
        self.assertEqual(evaluate(request, {})['gap']['decision'], 'end_interview')
        request['previous_details'] = None
        request['state']['total_questions'] = 1
        request['state']['followup_count'] = 2
        self.assertEqual(evaluate(request, {})['gap']['decision'], 'switch_topic')

    def test_bad_scores_rejected(self):
        request = json.loads((HERE / 'request.example.json').read_text())
        bad = copy.deepcopy(request['details'])
        bad['star']['why_score'] = 10
        with self.assertRaises(ValueError):
            validate_details(bad)


if __name__ == '__main__':
    unittest.main()
