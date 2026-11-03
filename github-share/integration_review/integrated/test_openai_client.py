import os
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from pydantic import BaseModel
from interview_gap_detection import llm_client


class Result(BaseModel):
    value: str


class OpenAIClientTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {'LLM_PROVIDER': 'openai'})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.previous_client = llm_client._client
        self.client = Mock()
        llm_client._client = self.client

    def tearDown(self):
        llm_client._client = self.previous_client

    def test_structured_response_and_model_selection(self):
        self.client.responses.parse.return_value = SimpleNamespace(status='completed', output_parsed=Result(value='正常'))
        with patch.dict(os.environ, {'OPENAI_MODEL': 'test-model'}):
            result = llm_client.call_llm('測試輸入', Result)
        self.assertEqual(result.value, '正常')
        args = self.client.responses.parse.call_args.kwargs
        self.assertEqual(args['model'], 'test-model')
        self.assertIs(args['text_format'], Result)
        self.assertFalse(args['store'])
        self.assertNotIn('temperature', args)

    def test_no_model_requires_explicit_configuration(self):
        with patch.dict(os.environ, {'LLM_PROVIDER': 'openai'}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'OPENAI_MODEL'):
                llm_client.call_llm('資料', Result)
        self.client.responses.parse.assert_not_called()

    def test_refusal_or_missing_output_is_not_adopted(self):
        self.client.responses.parse.return_value = SimpleNamespace(status='completed', output_parsed=None)
        with patch.dict(os.environ, {'OPENAI_MODEL': 'test-model'}):
            with self.assertRaisesRegex(RuntimeError, '未提供'):
                llm_client.call_llm('資料', Result)

    def test_incomplete_output_is_not_adopted(self):
        self.client.responses.parse.return_value = SimpleNamespace(status='incomplete', output_parsed=Result(value='部分'))
        with patch.dict(os.environ, {'OPENAI_MODEL': 'test-model'}):
            with self.assertRaisesRegex(RuntimeError, '未完成'):
                llm_client.call_llm('資料', Result)

    def test_key_required_and_client_has_timeout(self):
        llm_client._client = None
        with patch.dict(os.environ, {'LLM_PROVIDER': 'openai'}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'OPENAI_API_KEY'):
                llm_client.get_client()
        factory = Mock(return_value=self.client)
        with patch.dict(sys.modules, {'openai': SimpleNamespace(OpenAI=factory)}):
            with patch.dict(os.environ, {'OPENAI_API_KEY': 'fake-for-test'}):
                self.assertIs(llm_client.get_client(), self.client)
        self.assertEqual(factory.call_args.kwargs['timeout'], 30)
        self.assertEqual(factory.call_args.kwargs['max_retries'], 1)


if __name__ == '__main__':
    unittest.main()
