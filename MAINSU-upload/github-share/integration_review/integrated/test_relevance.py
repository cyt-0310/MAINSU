import unittest
from interview_gap_detection.relevance import (
    calibrate_vector, soften_cross, copy_ratio, combine_with_llm, split_sentences,
)
from interview_session import InterviewSession
from test_text_pipeline import Clock, Services, topics


class RelevanceMathTests(unittest.TestCase):
    def test_vector_calibration_clips_to_unit_range(self):
        self.assertEqual(calibrate_vector(0.1), 0.0)
        self.assertEqual(calibrate_vector(0.9), 1.0)
        self.assertAlmostEqual(calibrate_vector(0.375), 0.5)

    def test_cross_sigmoid_applied_once_with_temperature(self):
        self.assertAlmostEqual(soften_cross(0), 0.5)
        # One sigmoid only: strong logits reach near 0/1 instead of being squashed to 0.5~0.73.
        self.assertGreater(soften_cross(10), 0.9)
        self.assertLess(soften_cross(-10), 0.1)
        self.assertTrue(0.2 < soften_cross(-2.6) < 0.4)

    def test_copy_ratio_flags_copied_question(self):
        q = '請說明你在校園專題「智慧點名系統」中負責的工作，以及遇到最大的困難是什麼？'
        self.assertGreaterEqual(copy_ratio(q, '我在校園專題智慧點名系統中負責的工作以及遇到最大的困難。'), 0.5)
        self.assertLess(copy_ratio(q, '我負責後端，最大困難是辨識準確率不高。'), 0.5)

    def test_split_sentences(self):
        self.assertEqual(split_sentences('甲。乙！丙'), ['甲。', '乙！', '丙'])
        self.assertEqual(split_sentences('沒有標點'), ['沒有標點'])


class LLMCombineTests(unittest.TestCase):
    base = {'relevance_score': 0.3, 'vector_score': 0.5, 'cross_score': 0.1}

    def test_llm_relevant_lifts_low_model_score_into_band(self):
        r = combine_with_llm(self.base, {'label': 'relevant', 'reason': '有具體回答'})
        self.assertEqual((r['relevance_score'], r['level'], r['model_score']), (0.6, 'relevant', 0.3))

    def test_model_score_keeps_position_inside_band(self):
        r = combine_with_llm(dict(self.base, relevance_score=0.85), {'label': 'relevant', 'reason': ''})
        self.assertEqual(r['relevance_score'], 0.85)

    def test_off_topic_caps_score(self):
        r = combine_with_llm(dict(self.base, relevance_score=0.95), {'label': 'off_topic', 'reason': '照抄題目'})
        self.assertEqual((r['relevance_score'], r['level']), (0.399, 'off_topic'))

    def test_partial_band(self):
        r = combine_with_llm(dict(self.base, relevance_score=0.9), {'label': 'partial', 'reason': ''})
        self.assertEqual(r['level'], 'partial')

    def test_without_llm_uses_models(self):
        r = combine_with_llm(self.base, None)
        self.assertEqual((r['relevance_score'], r['method']), (0.3, 'models_only'))


class LLMJudgementSessionTests(unittest.TestCase):
    def test_llm_judgement_overrides_level_in_session(self):
        services = Services(scores=[.9, .9], value=0.5)
        original = services.assess
        services.assess = lambda topic, history: dict(original(topic, history),
                                                      relevance_judgement={'label': 'off_topic', 'reason': '照抄'})
        s = InterviewSession(topics(), services, Clock())
        s.start()
        event = s.submit('照抄題目')
        self.assertEqual(event['question_kind'], 'restate')
        analysis = [e for e in s.log if e['kind'] == 'analysis'][-1]
        self.assertEqual(analysis['relevance']['relevance_score'], 0.399)
        self.assertEqual(analysis['relevance']['model_score'], 0.9)



