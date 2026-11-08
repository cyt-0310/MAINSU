"""Text interview state machine for steps 6-12. Services are injected for testing."""
import math
import time
from bridge import validate_details
from interview_gap_detection.gap_detection import detect_gap


class InterviewSession:
    def __init__(self, topics, services, clock=time.monotonic):
        if not 2 <= len(topics) <= 3:
            raise ValueError('Require intro and 1-2 portfolio event topics')
        if topics[0]['type'] != '自我介紹' or any(t['type'] != '學習歷程' for t in topics[1:]):
            raise ValueError('Only intro and portfolio events are allowed')
        self.topics, self.services, self.clock = topics, services, clock
        self.started = clock()
        self.index = -1
        self.total_questions = 0
        self.outside_followups = 0
        self.finished = False
        self.log = []
        self.active = None
        self.pending = None

    def elapsed(self):
        return max(0, self.clock() - self.started)

    def topic_elapsed(self):
        return max(0, self.clock() - self.active['started'])

    def _log(self, kind, **values):
        self.log.append({'kind': kind, 'elapsed': round(self.elapsed(), 3), **values})

    def _finish(self, reason):
        self.finished = True
        self.pending = None
        self._log('interview_end', reason=reason, total_questions=self.total_questions)
        return {'kind': 'finished', 'reason': reason}

    def _end_topic(self, reason):
        self._log('topic_end', topic_index=self.index, reason=reason,
                  followups=self.active['followups'], topic_elapsed=round(self.topic_elapsed(), 3),
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
                       'qa_history': [], 'details': None}
        return self._ask(self.topics[self.index]['question'], 'main')

    def _ask(self, text, kind):
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
        return self._next_topic()

    def remaining_answer_seconds(self):
        if self.finished or self.pending is None:
            return 0
        limit = 90 if self.index == 0 else 120
        return max(0, min(limit - (self.clock()-self.pending['asked_at']),
                          240-self.topic_elapsed(), 1200-self.elapsed()))

    def submit(self, answer, timed_out=False):
        if self.finished or self.pending is None:
            raise RuntimeError('No pending question')
        if not isinstance(answer, str) or (not answer.strip() and not timed_out):
            raise ValueError('請輸入文字回答')
        topic = self.topics[self.index]
        answer_elapsed = self.clock() - self.pending['asked_at']
        limit = 90 if self.index == 0 else 120
        timed_out = timed_out or answer_elapsed >= limit
        self._log('answer', topic_index=self.index, question=self.pending['text'],
                  answer=answer, answer_elapsed=round(answer_elapsed, 3), timed_out=timed_out,
                  submitted_by='timeout' if timed_out else 'enter')
        self.active['qa_history'].append((self.pending['text'], answer))
        if self.elapsed() >= 1200:
            self._log('topic_end', topic_index=self.index, reason='全場時間達上限')
            return self._finish('全場時間達 20 分鐘')
        if self.topic_elapsed() >= 240:
            return self._end_topic('本主題時間達 4 分鐘')
        if timed_out and not answer.strip():
            return self._end_topic('單題超時且未提交文字')
        # Relevance is against the main topic question, using every answer in this topic.
        relevance = self.services.relevance(topic['question'], '\n'.join(a for _, a in self.active['qa_history']))
        score = relevance['relevance_score']
        if not isinstance(score, (int, float)) or not math.isfinite(score):
            raise ValueError('Invalid relevance score')
        assessment = self.services.assess(topic, self.active['qa_history'])
        validate_details(assessment['details'])
        gap = detect_gap(assessment['details'], self.active['details'],
                         self.active['followups'], 1 if self.index == 0 else 2,
                         self.total_questions, self.elapsed(), self.topic_elapsed())
        self.active['details'] = gap['details']
        self._log('analysis', topic_index=self.index, relevance=relevance,
                  relevance_status='切題' if score >= .6 else ('可能離題' if score >= .4 else '離題'),
                  assessment=assessment, gap=gap)
        # Overall/time limits precede relevance and completeness decisions.
        if gap['decision'] == 'end_interview':
            self._log('topic_end', topic_index=self.index, reason=gap['reason'])
            return self._finish(gap['reason'])
        if self.topic_elapsed() >= 240:
            return self._end_topic('本主題時間達 4 分鐘')
        if score < .4:
            if self.active['rephrased']:
                return self._end_topic('重述一次後累積回答相關度仍低於 0.4')
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
        # Model latency counts toward topic and overall clocks.
        if self.elapsed() >= 1200:
            return self._finish('全場時間達 20 分鐘')
        if self.topic_elapsed() >= 240:
            return self._end_topic('本主題時間達 4 分鐘')
        self.active['followups'] += 1
        self.outside_followups += int(outside)
        self._log('followup_reason', topic_index=self.index, **followup)
        return self._ask(followup['follow_up_question'], 'followup')

    def snapshot(self):
        from results_summary import build_summary
        snapshot = {'schema_version': 1, 'scope': 'steps_2_to_12_text_only',
                'finished': self.finished, 'elapsed': round(self.elapsed(), 3),
                'total_questions': self.total_questions, 'topics': self.topics, 'log': self.log}
        snapshot['summary'] = build_summary(snapshot)
        return snapshot
