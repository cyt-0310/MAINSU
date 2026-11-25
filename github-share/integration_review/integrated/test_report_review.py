import unittest
from unittest.mock import patch
from report_review import evaluate, QuestionReview, ReviewBatch, question_details


class ReportReviewTests(unittest.TestCase):
    def test_followup_history_preserves_real_scores_and_reason(self):
        record = {'snapshot': {'log': [
            {'kind':'question','question_kind':'main','topic_index':0},
            {'kind':'answer','topic_index':0},
            {'kind':'analysis','gap':{'scores':{'trait':40,'depth':60,'exp':70},'gaps':['trait'],'target_gap':'trait'}},
            {'kind':'followup_reason','topic_index':0,'follow_up_reason':'Ask for a concrete action.'},
            {'kind':'question','question_kind':'followup','topic_index':0},
            {'kind':'answer','topic_index':0},
            {'kind':'analysis','gap':{'scores':{'trait':75,'depth':60,'exp':70},'gaps':[]}},
            {'kind':'question','question_kind':'main','topic_index':1},
            {'kind':'answer','topic_index':1},
        ]}}
        rows = question_details(record)
        self.assertEqual(rows[0]['analysisScores']['trait'], 40)
        self.assertEqual(rows[0]['targetGap'], 'trait')
        self.assertEqual(rows[1]['followupReason'], 'Ask for a concrete action.')
        self.assertEqual(rows[1]['analysisScores']['trait'], 75)
        self.assertNotIn('analysisScores', rows[2])
        self.assertNotIn('followupReason', rows[2])

    def test_review_uses_individual_answers_and_verified_evidence(self):
        record = {'answers': [{'question':'why', 'text':'I used a spreadsheet.'}, {'question':'how', 'text':'I sorted records.'}], 'snapshot': {'log': [
            {'kind':'question','question_kind':'main'}, {'kind':'answer','topic_index':0},
            {'kind':'analysis','assessment':{'retrieved_evidence':[{'text':'used a spreadsheet','page':2}]}},
            {'kind':'question','question_kind':'followup'}, {'kind':'answer','topic_index':0},
            {'kind':'analysis','assessment':{'retrieved_evidence':[]}}]}}
        self.assertEqual([x['kind'] for x in question_details(record)], ['main','followup'])
        supplied = ReviewBatch(reviews=[QuestionReview(number=1,relevance=85,relevant_evidence="used a spreadsheet",consistency_status='matched',consistency_quote='used a spreadsheet',answer_quote='used a spreadsheet',advice='Explain which formulas.'), QuestionReview(number=2,relevance=70,relevant_evidence="sorted records",consistency_status='matched',consistency_quote='invented',answer_quote='sorted records',advice='Describe sorting criteria.')])
        with patch('report_review.call_llm', return_value=supplied):
            result = evaluate(record)['questions']
        self.assertEqual(result[0]['relevance'],85)
        self.assertEqual(result[0]['consistency'],100)
        self.assertIsNone(result[1]['consistency'])
        self.assertEqual(result[1]['consistencyStatus'],'pending')

    def test_non_answer_is_not_sent_to_model(self):
        record={'answers':[{'question':'why','text':''}],'snapshot':{'log':[]}}
        with patch('report_review.call_llm') as llm:
            result=evaluate(record)['questions'][0]
        llm.assert_not_called()
        self.assertIsNone(result['relevance'])

    def test_partial_review_resumes_without_repeating_completed_questions(self):
        record={'answers':[{'question':'why','text':'I used a spreadsheet.'} for _ in range(4)], 'snapshot':{'log':[]}}
        def result(number):
            return QuestionReview(number=number,relevance=80,relevant_evidence='spreadsheet',consistency_status='not_applicable',consistency_quote='',answer_quote='',advice='Explain a concrete example.')
        checkpoints=[]
        with patch('report_review.call_llm',side_effect=[ReviewBatch(reviews=[result(i) for i in (1,2,3)]),RuntimeError('unavailable')]):
            with self.assertRaises(RuntimeError):
                evaluate(record,checkpoint=checkpoints.append)
        self.assertEqual(len(checkpoints[0]['questions']),3)
        self.assertFalse(checkpoints[0]['complete'])
        with patch('report_review.call_llm',return_value=ReviewBatch(reviews=[result(4)])) as llm:
            final=evaluate(record,previous=checkpoints[0])
        llm.assert_called_once()
        self.assertTrue(final['complete'])
        self.assertEqual(len(final['questions']),4)
