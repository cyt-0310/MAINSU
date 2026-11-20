"""Text interview state machine for steps 6-12. Services are injected for testing."""
import math
import time
from bridge import validate_details
from interview_gap_detection.gap_detection import detect_gap
from interview_gap_detection.relevance import combine_with_llm

TOPIC_SECONDS = 240
# Fewer seconds than this left in a topic: skip restate/follow-up and move on.
MIN_TOPIC_SECONDS_TO_CONTINUE = 60


class InterviewSession:
    def __init__(self, topics, services, clock=time.monotonic):
        if not 2 <= len(topics) <= 3:
            raise ValueError('Require intro and 1-2 portfolio event topics')
        if topics[0]['type'] != '自我介紹' or any(t['type'] != '學習歷程' for t in topics[1:]):
            raise ValueError('Only intro and portfolio events are allowed')
        self.topics, self.services, self.clock = topics, services, clock
        self.started = clock()
        # Overall 20-minute clock also pauses while the program processes an answer.
        self.paused_at = None
        self.paused_total = 0.0
        self.index = -1
        self.total_questions = 0
        self.outside_followups = 0
        self.finished = False
        self.log = []
        self.active = None
        self.pending = None

    def elapsed(self):
        """Interview time = examiner asking + student answering; program processing is excluded."""
        now = self.paused_at if self.paused_at is not None else self.clock()
        return max(0, now - self.started - self.paused_total)

    def processing_seconds(self):
        """Total program processing time excluded from the 20-minute clock."""
        current = self.clock() - self.paused_at if self.paused_at is not None else 0
        return self.paused_total + max(0, current)

    def topic_elapsed(self):
        """Topic time = examiner asking + student answering. The clock pauses from answer submission
        until the next question is asked, so model/program processing is not counted."""
        now = self.active['paused_at'] if self.active['paused_at'] is not None else self.clock()
        return max(0, now - self.active['started'] - self.active['paused_total'])

    def _pause_topic_clock(self):
        if self.paused_at is None:
            self.paused_at = self.clock()
        if self.active['paused_at'] is None:
            self.active['paused_at'] = self.clock()

    def _resume_topic_clock(self):
        if self.paused_at is not None:
            self.paused_total += max(0, self.clock() - self.paused_at)
            self.paused_at = None
        if self.active['paused_at'] is not None:
            self.active['paused_total'] += max(0, self.clock() - self.active['paused_at'])
            self.active['paused_at'] = None

    def _topic_time_low(self):
        return TOPIC_SECONDS - self.topic_elapsed() < MIN_TOPIC_SECONDS_TO_CONTINUE

    def _log(self, kind, **values):
        self.log.append({'kind': kind, 'elapsed': round(self.elapsed(), 3), **values})

    def _finish(self, reason):
        self.finished = True
        self.pending = None
        self._log('interview_end', reason=reason, total_questions=self.total_questions,
                  processing_excluded=round(self.processing_seconds(), 3))
        return {'kind': 'finished', 'reason': reason}

    def _end_topic(self, reason):
        self._log('topic_end', topic_index=self.index, reason=reason,
                  followups=self.active['followups'], topic_elapsed=round(self.topic_elapsed(), 3),
                  processing_excluded=round(self.active['paused_total'] + (
                      self.clock() - self.active['paused_at'] if self.active['paused_at'] is not None else 0), 3),
                  details=self.active['details'])
        self.pending = None
        return self._next_topic()

    def _next_topic(self):
        if self.elapsed() >= 1200 or self.total_questions >= 15:
            return self._finish('全場時間或題數達上限')
        self.index += 1
        if self.index >= len(self.topics):
            return self._finish('所有主題已完成')
        self.active = {'started': self.clock(), 'followups': 0, 'rephrased': False,
                       'qa_history': [], 'details': None, 'not_applicable': None,
                       'paused_at': None, 'paused_total': 0.0}
        return self._ask(self.topics[self.index]['question'], 'main')

    def _ask(self, text, kind):
        # Asking the question (and the examiner reading it out) counts toward the topic's 4 minutes.
        self._resume_topic_clock()
        if kind != 'restate':
            self.total_questions += 1
        self.pending = {'kind': 'question', 'question_kind': kind, 'text': text,
                        'topic_index': self.index, 'asked_at': self.clock()}
        self._log('question', question_kind=kind, text=text, topic_index=self.index,
                  total_questions=self.total_questions)
        return self.pending

    def start(self):
        if self.active is not None or self.finished:
            raise RuntimeError('Interview has already started')
        self.started = self.clock()  # the 20 minutes start with the first question, not at setup
        return self._next_topic()

    def remaining_answer_seconds(self):
        if self.finished or self.pending is None:
            return 0
        limit = 90 if self.index == 0 else 120
        return max(0, min(limit - (self.clock()-self.pending['asked_at']),
                          TOPIC_SECONDS-self.topic_elapsed(), 1200-self.elapsed()))

    def submit(self, answer, timed_out=False):
        if self.finished or self.pending is None:
            raise RuntimeError('No pending question')
        if not isinstance(answer, str) or (not answer.strip() and not timed_out):
            raise ValueError('請輸入文字回答')
        topic = self.topics[self.index]
        answer_elapsed = self.clock() - self.pending['asked_at']
        # Answer submitted: stop the topic and overall clocks while the program analyzes / generates the next question.
        self._pause_topic_clock()
        limit = 90 if self.index == 0 else 120
        timed_out = timed_out or answer_elapsed >= limit
        self._log('answer', topic_index=self.index, question=self.pending['text'],
                  answer=answer, answer_elapsed=round(answer_elapsed, 3), timed_out=timed_out,
                  submitted_by='timeout' if timed_out else 'enter')
        self.active['qa_history'].append((self.pending['text'], answer))
        if self.elapsed() >= 1200:
            self._log('topic_end', topic_index=self.index, reason='全場時間達上限')
            return self._finish('全場時間達 20 分鐘')
        # Low topic time no longer skips analysis: the answer is still scored and added to the
        # topic's cumulative completeness; only restate/follow-up is skipped afterwards.
        if timed_out and not answer.strip():
            # No answer counts as relevance 0: same once-per-topic restatement as an off-topic answer.
            self._log('no_answer', topic_index=self.index, question=self.pending['text'],
                      question_kind=self.pending['question_kind'], relevance_score=0)
            if self._topic_time_low():
                return self._end_topic(f'本主題剩餘不足 {MIN_TOPIC_SECONDS_TO_CONTINUE} 秒，直接換題')
            if self.active['rephrased']:
                return self._end_topic('重述一次後仍未作答')
            self.active['rephrased'] = True
            return self._ask(self.pending['text'], 'restate')
        # Relevance is per question: this question's text against this answer only.
        # Bi-Encoder + Cross-Encoder give the score; the LLM judgement (same assess call) fixes the level band.
        relevance = self.services.relevance(self.pending['text'], answer)
        assessment = self.services.assess(topic, self.active['qa_history'])
        validate_details(assessment['details'])
        relevance = combine_with_llm(relevance, assessment.get('relevance_judgement'))
        score = relevance['relevance_score']
        if not isinstance(score, (int, float)) or not math.isfinite(score):
            raise ValueError('Invalid relevance score')
        gap = detect_gap(assessment['details'], self.active['details'],
                         self.active['followups'], 1 if self.index == 0 else 2,
                         self.total_questions, self.elapsed(), self.topic_elapsed(),
                         assessment.get('not_applicable'), self.active['not_applicable'])
        self.active['details'] = gap['details']
        self.active['not_applicable'] = gap['not_applicable']
        self._log('analysis', topic_index=self.index, question=self.pending['text'],
                  question_kind=self.pending['question_kind'], relevance=relevance,
                  relevance_status=relevance['relevance_status'],
                  assessment=assessment, gap=gap)
        # Overall/time limits precede relevance and completeness decisions.
        if gap['decision'] == 'end_interview':
            self._log('topic_end', topic_index=self.index, reason=gap['reason'])
            return self._finish(gap['reason'])
        if self._topic_time_low():
            return self._end_topic(f'本主題剩餘不足 {MIN_TOPIC_SECONDS_TO_CONTINUE} 秒，直接換題')
        if score < .4:
            if self.active['rephrased']:
                return self._end_topic('重述一次後本題回答相關度仍低於 0.4')
            self.active['rephrased'] = True
            return self._ask(self.pending['text'], 'restate')
        if gap['decision'] == 'switch_topic':
            return self._end_topic(gap['reason'])
        allow_outside = self.outside_followups < 1
        if self.index == 0 and (not assessment.get('mentions_outside_portfolio') or not allow_outside):
            return self._end_topic('自介沒有可追問的備審外重要內容')
        followup = self.services.followup(topic, self.active['qa_history'], gap, allow_outside)
        outside = followup['targets_outside_portfolio']
        if (outside and not allow_outside) or (self.index == 0 and not outside):
            return self._end_topic('生成追問不符合備審外內容限制')
        # Model latency is excluded from both the topic clock and the 20-minute overall clock (both paused).
        if self.elapsed() >= 1200:
            return self._finish('全場時間達 20 分鐘')
        if self._topic_time_low():
            return self._end_topic(f'本主題剩餘不足 {MIN_TOPIC_SECONDS_TO_CONTINUE} 秒，直接換題')
        self.active['followups'] += 1
        self.outside_followups += int(outside)
        self._log('followup_reason', topic_index=self.index, **followup)
        return self._ask(followup['follow_up_question'], 'followup')

    def relevance_summary(self):
        """Final relevance: every question scored on its own (unanswered = 0), averaged per topic,
        then the topic averages are averaged for the whole interview."""
        per_topic, completeness = {}, {}
        for entry in self.log:
            if entry['kind'] == 'analysis':
                score = entry['relevance']['relevance_score']
                completeness[entry['topic_index']] = entry['gap']['scores']
            elif entry['kind'] == 'no_answer':
                score = 0.0
            else:
                continue
            per_topic.setdefault(entry['topic_index'], []).append(
                {'question_kind': entry.get('question_kind'), 'question': entry.get('question'),
                 'relevance_score': round(score, 3)})
        # Completeness is cumulative, so each topic's last analysis is its final value (None if never analyzed).
        topics = [{'topic_index': i, 'type': self.topics[i]['type'], 'questions': questions,
                   'relevance_score': round(sum(q['relevance_score'] for q in questions) / len(questions), 3),
                   'completeness': completeness.get(i)}
                  for i, questions in sorted(per_topic.items())]
        overall = round(sum(t['relevance_score'] for t in topics) / len(topics), 3) if topics else None
        return {'method': 'mean_of_question_scores_per_topic', 'topics': topics, 'overall': overall}

    def snapshot(self):
        return {'schema_version': 1, 'scope': 'steps_2_to_12_text_only',
                'finished': self.finished, 'elapsed': round(self.elapsed(), 3),
                'processing_excluded': round(self.processing_seconds(), 3),
                'total_questions': self.total_questions, 'topics': self.topics,
                'relevance_summary': self.relevance_summary(), 'log': self.log}
