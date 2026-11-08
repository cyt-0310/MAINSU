import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from results_summary import build_summary, render_summary
from interview_session import InterviewSession
from test_text_pipeline import Clock, Services, topics


def snapshot():
    return {'topics': topics(), 'finished': True, 'total_questions': 3, 'elapsed': 80, 'log': [
        {'kind': 'question', 'topic_index': 0, 'question_kind': 'main'},
        {'kind': 'answer', 'topic_index': 0, 'answer_elapsed': 10, 'timed_out': False},
        {'kind': 'analysis', 'topic_index': 0,
         'relevance': {'relevance_score': .4}, 'relevance_status': '可能離題',
         'gap': {'scores': {'trait': 20, 'depth': 25, 'exp': 30}, 'gaps': ['trait', 'depth', 'exp']},
         'assessment': {'consistency_issues': [{'issue_type': '角色差異', 'source_verified': True}]}},
        {'kind': 'question', 'topic_index': 0, 'question_kind': 'followup'},
        {'kind': 'analysis', 'topic_index': 0,
         'relevance': {'relevance_score': .65}, 'relevance_status': '切題',
         'gap': {'scores': {'trait': 55, 'depth': 60, 'exp': 80}, 'gaps': []},
         'assessment': {'reasoning': '補充了具體行動',
                        'consistency_issues': [{'issue_type': '角色差異', 'source_verified': True,
                                                'portfolio_evidence': '組員', 'answer_evidence': '統籌全案',
                                                'portfolio_sources': [{'page': 2}], 'answer_sources': [{'turn': 2}]}]}},
        {'kind': 'topic_end', 'topic_index': 0, 'reason': '三項達標'},
        {'kind': 'question', 'topic_index': 1, 'question_kind': 'main'},
        {'kind': 'interview_end', 'reason': '全場時間達上限'},
    ]}


class SummaryTests(unittest.TestCase):
    def test_latest_cumulative_analysis_not_sum_or_average(self):
        summary = build_summary(snapshot())
        first = summary['topics'][0]
        self.assertEqual(first['scores']['trait'], 55)
        self.assertTrue(first['is_all_passed'])
        self.assertEqual(first['relevance_score'], .65)
        self.assertEqual(first['followup_count'], 1)
        self.assertEqual(len(first['consistency_issues']), 1)
        self.assertEqual(summary['assessed_topic_count'], 1)

    def test_unassessed_is_none_and_does_not_pass(self):
        summary = build_summary(snapshot())
        for row in summary['topics'][1:]:
            self.assertIsNone(row['scores'])
            self.assertIsNone(row['is_all_passed'])
        self.assertEqual(summary['topics'][1]['status'], 'not_assessed')
        self.assertEqual(summary['topics'][2]['status'], 'not_started')

    def test_render_contains_threshold_gaps_and_source_citations(self):
        text = render_summary(snapshot())
        for expected in ('55%', '個人特質 55%', '深度邏輯 60%', '經驗內容 80%', '未評估', 'PDF頁 [2]', '輪次 [2]'):
            self.assertIn(expected, text)
        self.assertIn('待核對', text)

    def test_interrupted_and_empty_session(self):
        summary = build_summary({'topics': topics(), 'log': [], 'finished': False})
        self.assertEqual(summary['assessed_topic_count'], 0)
        self.assertIn('已中斷', render_summary({'topics': topics(), 'log': [], 'finished': False}))

    def test_session_snapshot_persists_summary(self):
        session = InterviewSession(topics(), Services(value=1), Clock())
        session.start()
        session.submit('實際回答')
        self.assertEqual(session.snapshot()['summary']['topics'][0]['scores']['trait'], 100)

    def test_one_dynamic_followup_round_reaches_final_summary(self):
        services = Services(value=1)
        session = InterviewSession(topics(), services, Clock())
        session.start()
        session.submit('自我介紹回答')
        services.value = 0
        followup = session.submit('事件主問題回答')
        self.assertEqual(followup['question_kind'], 'followup')
        services.value = 1
        session.submit('補充具體行動及反思')
        session.submit('最後一個事件的完整回答')
        self.assertTrue(session.finished)
        summary = session.snapshot()['summary']
        self.assertEqual(summary['topics'][1]['followup_count'], 1)
        self.assertEqual(summary['topics'][1]['scores']['depth'], 100)
        self.assertEqual(summary['assessed_topic_count'], 3)

    def test_saved_session_command_requires_no_key_or_api(self):
        here = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(dir=here) as folder:
            source, target = Path(folder)/'session.json', Path(folder)/'summary.md'
            source.write_text(json.dumps(snapshot()), encoding='utf-8')
            process = subprocess.run([sys.executable, str(here/'run_text_interview.py'), 'summary', str(source), '--output', str(target)],
                                     capture_output=True)
            self.assertEqual(process.returncode, 0, process.stderr.decode(errors='replace'))
            self.assertIn('個人特質 55%', target.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
