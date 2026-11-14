import unittest
from unittest.mock import Mock

from interview_gap_detection.answer_content import no_content_reason
from interview_session import InterviewSession
from test_text_pipeline import Clock, Services, topics


class AnswerContentTests(unittest.TestCase):
    def test_standalone_labels_placeholders_and_symbols(self):
        for answer in ('', '  ', '……！？', '測試回答範例：', '**測試回答範例：**',
                       '以下是我的回答：', '以下是測試用回答：', '參考回答：',
                       '請在此輸入回答', '（待補）', 'sample answer:', '嗯，呃……'):
            with self.subTest(answer=answer):
                self.assertIsNotNone(no_content_reason(answer))

    def test_short_honest_or_off_topic_answers_go_to_relevance(self):
        for answer in ('SUM', '我負責收社費', '不知道', '我不會使用公式',
                       '今天晚餐吃麵', '測試回答範例：我使用 SUM 加總社費。',
                       '我先測試，再核對結果。', '我會先嗯一聲，再說明原因。'):
            with self.subTest(answer=answer):
                self.assertIsNone(no_content_reason(answer))

    def make(self):
        clock = Clock()
        services = Mock(wraps=Services(outside=True))
        session = InterviewSession(topics(), services, clock)
        session.start()
        return session, services, clock

    def test_label_reasks_without_models_or_question_count_then_recovers(self):
        session, services, clock = self.make()
        clock.advance(10)
        event = session.submit('測試回答範例：')
        self.assertEqual(event['question_kind'], 'restate')
        self.assertEqual(event['text'], '問題0')
        self.assertEqual(session.total_questions, 1)
        self.assertEqual(session.active['qa_history'], [])
        services.relevance.assert_not_called()
        services.assess.assert_not_called()
        services.followup.assert_not_called()
        self.assertFalse(any(row['kind'] == 'analysis' for row in session.log))
        self.assertEqual(session.log[-2]['relevance_computed'], False)
        session.submit('我主動協調團員並整理排練時間')
        self.assertEqual(services.relevance.call_count, 1)
        self.assertNotIn('測試回答範例', services.relevance.call_args.args[1])
        history = services.assess.call_args.args[1]
        self.assertEqual(len(history), 1)
        self.assertEqual(len([e for e in session.log if e['kind'] == 'answer']), 2)

    def test_second_placeholder_switches_with_shared_restate_limit(self):
        session, services, clock = self.make()
        session.submit('測試回答範例：')
        self.assertEqual(session.submit('待補')['topic_index'], 1)
        end = next(row for row in session.log if row['kind'] == 'topic_end')
        self.assertEqual(end['reason'], '重述一次後仍未實質作答')
        self.assertEqual(end['followups'], 0)
        services.assess.assert_not_called()

    def test_placeholder_on_followup_not_masked_by_previous_good_answer(self):
        session, services, clock = self.make()
        session.submit('我曾主動帶領團隊')
        services.reset_mock()
        event = session.submit('測試回答範例：')
        self.assertEqual(event['question_kind'], 'restate')
        self.assertEqual(session.active['followups'], 1)
        self.assertEqual(session.total_questions, 2)
        services.relevance.assert_not_called()
        services.followup.assert_not_called()

    def test_no_content_still_respects_time_and_question_limits(self):
        session, services, clock = self.make()
        clock.advance(181)
        self.assertEqual(session.submit('待補')['topic_index'], 1)
        services.relevance.assert_not_called()
        session, services, clock = self.make()
        session.total_questions = 15
        self.assertEqual(session.submit('待補')['kind'], 'finished')
        self.assertEqual(session.total_questions, 15)

    def test_empty_timeout_uses_same_restate_once(self):
        session, services, clock = self.make()
        clock.advance(90)
        self.assertEqual(session.submit('', timed_out=True)['question_kind'], 'restate')
        self.assertEqual(session.total_questions, 1)
        services.relevance.assert_not_called()


if __name__ == '__main__':
    unittest.main()