class NotApplicableTests(unittest.TestCase):
    def details(self, role=0.0):
        return {'star': {'why_score': 1, 'how_score': .75, 'what_score': .75, 'role_score': role, 'action_score': .75},
                'ask': {'skill_score': .5, 'attitude_score': .5, 'knowledge_score': .5},
                'gibbs': {'reflection_score': 0, 'challenge_score': 0}}

    def test_not_applicable_item_leaves_denominator(self):
        from interview_gap_detection.gap_detection import compute_completeness
        self.assertEqual(compute_completeness(self.details())['exp'], 65.0)
        self.assertEqual(compute_completeness(self.details(), ['role_score'])['exp'], 81.2)

    def test_whole_group_not_applicable_is_still_scored(self):
        from interview_gap_detection.gap_detection import compute_completeness
        self.assertEqual(compute_completeness(self.details(), ['reflection_score', 'challenge_score'])['depth'], 0.0)

    def test_not_applicable_must_hold_every_round_and_have_no_score(self):
        from interview_gap_detection.gap_detection import merge_not_applicable
        d = self.details()
        self.assertEqual(merge_not_applicable(['role_score'], None, d), ['role_score'])
        # A later round judging it applicable restores scoring for the rest of the topic.
        self.assertEqual(merge_not_applicable([], ['role_score'], d), [])
        # Any score > 0 means it is applicable.
        self.assertEqual(merge_not_applicable(['role_score'], None, self.details(role=.5)), [])

    def test_session_tracks_not_applicable_per_topic(self):
        services = Services(value=0.5)
        original = services.assess
        def assess(topic, history):
            result = original(topic, history)
            result['details']['star']['role_score'] = 0  # not applicable -> LLM fills 0
            return dict(result, not_applicable=['role_score'])
        services.assess = assess
        s = InterviewSession(topics(), services, Clock())
        s.start()
        s.submit('自介', timed_out=True)
        s.submit('自介', timed_out=True)
        s.submit('主問回答')
        self.assertEqual(s.active['not_applicable'], ['role_score'])
        gap = [e for e in s.log if e['kind'] == 'analysis'][-1]['gap']
        self.assertEqual(gap['scores']['exp'], 50.0)  # 2.0 / 4, role excluded (would be 40% / 5)
        self.assertEqual(gap['not_applicable'], ['role_score'])



class SingleGapFollowupTests(unittest.TestCase):
    def details(self):
        return {'star': {'why_score': 1, 'how_score': .5, 'what_score': .25, 'role_score': 0, 'action_score': .5},
                'ask': {'skill_score': .5, 'attitude_score': .25, 'knowledge_score': .25},
                'gibbs': {'reflection_score': .5, 'challenge_score': .5}}

    def test_picks_single_lowest_item(self):
        from interview_gap_detection.gap_detection import pick_target_item
        self.assertEqual(pick_target_item(self.details(), 'exp'), 'role_score')
        # Not-applicable items are never targeted.
        self.assertEqual(pick_target_item(self.details(), 'exp', ['role_score']), 'what_score')
        # Ties follow fixed order: attitude before knowledge.
        self.assertEqual(pick_target_item(self.details(), 'trait'), 'attitude_score')

    def test_hidden_items_span_fields_lowest_first(self):
        from interview_gap_detection.gap_detection import pick_hidden_items
        # gaps sorted lowest field first: trait (ASK) then depth (Gibbs) then exp (STAR)
        hidden = pick_hidden_items(self.details(), ['trait', 'depth', 'exp'], limit=3)
        self.assertEqual(hidden[0], {'field': 'trait', 'item': 'attitude_score'})  # primary gap always first
        self.assertEqual([h['item'] for h in hidden[1:]], ['role_score', 'knowledge_score'])
        self.assertEqual(len(pick_hidden_items(self.details(), ['trait', 'exp'], ['role_score'], limit=5)), 5)

    def test_hidden_items_skip_not_applicable_and_specific_items(self):
        from interview_gap_detection.gap_detection import pick_hidden_items
        hidden = pick_hidden_items(self.details(), ['exp'], ['role_score'], limit=10)
        # why=1.0 already specific -> never hidden; role not applicable -> never hidden
        self.assertEqual([h['item'] for h in hidden], ['what_score', 'how_score', 'action_score'])

    def test_detect_gap_returns_hidden_items(self):
        from interview_gap_detection.gap_detection import detect_gap
        gap = detect_gap(self.details(), None, 0, 2, 2, 0, 0)
        self.assertEqual((gap['decision'], gap['target_gap'], gap['target_item']), ('follow_up', 'trait', 'attitude_score'))
        self.assertEqual(len(gap['hidden_items']), 3)
        self.assertIn('暗藏', gap['reason'])

    def test_followup_prompt_lists_hidden_items(self):
        from unittest import mock
        from interview_gap_detection import followup
        from interview_gap_detection.gap_detection import detect_gap
        gap = detect_gap(self.details(), None, 0, 2, 2, 0, 0)
        topic = {'type': '學習歷程', 'event': '專題', 'source': '備審'}
        with mock.patch.object(followup, 'call_llm') as call:
            followup.generate_followup(topic, [('問', '答')], gap, {'full_text': ''}, True)
        prompt = call.call_args[0][0]
        self.assertIn('1. 個人特質›態度', prompt)
        self.assertIn('← 主要缺口', prompt)
        self.assertIn('經驗內容›角色', prompt)
        self.assertIn('只能有一個問句、一個問號', prompt)



