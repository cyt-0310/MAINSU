import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import web_portfolios as web


class PortfolioReuseTests(unittest.TestCase):
    def test_reuploads_reference_original_and_retry_does_not_delete(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(web, 'DATA', Path(temp)), patch.object(web, 'queue_analysis'), patch.object(web.pdfium, 'PdfDocument') as pdf:
                pdf.return_value.__enter__.return_value.__len__.return_value = 1
                first = web.save_submission('A', 'Dept', [('statement', 'first.pdf', b'%PDF-example', None)])
                next_record = web.save_submission('B', 'Dept', [('statement', 'second.pdf', b'%PDF-example', None)])
                directory = web.path_for(next_record['id'])
                file = next_record['files'][0]
                self.assertEqual(file['source']['portfolio'], first['id'])
                self.assertFalse((directory / '1.pdf').exists())
                self.assertEqual(web.document_path(directory, file).read_bytes(), b'%PDF-example')
                self.assertEqual(web.portfolio_record(directory)['status'], 'failed')
                self.assertTrue(web.document_path(directory, file).exists())
