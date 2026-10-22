"""a20.7: report-level evidence status is visible, no invented totals."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from noark5_workflow.reporting.report_service_a20 import (
    _recovered_source_rows, write_report_package,
)
from test_a20_report_service import make_payload, fake_legacy, opts


class RecoverySourcesTest(unittest.TestCase):
    def _recovered_jobs(self):
        def job(no, **state):
            return SimpleNamespace(job_id=f'JOB-{no:03d}',name=f'1535_{no:03d} ephorte',
                operation_params={'__dwm_report_recovery__':{'report_only':True,
                  'evidence':['DWM depotrapport'] if no==1 else ['KDRS Query (eldre kildefiler)'],
                  'source_job_id':'JOB-001',**state}})
        return (job(1,report_file='/g/1535_001/report.json'),job(2,report_file=''))

    def test_evidence_roles_are_separate_from_unknown_counts(self):
        rows=_recovered_source_rows(self._recovered_jobs())
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['basis'],'Lagret DWM-depotrapport')
        self.assertIn('antall ukjent',rows[1]['basis'])
        self.assertEqual(rows[1]['evidence'],['KDRS Query (eldre kildefiler)'])

    def test_html_and_json_show_recovery_sources(self):
        jobs=self._recovered_jobs()
        payload=make_payload(2,missing={2})
        with tempfile.TemporaryDirectory() as tmp:
            write_report_package(tmp,jobs,opts(),formats=('html','json'),
                                 _legacy_export=fake_legacy(payload))
            html=(Path(tmp)/'index.html').read_text('utf8')
            structured=json.loads((Path(tmp)/'index.json').read_text('utf8'))
            self.assertIn('Gjenfunne rapportjobber',html)
            self.assertIn('Uten komplett DWM-depotrapport',html)
            self.assertIn('KDRS Query (eldre kildefiler)',html)
            self.assertEqual(len(structured['report_recovery_sources']),2)
            self.assertIsNone(structured['a20_report_snapshot']['jobs'][1]['counts']['folder_count'])


if __name__=='__main__':
    unittest.main()
