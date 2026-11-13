"""Stable extract labels, also for Windows paths on non-Windows CI."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from app.noark_extract_display_v0114_a7 import extract_display_name


class ExtractNameTest(unittest.TestCase):
    def test_job_label_preferred(self):
        self.assertEqual('1525_004', extract_display_name('1525_004 | 2025-acos'))

    def test_generic_name_read_work_job_name(self):
        with TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / 'job.json').write_text(json.dumps({'job': {'name':'1525_004 | E-1525-2025-0001'}}),encoding='utf-8')
            report = work / 'noark5_reports' / 'depot_validation' / 'report.json'
            self.assertEqual('1525_004', extract_display_name('content', report))

    def test_windows_source_fallback_not_last_content(self):
        with TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / 'job.json').write_text(json.dumps({'job': {'name':'content','source_extraction':r'I:\arkiv-noark5\1525\1525_004_E-1525-2025-0001\content\sip\content'}}),encoding='utf-8')
            self.assertEqual('1525_004', extract_display_name('content',work/'reports'/'report.json'))

    def test_path_fallback_from_report(self):
        report=Path('/data/1525_004_E-1525-2025-0001/repository_operations/dwm/noark5_reports/report.json')
        self.assertEqual('1525_004',extract_display_name('content', report))

    def test_unknown_does_not_invent_id(self):
        self.assertEqual('content', extract_display_name('content',Path('/tmp/no-matching-code/report.json')))

if __name__=='__main__':
    unittest.main()
