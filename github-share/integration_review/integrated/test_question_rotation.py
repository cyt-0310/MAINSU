import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import web_interviews as web
from question_rotation import rotate_questions, portfolio_identity, ANGLES
from test_text_pipeline import topics

class RotationTests(unittest.TestCase):
    def test_four_consecutive_plans_and_resume(self):
        with TemporaryDirectory() as temp:
            directory=Path(temp)
            (directory/'prepared').mkdir()
            web.write_json(directory/'prepared'/'topics.json', topics())
            web.write_json(directory/'submission.json', {})
            with patch.object(web,'ROOT',directory/'sessions'), patch.object(web,'path_for',return_value=directory), patch.object(web,'portfolio_record',return_value={'status':'ready'}):
                payload={'school':'Test','department':'Test','mode':'text'}
                plans=[]
                for _ in range(5):
                    result=web.start(payload)
                    record=web.read_json(web.file_for(result['id']))
                    plan=record['snapshot']['topics']
                    for previous in plans[-3:]:
                        self.assertEqual(plan[0]['question'], previous[0]['question'])
                        for new,old in zip(plan[1:],previous[1:]):
                            self.assertNotEqual(new['question'],old['question'])
                            self.assertNotEqual(new['question_angle'],old['question_angle'])
                    plans.append(plan)
                    self.assertEqual(web.resume_or_start(payload)['id'],result['id'])
                self.assertEqual(plans[0][1]['question_angle'],plans[4][1]['question_angle'])

    def test_legacy_question_angle_not_repeated(self):
        original=topics()
        original[1]['question']='請說明曾遇到什麼困難，以及如何克服？'
        history=[{'snapshot':{'topics':original}}]
        selected=rotate_questions(original,history,'Test')
        self.assertNotEqual(selected[1]['question_angle'],'challenge')
        self.assertEqual(selected[0],original[0])

if __name__=='__main__':
    unittest.main()
