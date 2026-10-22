"""a20.5: scanning follows municipal/extraction/repository_operations/dwm/b03 layouts."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.reporting.report_job_recovery_a204 import (
    discover_report_jobs, RecoveryError,
)


def saved_depot_report(dwm: Path, *, job_id: str='JOB-001',
                       manifest_source: str | None='G:/arkiv-noark5/1535/1535_005_source') -> Path:
    run=dwm/'noark5_reports'/'depot_validation'/f'{job_id}__RUN-20261012-234738-example'
    run.mkdir(parents=True,exist_ok=True)
    (run/'depot_validation_report.json').write_text(
        json.dumps({'summary': {'folder_count': 72}, 'archive_parts': []}), encoding='utf-8')
    if manifest_source is not None:
        (run/'artifact_manifest.json').write_text(json.dumps({
            'job_id':job_id,'source_extraction': manifest_source}), encoding='utf-8')
    return run


class DeepRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'arkiv-noark5'
        self.root.mkdir()

    def test_k18_nine_extractions_one_dwm_depot_report(self):
        extraction_names=(
            '1535_003_E-Docu-2025-0001_AIC-10',
            '1535_005_E-Docu-2025-0001_AIC-9',
            '1539_007_E-Docu-2025-0001_AIC-11',
            '1543_010_E-Docu-2025-0001_AIC-4',
            '1543_012_E-Docu-2025-0001_AIC-5',
            '1545_005_E-Docu-2025-0001_AIC-3',
            '1547_003_E-Docu-2025-0001_AIC-6',
            '1547_005_E-Docu-2025-0001_AIC-7',
            '1547_007-E-Docu-2025-0001_AIC-8',
        )
        for name in extraction_names:
            (self.root/name[:4]/name/'repository_operations').mkdir(parents=True)
            (self.root/name[:4]/name/'content'/'sip'/'content').mkdir(parents=True)
        dwm=self.root/'1535'/extraction_names[1]/'repository_operations'/'dwm'/'b03'
        saved_depot_report(dwm)
        (self.root/'K18_v0.1.4-a8_a-nnn.n5jobs').write_text('{}',encoding='utf-8')
        (self.root/'1535'/extraction_names[0]/'repository_operations'/
         '1535_003_v0.1.7-a14-a2_dwm.zip').write_bytes(b'zip inventory placeholder')
        progress=[]
        plan=discover_report_jobs(self.root,on_progress=progress.append)
        self.assertEqual(len(plan.extraction_folders),9)
        self.assertEqual(len(plan.jobs),1)
        self.assertEqual(len(plan.missing_report_extractions),8)
        self.assertEqual(plan.jobs[0].job_id,'JOB-001')
        self.assertEqual(plan.jobs[0].work_operations,dwm)
        self.assertEqual(plan.existing_job_lists,
                         (self.root/'K18_v0.1.4-a8_a-nnn.n5jobs',))
        self.assertEqual(len(plan.archived_dwm_zips),1)
        self.assertTrue(progress and 'Ferdig' in progress[-1])

    def test_evidence_subtree_not_used_as_work_root(self):
        base=self.root/'1535'/'1535_005_collection'/'repository_operations'/'dwm'
        saved_depot_report(base/'b03')
        # A false report inside a source payload must not be visited.
        saved_depot_report(self.root/'1539'/'1539_007_collection'/'content'/'sip'/'dwm',job_id='JOB-999')
        plan=discover_report_jobs(self.root)
        self.assertEqual(len(plan.jobs),1)
        self.assertEqual(plan.jobs[0].job_id,'JOB-001')
        self.assertEqual(plan.jobs[0].work_operations,base/'b03')

    def test_dwm_or_repo_selected_directly(self):
        work=self.root/'1535'/'1535_005_test'/'repository_operations'
        saved_depot_report(work/'dwm'/'b03')
        for chosen in (work,work/'dwm',work/'dwm'/'b03',
                       work/'dwm'/'b03'/'noark5_reports'/'depot_validation'):
            with self.subTest(chosen=chosen):
                plan=discover_report_jobs(chosen)
                self.assertEqual(len(plan.jobs),1)

    def test_no_manifest_fallback_uses_extraction_folder_without_false_verification(self):
        work=self.root/'1535'/'1535_005_E-Docu-2025-0001_AIC-9'/'repository_operations'/'dwm'/'b03'
        saved_depot_report(work,manifest_source=None)
        plan=discover_report_jobs(self.root)
        self.assertEqual(plan.jobs[0].name,
                         '1535_005_E-Docu-2025-0001_AIC-9 – gjenfunnet depotrapport')
        self.assertFalse(plan.jobs[0].manifest_verified)

    def test_cannot_recover_from_only_old_kdrs_texts(self):
        extraction=self.root/'1539'/'1539_007_E-Docu-2025-0001_AIC-11'
        (extraction/'repository_operations'/'analyse').mkdir(parents=True)
        (extraction/'repository_operations'/'analyse'/'1539_007_noark5-xpath-report.txt').write_text(
            'Historical KDRS Query only',encoding='utf-8')
        with self.assertRaisesRegex(RecoveryError,'Ingen lagrede depotrapporter'):
            discover_report_jobs(self.root)

    def test_duplicate_local_job_ids_still_rejected(self):
        saved_depot_report(self.root/'1535'/'1535_005_A'/'repository_operations'/'dwm'/'b03')
        saved_depot_report(self.root/'1547'/'1547_007_A'/'repository_operations'/'dwm'/'b03')
        with self.assertRaisesRegex(RecoveryError,'flere arbeidsområder'):
            discover_report_jobs(self.root)

    def test_gui_has_progress_and_missing_archive_explanation(self):
        file=Path(__file__).resolve().parents[1]/'gui'/'jobs_window_v017_a2.py'
        text=file.read_text(encoding='utf-8')
        self.assertIn("results.put(('progress', message))",text)
        self.assertIn('missing_report_extractions',text)
        self.assertIn('existing_job_lists',text)


if __name__ == '__main__':
    unittest.main()
