import io
import json
import os
import unittest
import urllib.error
from unittest.mock import patch
from pydantic import BaseModel, ValidationError
from interview_gap_detection.gemini_rest import GeminiRESTClient
from interview_gap_detection import llm_client


class Result(BaseModel):
    message: str


def reply(text='{"message":"正常"}', reason='STOP', **extra):
    return io.BytesIO(json.dumps({'candidates': [{'finishReason': reason,
                                                'content': {'parts': [{'text': text}]}}], **extra}).encode())


class RESTTests(unittest.TestCase):
    def test_post_schema_header_key_and_seconds(self):
        with patch('urllib.request.urlopen', return_value=reply()) as open_url:
            result = GeminiRESTClient('fake-key').generate('備審測試', Result, 'models/gemini-test', 12)
        self.assertEqual(result.message, '正常')
        request = open_url.call_args.args[0]
        self.assertEqual(request.method, 'POST')
        self.assertTrue(request.full_url.endswith('/models/gemini-test:generateContent'))
        self.assertNotIn('fake-key', request.full_url)
        self.assertEqual(request.get_header('X-goog-api-key'), 'fake-key')
        self.assertEqual(open_url.call_args.kwargs['timeout'], 12)
        body = json.loads(request.data)
        self.assertEqual(body['generationConfig']['responseJsonSchema'], Result.model_json_schema())

    def test_http_errors_are_explicit_and_do_not_leak_input(self):
        for code in (400, 403, 404, 429, 503):
            error = urllib.error.HTTPError('https://example.test', code, 'secret-key-or-input', {}, io.BytesIO(b'private body'))
            with patch('urllib.request.urlopen', side_effect=error):
                with self.assertRaisesRegex(RuntimeError, str(code)) as caught:
                    GeminiRESTClient('fake-key').generate('private text', Result, 'test', 5)
            self.assertNotIn('private', str(caught.exception))
            self.assertNotIn('secret', str(caught.exception))

    def test_timeout_and_network_errors(self):
        for error in (TimeoutError(), urllib.error.URLError(TimeoutError()), urllib.error.URLError(OSError())):
            with patch('urllib.request.urlopen', side_effect=error):
                with self.assertRaises(RuntimeError):
                    GeminiRESTClient('fake-key').generate('text', Result, 'test', 5)

    def test_blocked_partial_and_empty_are_not_adopted(self):
        for response in (io.BytesIO(b'{"candidates":[]}'), reply(reason='MAX_TOKENS'), reply('')):
            with patch('urllib.request.urlopen', return_value=response):
                with self.assertRaises(RuntimeError):
                    GeminiRESTClient('fake-key').generate('text', Result, 'test', 5)

    def test_invalid_model_output_is_not_a_score(self):
        with patch('urllib.request.urlopen', return_value=reply('not JSON')):
            with self.assertRaises(ValidationError):
                GeminiRESTClient('fake-key').generate('text', Result, 'test', 5)

    def test_rest_dispatch_does_not_touch_sdk_or_openai(self):
        with patch.dict(os.environ, {'LLM_PROVIDER': 'gemini', 'GEMINI_TRANSPORT': 'rest',
                                    'GEMINI_API_KEY': 'fake-key', 'GEMINI_TIMEOUT_SECONDS': '15'}):
            with patch.object(llm_client, '_gemini_rest_client', None):
                with patch.object(llm_client, '_gemini_client') as sdk, patch.object(llm_client, '_client') as openai:
                    with patch('urllib.request.urlopen', return_value=reply()):
                        self.assertEqual(llm_client.call_llm('text', Result).message, '正常')
                    sdk.interactions.create.assert_not_called()
                    openai.responses.parse.assert_not_called()


if __name__ == '__main__':
    unittest.main()
