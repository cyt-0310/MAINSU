import copy
import json
from pathlib import Path
import tempfile
import unittest
from bridge import load_portfolio_events
from evidence import EvidenceIndex, chunks_for, event_records
from interview_session import InterviewSession

ROOT = Path(__file__).resolve().parents[2]


class Clock:
    value = 0
    def __call__(self):
        return self.value
    def advance(self, seconds):
        self.value += seconds


def details(value):
    from bridge import FIELDS
    return {g: {k: value for k in keys} for g, keys in FIELDS.items()}


def topics():
    return [{'type': kind, 'question': f'問題{i}', 'event': f'事件{i}', 'event_id': None if i == 0 else f'e{i}'}
            for i, kind in enumerate(['自我介紹', '學習歷程', '學習歷程'])]


class Services:
    def __init__(self, scores=(.7,), value=0, outside=False):
        self.scores = iter(scores)
        self.value, self.outside = value, outside
        self.histories = []
        self.questions = []

    def relevance(self, question, answer):
        self.questions.append(question)
        return {'relevance_score': next(self.scores, .7)}

    def assess(self, topic, history):
        self.histories.append(copy.deepcopy(history))
        return {'details': details(self.value), 'mentions_outside_portfolio': self.outside,
                'consistency_issues': []}

    def followup(self, topic, history, gap, allow_outside):
        return {'targets_outside_portfolio': self.outside and allow_outside,
                'follow_up_question': '請具體說明你的行動？', 'follow_up_reason': '補足行動缺口'}


class FakeEmbedder:
    model_name = 'deterministic-test-only'
    def encode(self, texts):
        return [[float('角色' in text), float('反思' in text), 1.] for text in texts]


class TimedServices(Services):
    def __init__(self):
        super().__init__()
        self.followup_calls = 0
        self.latency = 0
        self.clock = None

    def followup(self, *args):
        self.followup_calls += 1
        self.clock.advance(self.latency)
        return super().followup(*args)


