from pathlib import Path
import unittest
from bridge import load_portfolio_events
from evidence import event_records


class SharedSampleTests(unittest.TestCase):
    def test_public_fictional_sample_has_event_sources(self):
        root = Path(__file__).resolve().parents[2]
        sample = root / 'examples' / 'fictional.events.json'
        if not sample.exists():
            self.skipTest('Public sample is supplied in the GitHub export')
        portfolio = load_portfolio_events(sample)
        records = event_records(portfolio)
        self.assertEqual(len(records), 1)
        self.assertIn('虛構', records[0]['text'])
        self.assertEqual(records[0]['evidence'][0]['page'], 1)


if __name__ == '__main__':
    unittest.main()