class TopicClockTests(unittest.TestCase):
    def slow_session(self, latency):
        """Services that take `latency` seconds per model call (relevance, assess, followup)."""
        clock = Clock()
        services = Services(value=0)
        for name in ('relevance', 'assess', 'followup'):
            original = getattr(services, name)
            def slow(*args, _f=original):
                clock.advance(latency)
                return _f(*args)
            setattr(services, name, slow)
        s = InterviewSession(topics(), services, clock)
        s.start()
        s.submit('', timed_out=True)
        s.submit('', timed_out=True)       # intro unanswered twice (no model calls) -> topic 1 main question
        assert s.index == 1 and s.pending['question_kind'] == 'main'
        return s, clock

    def test_processing_time_not_counted_in_topic(self):
        s, clock = self.slow_session(latency=30)
        clock.advance(40)                      # asking + answering: 40 s
        event = s.submit('主問回答')          # 3 model calls x 30 s = 90 s processing
        self.assertEqual(event['question_kind'], 'followup')
        self.assertEqual(s.topic_elapsed(), 40)
        clock.advance(25)                      # reading the follow-up + answering
        self.assertEqual(s.topic_elapsed(), 65)
        self.assertEqual(s.remaining_answer_seconds(), 95)   # 120 s answer limit - 25

    def test_heavy_processing_does_not_end_topic(self):
        # Old behaviour: 3 x 70 s processing would push the topic past 4 minutes and skip follow-up.
        s, clock = self.slow_session(latency=70)
        clock.advance(30)
        self.assertEqual(s.submit('主問回答')['question_kind'], 'followup')
        self.assertEqual(s.topic_elapsed(), 30)

    def test_topic_end_logs_excluded_processing(self):
        s, clock = self.slow_session(latency=10)
        clock.advance(230)
        s.submit('主問回答')                   # 230 s used -> under 60 s left -> analyzed, then switch
        end = [e for e in s.log if e['kind'] == 'topic_end'][-1]
        self.assertEqual((end['topic_elapsed'], end['processing_excluded']), (230, 20))


    def test_processing_time_not_counted_in_overall_20_minutes(self):
        s, clock = self.slow_session(latency=30)
        clock.advance(40)
        s.submit('主問回答')                   # 90 s processing
        self.assertEqual(s.elapsed(), 40)
        self.assertEqual(s.processing_seconds(), 90)
        clock.advance(10)
        self.assertEqual(s.elapsed(), 50)
        self.assertEqual(s.snapshot()['processing_excluded'], 90)

    def test_heavy_processing_does_not_end_interview(self):
        # 3 x 500 s of processing would exceed 20 minutes of wall time; interview must continue.
        s, clock = self.slow_session(latency=500)
        clock.advance(30)
        event = s.submit('主問回答')
        self.assertFalse(s.finished)
        self.assertEqual(event['question_kind'], 'followup')
        self.assertEqual(s.elapsed(), 30)

    def test_twenty_minutes_of_asking_and_answering_still_ends(self):
        s, clock = self.slow_session(latency=1)
        clock.advance(1200)
        self.assertEqual(s.submit('主問回答')['kind'], 'finished')


if __name__ == '__main__':
    unittest.main()
