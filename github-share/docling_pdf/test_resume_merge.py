import unittest
from parse_pdf import segment_events


def document(briefs, narrative):
    rows = [(1, 'section_header', '個人簡歷', 30)]
    rows.extend((1, 'list_item', title, 100 + i * 40) for i, title in enumerate(briefs))
    rows.extend([(2, 'section_header', '主動學習', 30),
                 (2, 'text', narrative, 150)])
    units = [dict(id=f'u{i}', page=p, type=kind, text=text, bbox=[60, y, 500, y + 20],
                  block_ids=[f'b{i}']) for i, (p, kind, text, y) in enumerate(rows)]
    return dict(reading_units=units, blocks=[dict(id=f'b{i}') for i in range(len(rows))],
                pages=[dict(page=p, width=600, height=800) for p in (1, 2)])


class ResumeMergeTests(unittest.TestCase):
    narrative = '在高二擔任社團總務之前，我未曾使用試算表，我上網自學公式，用於管理社費及製作出席紀錄。'

    def test_resume_and_narrative_merge_with_all_provenance(self):
        data = segment_events(document(['高二上、下學期手語社總務'], self.narrative))
        self.assertEqual(len(data['events']), 1)
        event = data['events'][0]
        self.assertEqual(event['pages'], [1, 2])
        self.assertIn('管理社費', event['text'])
        self.assertEqual(event['title'], '高二上、下學期手語社總務')
        self.assertTrue(event['merge_evidence'][0]['confirmation_required'])
        self.assertNotIn('brief_resume_item', event['quality_flags'])
        for uid in event['source_unit_ids']:
            self.assertEqual(data['event_assignments'][uid]['event_id'], event['id'])

    def test_same_role_different_school_year_stays_separate(self):
        data = segment_events(document(['高一手語社總務'], self.narrative))
        self.assertEqual(len(data['events']), 2)

    def test_two_clubs_in_same_year_are_ambiguous(self):
        data = segment_events(document(['高二手語社總務', '高二攝影社總務'], self.narrative))
        self.assertEqual(len(data['events']), 3)

    def test_explicit_club_resolves_ambiguity(self):
        narrative = self.narrative.replace('社團總務', '手語社總務')
        data = segment_events(document(['高二手語社總務', '高二攝影社總務'], narrative))
        self.assertEqual(len(data['events']), 2)
        target = next(e for e in data['events'] if '手語社' in e['title'])
        self.assertEqual(target['pages'], [1, 2])
        other = next(e for e in data['events'] if '攝影社' in e['title'])
        self.assertEqual(other['pages'], [1])

    def test_explicit_different_club_does_not_merge(self):
        data = segment_events(document(['高二攝影社總務'], self.narrative.replace('社團總務', '手語社總務')))
        self.assertEqual(len(data['events']), 2)

    def test_different_roles_do_not_merge(self):
        data = segment_events(document(['高二手語社團社長'], self.narrative))
        self.assertEqual(len(data['events']), 2)

    def test_role_alone_without_period_or_club_does_not_merge(self):
        data = segment_events(document(['高二手語社總務'], self.narrative.replace('高二', '當時')))
        self.assertEqual(len(data['events']), 2)


if __name__ == '__main__':
    unittest.main()
