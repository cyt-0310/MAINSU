import os
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from pydantic import BaseModel, ValidationError
from interview_gap_detection import llm_client


class Result(BaseModel):
    message: str


class GeminiClientTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {'LLM_PROVIDER': 'gemini', 'GEMINI_MODEL': 'gemini-test',
                                                   'GEMINI_TRANSPORT': 'sdk',
                                                   'OPENAI_MODEL': 'unused-openai-model'})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.old = llm_client._gemini_client
        self.client = Mock()
        llm_client._gemini_client = self.client

    def tearDown(self):
        llm_client._gemini_client = self.old

    def test_explicit_gemini_ignores_stale_openai_model(self):
        self.client.interactions.create.return_value = SimpleNamespace(status='completed', output_text='{"message":"正常"}')
        with patch.object(llm_client, '_client') as openai:
            response = llm_client.call_llm('資料', Result)
            openai.responses.parse.assert_not_called()
        self.assertEqual(response.message, '正常')
        args = self.client.interactions.create.call_args.kwargs
        self.assertEqual(args['model'], 'gemini-test')
        self.assertEqual(args['response_format']['schema'], Result.model_json_schema())
        self.assertFalse(args['store'])
        self.assertEqual(args['timeout'], 60)

    def test_blocked_empty_and_incomplete_fail_closed(self):
        for status, text in [('completed', ''), ('failed', '{}'), ('in_progress', '{}')]:
            self.client.interactions.create.return_value = SimpleNamespace(status=status, output_text=text)
            with self.assertRaises(RuntimeError):
                llm_client.call_llm('資料', Result)

    def test_invalid_json_is_not_a_score(self):
        self.client.interactions.create.return_value = SimpleNamespace(status='completed', output_text='not json')
        with self.assertRaises(ValidationError):
            llm_client.call_llm('資料', Result)

    def test_quota_error_does_not_switch_provider(self):
        class QuotaError(Exception):
            code = 429
        self.client.interactions.create.side_effect = QuotaError()
        with patch.object(llm_client, '_client') as openai:
            with self.assertRaisesRegex(RuntimeError, '429'):
                llm_client.call_llm('資料', Result)
            openai.responses.parse.assert_not_called()

    def test_missing_key_and_timeout_milliseconds(self):
        llm_client._gemini_client = None
        with patch.dict(os.environ, {'LLM_PROVIDER': 'gemini'}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'GEMINI_API_KEY'):
                llm_client.get_client()
        factory = Mock(return_value=self.client)
        with patch.dict(sys.modules, {'google': SimpleNamespace(genai=SimpleNamespace(Client=factory))}):
            with patch.dict(os.environ, {'GEMINI_API_KEY': 'fake-gemini-key'}):
                self.assertIs(llm_client.get_client(), self.client)
        self.assertEqual(factory.call_args.kwargs['http_options']['timeout'], 60000)

    def test_explicit_timeout_seconds_and_safe_message(self):
        class APITimeoutError(Exception):
            pass
        self.client.interactions.create.side_effect = APITimeoutError('raw network details')
        with patch.dict(os.environ, {'GEMINI_TIMEOUT_SECONDS': '120'}):
            with self.assertRaisesRegex(RuntimeError, '連線逾時') as caught:
                llm_client.call_llm('資料', Result)
        self.assertEqual(self.client.interactions.create.call_args.kwargs['timeout'], 120)
        self.assertNotIn('raw network details', str(caught.exception))

    def test_invalid_timeouts_and_status_code_quota(self):
        for value in ('0', '-1', 'nan', 'inf', 'text', '301'):
            with patch.dict(os.environ, {'GEMINI_TIMEOUT_SECONDS': value}):
                with self.assertRaises(RuntimeError):
                    llm_client.get_gemini_timeout()
        class RateLimitError(Exception):
            status_code = 429
        self.client.interactions.create.side_effect = RateLimitError()
        with self.assertRaisesRegex(RuntimeError, '429'):
            llm_client.call_llm('資料', Result)

    def test_invalid_provider_and_default_model(self):
        with patch.dict(os.environ, {'LLM_PROVIDER': 'unknown'}):
            with self.assertRaises(RuntimeError):
                llm_client.get_provider()
        with patch.dict(os.environ, {'GEMINI_MODEL': ''}):
            self.assertEqual(llm_client.get_model(), 'gemini-3.5-flash-lite')


if __name__ == '__main__':
    unittest.main()
