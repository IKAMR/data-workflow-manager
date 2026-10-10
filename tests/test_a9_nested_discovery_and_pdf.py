import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

batch = load('tools/noark5_batch_overview_a6.py', 'a9_batch')
pdf = load('tools/report_outputs.py', 'a9_pdf')

class A9Tests(unittest.TestCase):
    def test_municipality_level_and_dwm_run_subfolder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for kommune, extraction, job in [('1535','1535_003','JOB-001'),('1502','1502_029','JOB-001')]:
                p = root / kommune / extraction / 'repository_operations' / 'dwm' / 'a01' / 'noark5_reports' / 'depot_validation' / (job+'__RUN-1')
                p.mkdir(parents=True)
                (p / 'depot_validation_report.json').write_text(json.dumps({'report_type':'noark5_depot_validation','archive_parts':[]}))
                payload = root / kommune / extraction / 'content' / 'sip' / 'content'
                payload.mkdir(parents=True)
                (payload / 'depot_validation_report.json').write_text('NOT A REPORT')
            found = batch.locate_reports(root)
            self.assertEqual(len(found), 2)
            self.assertTrue(all('repository_operations' in str(p) for p in found))

    def test_direct_extraction_and_legacy(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            p=root/'uttak'/'repository_operations'/'dwm'/'noark5_reports'/'JOB-002__RUN-1'
            p.mkdir(parents=True)
            (p/'depot_validation_report.json').write_text('{}')
            self.assertEqual(len(batch.locate_reports(root)), 1)

    def test_pdf_publish_copies_before_replace(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); source=root/'source.pdf'; dest=root/'folder'/'dest.pdf'
            dest.parent.mkdir();source.write_bytes(b'%PDF actual output')
            pdf._publish_pdf(source,dest)
            self.assertEqual(dest.read_bytes(),source.read_bytes())
            self.assertTrue(source.exists())
            self.assertFalse(list(dest.parent.glob('*.tmp.pdf')))

if __name__=='__main__':unittest.main()
