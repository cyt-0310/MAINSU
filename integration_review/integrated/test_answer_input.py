import contextlib
import io
import unittest
from run_text_interview import windows_answer
from interview_session import InterviewSession
from test_text_pipeline import Clock, Services, topics


class Console:
    def __init__(self, text):
        self.text = list(text)
    def kbhit(self):
        return bool(self.text)
    def getwch(self):
        return self.text.pop(0)


class AnswerInputTests(unittest.TestCase):
    def read(self, text, seconds=90):
        clock = Clock()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = windows_answer(seconds, Console(text), clock, clock.advance)
        return result, clock.value, output.getvalue()

    def test_enter_submits_chinese_immediately(self):
        result, elapsed, _ = self.read('我負責程式設計\r')
        self.assertEqual(result, ('我負責程式設計', False))
        self.assertEqual(elapsed, 0)

    def test_empty_enter_prompts_without_resetting_timer(self):
        result, elapsed, output = self.read('\r', seconds=.06)
        self.assertEqual(result, ('', True))
        self.assertGreaterEqual(elapsed, .06)
        self.assertIn('尚未輸入', output)

    def test_deadline_keeps_unsubmitted_text(self):
        result, _, _ = self.read('尚未寫完', seconds=.06)
        self.assertEqual(result, ('尚未寫完', True))

    def test_backspace_and_cancel(self):
        result, _, _ = self.read('甲\b乙\r')
        self.assertEqual(result, ('乙', False))
        with self.assertRaises(KeyboardInterrupt):
            self.read('\x03')

    def test_enter_submission_records_actual_time(self):
        clock = Clock()
        session = InterviewSession(topics(), Services(value=1), clock)
        session.start()
        clock.advance(8)
        session.submit('提前回答完成')
        answer = next(e for e in session.log if e['kind'] == 'answer')
        self.assertEqual(answer['answer_elapsed'], 8)
        self.assertEqual(answer['submitted_by'], 'enter')
        self.assertFalse(answer['timed_out'])


if __name__ == '__main__':
    unittest.main()
