import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

from interview_gap_detection import llm_client
from interview_gap_detection.api_retry import TemporaryServiceError, retry_clock, retry_transient
from interview_gap_detection.gemini_rest import GeminiRESTClient
from interview_session import InterviewSession
from run_text_interview import run_interview
from test_gemini_rest import Result, reply
from test_text_pipeline import Clock, Services, topics


def unavailable(code=503):
    return urllib.error.HTTPError('https://example.test', code, 'private', {},
                                  io.BytesIO(b'{"error":{"status":"UNAVAILABLE","message":"secret"}}'))


class RetryTests(unittest.TestCase):
    def test_rest_recovers_and_excludes_only_failed_attempts_and_wait(self):
        clock = Clock()
        def transport(*args, **kwargs):
            clock.advance(10)
            if clock.value < 20:
                raise unavailable()
            return reply()
        excluded = []
        with patch.dict(os.environ, {'LLM_PROVIDER': 'gemini', 'GEMINI_TRANSPORT': 'rest'}), \
             patch.object(llm_client, 'get_client', return_value=GeminiRESTClient('fake')), \
             patch('urllib.request.urlopen', side_effect=transport) as request, \
             patch('interview_gap_detection.api_retry.time.monotonic', clock), \
             patch('interview_gap_detection.api_retry.time.sleep', side_effect=clock.advance), \
             patch('interview_gap_detection.api_retry.random.uniform', return_value=0), \
             retry_clock(excluded.append):
            self.assertEqual(llm_client.call_llm('text', Result).message, '正常')
        self.assertEqual(request.call_count, 2)
        self.assertEqual(excluded, [12])
        self.assertEqual(clock.value, 22)

    def test_exhausted_retries_bounded_and_do_not_leak_payload(self):
        with patch.dict(os.environ, {'LLM_PROVIDER': 'gemini', 'GEMINI_TRANSPORT': 'rest'}), \
             patch.object(llm_client, 'get_client', return_value=GeminiRESTClient('fake')), \
             patch('urllib.request.urlopen', side_effect=lambda *a, **kw: (_ for _ in ()).throw(unavailable())) as request, \
             patch('interview_gap_detection.api_retry.time.sleep') as sleep:
            with self.assertRaises(TemporaryServiceError) as caught:
                llm_client.call_llm('private student answer', Result)
        self.assertEqual(request.call_count, 4)
        self.assertEqual(sleep.call_count, 3)
        self.assertNotIn('secret', str(caught.exception))
        self.assertNotIn('private', str(caught.exception))

    def test_bad_request_and_quota_not_retried(self):
        for code in (400, 403, 429):
            with patch('urllib.request.urlopen', side_effect=unavailable(code)) as request, \
                 patch('interview_gap_detection.api_retry.time.sleep') as sleep:
                with self.assertRaises(RuntimeError):
                    retry_transient(lambda: GeminiRESTClient('fake').generate('text', Result, 'test', 5))
            self.assertEqual(request.call_count, 1)
            sleep.assert_not_called()

    def test_sdk_503_uses_same_retry_policy(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        client = Mock()
        client.interactions.create.side_effect = [TemporaryServiceError('busy'),
            SimpleNamespace(status='completed', output_text='{"message":"ok"}')]
        with patch.dict(os.environ, {'LLM_PROVIDER': 'gemini', 'GEMINI_TRANSPORT': 'sdk'}), \
             patch.object(llm_client, 'get_client', return_value=client), \
             patch('interview_gap_detection.api_retry.time.sleep'):
            self.assertEqual(llm_client.call_llm('text', Result).message, 'ok')
        self.assertEqual(client.interactions.create.call_count, 2)


class RecoveryTests(unittest.TestCase):
    def make(self):
        clock = Clock()
        services = Services(outside=True)
        session = InterviewSession(topics(), services, clock)
        session.start()
        return session, clock, services

    def test_failed_followup_rolls_back_and_retains_answer_after_restart(self):
        session, clock, services = self.make()
        clock.advance(15)
        original = services.followup
        def fail(*args):
            clock.advance(300)
            raise TemporaryServiceError('busy')
        services.followup = fail
        with self.assertRaises(TemporaryServiceError):
            session.submit('已送出的回答')
        self.assertEqual(session.elapsed(), 15)
        self.assertEqual(session.total_questions, 1)
        self.assertEqual(session.active['qa_history'], [])
        self.assertFalse(any(row['kind'] == 'answer' for row in session.log))
        snapshot = json.loads(json.dumps(session.snapshot()))
        clock.advance(5000)
        services.followup = original
        resumed = InterviewSession.restore(snapshot, services, clock)
        self.assertEqual(resumed.elapsed(), 15)
        clock.advance(200)
        event = resumed.process_answer()
        self.assertEqual(event['question_kind'], 'followup')
        self.assertEqual(resumed.elapsed(), 15)
        self.assertEqual(resumed.total_questions, 2)
        answers = [row for row in resumed.log if row['kind'] == 'answer']
        self.assertEqual(len(answers), 1)
        self.assertEqual(answers[0]['answer'], '已送出的回答')
        self.assertEqual(answers[0]['answer_elapsed'], 15)
        self.assertFalse(answers[0]['timed_out'])
        self.assertEqual(resumed.remaining_answer_seconds(), 90)

    def test_success_after_long_retry_does_not_trigger_time_limits(self):
        session, clock, services = self.make()
        original = services.assess
        def assess(*args):
            clock.advance(400)
            # The retry layer reports failed requests and waits to the session.
            from interview_gap_detection.api_retry import _excluded_time
            _excluded_time.get()(400)
            return original(*args)
        services.assess = assess
        clock.advance(20)
        self.assertEqual(session.submit('回答')['question_kind'], 'followup')
        self.assertEqual(session.elapsed(), 20)
        self.assertEqual(session.topic_elapsed(), 20)

    def test_checkpoint_written_before_request_and_quit_resume(self):
        session, clock, services = self.make()
        clock.advance(5)
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            output = Path(folder) / 'session.json'
            def fail(*args):
                saved = json.loads(output.read_text(encoding='utf-8'))
                self.assertEqual(saved['runtime']['pending_answer']['answer'], '不能遺失的回答')
                raise TemporaryServiceError('busy')
            services.assess = fail
            with patch('run_text_interview.timed_input', return_value=('不能遺失的回答', False)), \
                 patch('builtins.input', return_value='q'):
                run_interview(session, output)
            saved = json.loads(output.read_text(encoding='utf-8'))
        self.assertIsNotNone(saved['runtime']['pending_answer'])
        self.assertFalse(saved['finished'])
        resumed = InterviewSession.restore(saved, Services(outside=True), clock)
        resumed.process_answer()
        self.assertEqual(len([row for row in resumed.log if row['kind'] == 'answer']), 1)

    def test_keyboard_interrupt_keeps_buffer_and_old_records_rejected(self):
        session, clock, services = self.make()
        services.assess = lambda *args: (_ for _ in ()).throw(KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            session.submit('已提交')
        self.assertEqual(session.pending_answer['answer'], '已提交')
        with self.assertRaisesRegex(RuntimeError, '舊紀錄'):
            InterviewSession.restore({'topics': topics()}, services, clock)

    def test_restart_with_unanswered_question_keeps_remaining_seconds(self):
        session, clock, services = self.make()
        clock.advance(12)
        snapshot = session.snapshot()
        clock.advance(9000)
        resumed = InterviewSession.restore(snapshot, services, clock)
        self.assertEqual(resumed.remaining_answer_seconds(), 78)
        self.assertEqual(resumed.total_questions, 1)


if __name__ == '__main__':
    unittest.main()
