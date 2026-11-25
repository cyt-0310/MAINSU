import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import web_interviews as web
from test_text_pipeline import topics, Services

class VoiceWebTests(unittest.TestCase):
    def test_saved_before_analysis_and_idempotent_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / 'prepared'
            folder.mkdir()
            web.write_json(folder / 'topics.json', topics())
            web.write_json(root / 'submission.json', {})
            with patch.object(web, 'ROOT', root / 'sessions'), patch.object(web, 'path_for', return_value=root), patch.object(web, 'portfolio_record', return_value={'status':'ready'}):
                first = web.start({'school':'Test','department':'Test'})
                payload = {'requestId':'test-1','text':'a meaningful answer','duration':10,'mode':'voice','metrics':{'rate':120}}
                with patch.object(web, 'services', side_effect=RuntimeError('offline')):
                    retry = web.turn(first['id'], payload)
                self.assertTrue(retry['awaitingRetry'])
                self.assertEqual(len(retry['answers']), 1)
                self.assertEqual(web.active_sessions()[0]['id'], first['id'])
                self.assertEqual(web.resume_or_start({'school':'Test','department':'Test'})['id'], first['id'])
                with patch.object(web, 'services', return_value=Services(outside=True)):
                    result = web.turn(first['id'], {})
                    duplicate = web.turn(first['id'], payload)
                    stale_retry = web.turn(first['id'], {'retryOnly': True})
                self.assertFalse(result['awaitingRetry'])
                self.assertEqual(len(duplicate['answers']), 1)
                self.assertEqual(stale_retry['pending'], result['pending'])
                self.assertAlmostEqual(duplicate['summary']['elapsed_seconds'], 10, delta=.1)

    def test_no_portfolio_requires_confirmation_and_uses_common_questions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(web, 'ROOT', root / 'sessions'), patch.object(web, 'path_for', return_value=root):
                payload = {'school':'Test','department':'資訊管理','mode':'text'}
                with self.assertRaises(ValueError):
                    web.start(payload)
                result = web.start({**payload, 'noPortfolio':True})
                self.assertTrue(result['noPortfolio'])
                self.assertEqual(result['mode'], 'text')
                self.assertIsNone(result["completedAt"])
                with self.assertRaises(ValueError):
                    web.turn(result["id"], {"text":"wrong mode","duration":1,"mode":"voice"})
                record = web.read_json(web.file_for(result['id']))
                self.assertEqual([t['type'] for t in record['snapshot']['topics']], ['自我介紹','常見問題','常見問題'])
                self.assertEqual(web.services(None).index.search('test'), [])
                web.write_json(root / 'submission.json', {})
                with patch.object(web, 'portfolio_record', return_value={'status':'parsing'}):
                    with self.assertRaises(ValueError):
                        web.start({**payload, 'noPortfolio':True})

    def test_progress_events_are_real_and_scoped(self):
        from interview_gap_detection.api_retry import retry_progress, retry_transient, TemporaryServiceError
        events = []
        with retry_progress(events.append), patch('interview_gap_detection.api_retry.time.sleep'), \
             patch('builtins.print'):
            from unittest.mock import Mock
            operation = Mock(side_effect=[TemporaryServiceError('busy'), 'ok'])
            self.assertEqual(retry_transient(operation, provider='gemini'), 'ok')
        self.assertEqual([e['state'] for e in events], ['requesting','retrying','requesting'])
        self.assertEqual(events[1]['delay'], 2)

if __name__ == '__main__':
    unittest.main()
