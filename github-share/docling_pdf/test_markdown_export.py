import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import parse_pdf


class MarkdownExportTests(unittest.TestCase):
    def test_parse_writes_event_content_before_full_text(self):
        units = [
            dict(id='cover', page=1, type='text', text='課程介紹', block_ids=['b1']),
            dict(id='project', page=2, type='text', text='| 欄位 | 值 |\n| --- | --- |\n| 成果 | 網站 |',
                 block_ids=['b2'], text_method='encoding_fallback_ocr'),
            dict(id='footer', page=2, type='page_footer', text='頁尾文字', block_ids=['b3']),
        ]
        events = [
            dict(id='event_0001', title='程式課程', type='course_portfolio', pages=[1], all_pages=[1, 2],
                 source_unit_ids=['cover'], child_event_ids=['event_0002']),
            dict(id='event_0002', title='網站製作', type='project', pages=[2],
                 source_unit_ids=['project'], parent_event_id='event_0001', quality_flags=['source_requires_review']),
        ]
        document = dict(blocks=[{}], reading_units=units, events=events, warnings=[])
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / 'portfolio.pdf'
            pdf.write_bytes(b'%PDF-test')
            output = Path(directory) / 'parsed'
            with patch.object(parse_pdf, 'convert_docling', return_value={'pages': {}, 'body': {}}), \
                 patch.object(parse_pdf, 'refine_events', return_value=document), \
                 patch.object(parse_pdf, 'recover_encoding', side_effect=lambda d, *a, **kw: d), \
                 patch.object(parse_pdf, 'segment_events', side_effect=lambda d: d), \
                 patch.object(parse_pdf.importlib.metadata, 'version', return_value='test'):
                self.assertEqual(parse_pdf.main([str(pdf), '--output', str(output)]), 0)
            self.assertEqual(len(list(output.iterdir())), 3)
            md = (output / 'portfolio.md').read_text(encoding='utf-8')
        self.assertTrue(md.startswith('# 事件切分索引\n'))
        event_section, original = md.split('# 原文解析', 1)
        parent_section, child_section = event_section.split('## event_0002：網站製作', 1)
        self.assertNotIn('成果 | 網站', parent_section)
        self.assertIn('所屬課程：event_0001：程式課程', child_section)
        self.assertIn('來源 PDF 頁碼：2', child_section)
        self.assertIn('局部 OCR', child_section)
        self.assertIn('| 成果 | 網站 |', child_section)
        self.assertNotIn('頁尾文字', event_section)
        self.assertIn('頁尾文字', original)
        self.assertIn('| --- | --- | --- | --- |\n| event_0001', md)

    def test_empty_events_keeps_original_text(self):
        unit = dict(id='u1', page=1, type='text', text='未歸入事件的原文', block_ids=['b1'])
        md = parse_pdf.export_md([unit], [])
        self.assertTrue(md.startswith('# 事件切分索引\n'))
        self.assertIn('尚無足夠依據', md)
        self.assertIn('未歸入事件的原文', md)


if __name__ == '__main__':
    unittest.main()