class SessionTests(unittest.TestCase):
    def make(self, services):
        clock = Clock()
        session = InterviewSession(topics(), services, clock)
        session.start()
        return session, clock

    def test_restate_once_without_count_and_then_switch(self):
        services = Services([.39, .39])
        s, _ = self.make(services)
        event = s.submit('回答一')
        self.assertEqual(event['question_kind'], 'restate')
        self.assertEqual(s.total_questions, 1)
        self.assertEqual(s.active['followups'], 0)
        event = s.submit('回答二')
        self.assertEqual(event['topic_index'], 1)
        self.assertEqual(s.total_questions, 2)
        self.assertEqual(len(services.histories[-1]), 2)
        self.assertTrue(any('仍低於' in e.get('reason', '') for e in s.log))

    def test_exact_point_four_allows_followup(self):
        s, _ = self.make(Services([.4], outside=True))
        event = s.submit('重要備審外經歷')
        self.assertEqual(event['question_kind'], 'followup')
        self.assertEqual(s.total_questions, 2)

    def test_recovered_restatement_can_followup(self):
        s, _ = self.make(Services([.1, .6], outside=True))
        s.submit('第一個回答')
        self.assertEqual(s.submit('補充回答')['question_kind'], 'followup')
        self.assertEqual(s.total_questions, 2)

    def test_intro_one_followup_only(self):
        s, _ = self.make(Services(outside=True))
        s.submit('重要備審外內容')
        event = s.submit('追問回答')
        self.assertEqual(event['topic_index'], 1)
        self.assertEqual(s.outside_followups, 1)
        self.assertIsNone(s.active['details'])
        self.assertEqual(s.active['qa_history'], [])

    def test_intro_without_outside_moves_on(self):
        s, _ = self.make(Services())
        self.assertEqual(s.submit('備審內自介')['topic_index'], 1)

    def test_general_two_followups_and_topic_reset(self):
        services = Services()
        s, _ = self.make(services)
        s.submit('自介')
        self.assertEqual(s.submit('主問回答')['question_kind'], 'followup')
        self.assertEqual(s.submit('追問一回答')['question_kind'], 'followup')
        self.assertEqual(s.submit('追問二回答')['topic_index'], 2)
        self.assertTrue(all(q == '問題1' for q in services.questions[1:]))

    def timed_general(self):
        services = TimedServices()
        session, clock = self.make(services)
        services.clock = clock
        session.submit('自介')
        return session, clock, services

    def test_under_sixty_seconds_skips_generation_without_using_followup(self):
        s, clock, services = self.timed_general()
        clock.advance(181)
        event = s.submit('回答')
        self.assertEqual(event['topic_index'], 2)
        self.assertEqual(services.followup_calls, 0)
        end = [e for e in s.log if e['kind'] == 'topic_end' and e['topic_index'] == 1][-1]
        self.assertIn('不足 60 秒', end['reason'])
        self.assertEqual(end['followups'], 0)
        self.assertEqual(s.total_questions, 3)  # intro, event 1 main, event 2 main

    def test_exactly_sixty_seconds_allows_followup(self):
        s, clock, services = self.timed_general()
        clock.advance(180)
        self.assertEqual(s.submit('回答')['question_kind'], 'followup')
        self.assertEqual(services.followup_calls, 1)
        self.assertEqual(s.remaining_answer_seconds(), 60)

    def test_generation_latency_can_cancel_followup_before_it_is_counted(self):
        s, clock, services = self.timed_general()
        clock.advance(170)
        services.latency = 11
        event = s.submit('回答')
        self.assertEqual(event['topic_index'], 2)
        self.assertEqual(services.followup_calls, 1)
        self.assertEqual(s.total_questions, 3)
        self.assertFalse(any(e['kind'] == 'question' and e['question_kind'] == 'followup' for e in s.log))

    def test_stops_after_one_followup_when_remaining_time_is_short(self):
        s, clock, services = self.timed_general()
        clock.advance(110)
        self.assertEqual(s.submit('主問題回答')['question_kind'], 'followup')
        clock.advance(71)
        self.assertEqual(s.submit('第一次追問回答')['topic_index'], 2)
        self.assertEqual(services.followup_calls, 1)
        end = [e for e in s.log if e['kind'] == 'topic_end' and e['topic_index'] == 1][-1]
        self.assertEqual(end['followups'], 1)

    def test_insufficient_overall_time_ends_interview_before_generation(self):
        s, clock, services = self.timed_general()
        clock.advance(1141)
        s.active['started'] = clock()
        s.pending['asked_at'] = clock()
        self.assertEqual(s.submit('回答')['kind'], 'finished')
        self.assertEqual(services.followup_calls, 0)
        self.assertIn('全場剩餘時間不足 60 秒', s.log[-1]['reason'])

    def test_complete_topic_switches_not_followup(self):
        s, _ = self.make(Services(value=1))
        self.assertEqual(s.submit('完整回答')['topic_index'], 1)

    def test_global_time_precedes_restate(self):
        s, clock = self.make(Services([.1]))
        clock.advance(1200)
        self.assertEqual(s.submit('回答')['kind'], 'finished')
        self.assertEqual(s.total_questions, 1)

    def test_fifteenth_question_has_no_restatement(self):
        s, _ = self.make(Services([.1]))
        s.total_questions = 15
        self.assertEqual(s.submit('回答')['kind'], 'finished')

    def test_topic_timeout_and_empty_answer_timeout(self):
        s, clock = self.make(Services())
        clock.advance(240)
        self.assertEqual(s.submit('已超時回答')['topic_index'], 1)
        self.assertEqual(s.submit('', timed_out=True)['question_kind'], 'restate')
        self.assertEqual(s.submit('', timed_out=True)['topic_index'], 2)

    def test_restate_does_not_reset_topic_clock(self):
        s, clock = self.make(Services([.1]))
        clock.advance(80)
        s.submit('離題回答')
        self.assertEqual(s.active['started'], 0)
        self.assertEqual(s.remaining_answer_seconds(), 90)

    def test_no_common_topics(self):
        bank = topics()
        bank[1]['type'] = '科系常見題'
        with self.assertRaises(ValueError):
            InterviewSession(bank, Services())


class EvidenceTests(unittest.TestCase):
    def test_real_portfolios_keep_source_hierarchy(self):
        if not (ROOT/'docling_pdf'/'results').exists():
            self.skipTest('Private PDF results are intentionally excluded from shared source')
        for path in (ROOT/'docling_pdf'/'results').glob('*/*.events.json'):
            portfolio = load_portfolio_events(path)
            records = event_records(portfolio)
            raw = {e['id']: e for e in portfolio['events']}
            self.assertTrue(records)
            for record in records:
                self.assertEqual(record['parent_event_id'], raw[record['event_id']].get('parent_event_id'))
                self.assertTrue(all(u['id'] and u['page'] for u in record['evidence']))
            index = EvidenceIndex(chunks_for(records), FakeEmbedder())
            found = index.search('角色', [records[-1]['event_id']])
            self.assertTrue(any(c['event_id'] == records[-1]['event_id'] for c in found))
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
                filename = Path(folder)/'index.json'
                index.save(filename)
                restored = EvidenceIndex.load(filename, FakeEmbedder())
                self.assertEqual(found, restored.search('角色', [records[-1]['event_id']]))
                data = json.loads(filename.read_text(encoding='utf-8'))
                data['chunks'][0]['text'] = 'changed'
                filename.write_text(json.dumps(data), encoding='utf-8')
                with self.assertRaises(ValueError):
                    EvidenceIndex.load(filename, FakeEmbedder())


if __name__ == '__main__':
    unittest.main()
