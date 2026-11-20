import contextlib
import io
import unittest
from run_text_interview import format_analysis, format_relevance_summary, windows_answer
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


class AnalysisDisplayTests(unittest.TestCase):
    def test_shows_relevance_and_completeness_after_each_answer(self):
        clock = Clock()
        session = InterviewSession(topics(), Services(value=0.5), clock)
        session.start()
        session.submit('自介', timed_out=True)
        start = len(session.log)
        session.submit('主問回答')
        text = '\n'.join(format_analysis(session.log[start:]))
        self.assertIn('相關度 0.70（切題）', text)
        self.assertIn('個人特質 50% 未通過、深度邏輯 50% 未通過、經驗內容 50% 未通過', text)
        self.assertIn('完整度整體：未通過', text)

    def test_completeness_pass_is_shown(self):
        session = InterviewSession(topics(), Services(value=1), Clock())
        session.start()
        session.submit('自介', timed_out=True)
        session.submit('自介', timed_out=True)
        start = len(session.log)
        session.submit('完整回答')
        text = '\n'.join(format_analysis(session.log[start:]))
        self.assertIn('個人特質 100% 通過、深度邏輯 100% 通過、經驗內容 100% 通過', text)
        self.assertIn('完整度整體：通過', text)

    def test_low_topic_time_still_analyzes_then_switches(self):
        clock = Clock()
        session = InterviewSession(topics(), Services(), clock)
        session.start()
        clock.advance(200)
        start = len(session.log)
        event = session.submit('回答')
        lines = format_analysis(session.log[start:])
        self.assertTrue(lines[0].startswith('【本題分析】相關度'))
        self.assertIn('剩餘不足 60 秒', lines[-1])
        self.assertEqual(event['topic_index'], 1)
        self.assertEqual(session.relevance_summary()['topics'][0]['questions'][0]['relevance_score'], .7)

    def test_empty_answer_shows_zero_relevance_and_restates(self):
        session = InterviewSession(topics(), Services(), Clock())
        session.start()
        start = len(session.log)
        event = session.submit('', timed_out=True)
        self.assertEqual(event['question_kind'], 'restate')
        self.assertEqual(format_analysis(session.log[start:]), ['【本題分析】未作答，相關度視為 0.00'])

    def test_final_relevance_is_per_question_then_topic_mean(self):
        # intro .9; topic 1 off-topic .2 then restated answer .5 -> mean .35; topic 2 unanswered twice -> 0
        session = InterviewSession(topics(), Services([.9, .2, .5], value=1), Clock())
        session.start()
        session.submit('自介')
        self.assertEqual(session.submit('離題')['question_kind'], 'restate')
        session.submit('補充')
        session.submit('', timed_out=True)
        session.submit('', timed_out=True)
        self.assertTrue(session.finished)
        summary = session.relevance_summary()
        self.assertEqual([[q['relevance_score'] for q in t['questions']] for t in summary['topics']],
                         [[.9], [.2, .5], [0, 0]])
        self.assertEqual([q['question_kind'] for q in summary['topics'][1]['questions']], ['main', 'restate'])
        self.assertEqual([t['relevance_score'] for t in summary['topics']], [.9, .35, 0])
        self.assertAlmostEqual(summary['overall'], .417)
        self.assertEqual(session.snapshot()['relevance_summary'], summary)
        text = '\n'.join(format_relevance_summary(summary))
        self.assertIn('主題 1（學習歷程）：平均 0.35', text)
        self.assertIn('  2. 重述：0.50', text)
        self.assertIn('整場相關度：0.42', text)
        self.assertIn('【最終完整度】', text)
        self.assertIn('主題 1（學習歷程）：個人特質 100% 通過、深度邏輯 100% 通過、經驗內容 100% 通過（整體通過）', text)
        self.assertIn('主題 2（學習歷程）：無（沒有已分析的回答）', text)
