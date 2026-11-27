"""Regression for failed-file counters and independent Arkade PRONOM import."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from noark5_workflow.analysis.siegfried_statistics import summarize_dwm_siegfried_statistics
from noark5_workflow.external_evidence.arkade5_pronom_standalone_v027_a20 import (
    import_preserved_pronom, verify_standalone_reference,
)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


class SiegfriedA20Tests(unittest.TestCase):
    def sample(self):
        return dict(evidence_type='dwm_siegfried_pronom_identification',
                    source_system='DWM / Siegfried', format_version=1,
                    files_total=748179, identified=745019, unidentified=3061,
                    ambiguous=0, files_failed=99, json_response_errors=957,
                    format_groups=[{'puid': 'fmt/354', 'count': 1}])

    def test_real_counter_shape(self):
        summary = summarize_dwm_siegfried_statistics(self.sample())
        self.assertEqual(summary['reported_failed_files'], 99)
        self.assertEqual(summary['reported_json_response_errors'], 957)
        self.assertFalse(summary['technical_validation_verified'])
        self.assertIsNone(summary['depot_approval'])

    def test_legacy_without_failed_counter(self):
        doc = self.sample()
        doc.pop('files_failed')
        doc['files_total'] -= 99
        self.assertEqual(summarize_dwm_siegfried_statistics(doc)['reported_failed_files'], 0)

    def test_wrong_total_still_rejected(self):
        doc = self.sample()
        doc['files_failed'] -= 1
        with self.assertRaises(ValueError):
            summarize_dwm_siegfried_statistics(doc)

    def test_invalid_error_counters_rejected(self):
        for key in ('files_failed', 'json_response_errors'):
            for value in (-1, True, '99'):
                doc = self.sample()
                doc[key] = value
                with self.assertRaises(ValueError):
                    summarize_dwm_siegfried_statistics(doc)


class ArkadeStandaloneA20Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.ids = {'job_id': 'JOB-001', 'job_uid': '00000000-0000-4000-8000-000000000001'}
        source = 'C:/example/source'
        self.output = self.root / 'arkade5_v2.13.1' / 'pronom'
        self.output.mkdir(parents=True)
        self.csv = self.output / 'filformatinfo-statistikk.csv'
        self.csv.write_text('Format-ID,Filtype,Formatversjon,RAF-220301,Antall\nfmt/354,PDF,1b,Gyldig,100\n', encoding='utf-8-sig')
        (self.output / 'filformatinfo').write_bytes(b'example inventory')
        job = {'file_type': 'dwm-work-job', 'job_uid': self.ids['job_uid'], 'job': {
            'job_id': self.ids['job_id'], 'source_extraction': source,
            'work_operations': str(self.root), 'workflow_ids': ['arkade5_pronom_analysis']}}
        (self.root / 'job.json').write_text(json.dumps(job), encoding='utf-8')
        run = 'JOB-001-pronom_analysis-20260101-000000-000001'
        self.run_dir = self.root / 'external_runs' / 'arkade5' / 'JOB-001' / 'pronom_analysis' / run
        self.run_dir.mkdir(parents=True)
        stdout = b'[Information] analyse successfully finished.\n'
        (self.run_dir / 'stdout.txt').write_bytes(stdout)
        (self.run_dir / 'stderr.txt').write_bytes(b'')
        self.manifest = self.run_dir / 'manifest.json'
        self.record = dict(tool_id='arkade5', operation_id='pronom_analysis', job_id='JOB-001',
                           run_id=run, ok=True, exit_code=0, cancelled=False, timed_out=False,
                           stdout={'sha256_utf8': _sha(stdout)}, stderr={'sha256_utf8': _sha(b'')},
                           metadata={'tool_version': '2.13.1', 'source_extraction': source,
                                     'work_operations': str(self.root), 'arkade_output_dir': str(self.output)})
        self.write_manifest()

    def write_manifest(self):
        self.manifest.write_text(json.dumps(self.record), encoding='utf-8')

    def test_independent_import_and_repeat(self):
        ref = import_preserved_pronom(self.root, **self.ids)
        self.assertIsNotNone(ref)
        self.assertEqual(ref, import_preserved_pronom(self.root, **self.ids))
        self.assertTrue(verify_standalone_reference(self.root, ref, **self.ids))
        model = json.loads((self.root / ref['file']).read_text(encoding='utf-8'))
        self.assertEqual(model['csv']['rows'][0]['Antall'], '100')
        self.assertFalse((self.root / 'external_evidence' / 'arkade5').exists())

    def test_missing_csv_does_not_create_fake_evidence(self):
        self.csv.unlink()
        self.assertIsNone(import_preserved_pronom(self.root, **self.ids))
        self.assertFalse((self.root / 'external_evidence').exists())

    def test_failed_cli_not_reused(self):
        self.record['ok'] = False
        self.write_manifest()
        self.assertIsNone(import_preserved_pronom(self.root, **self.ids))

    def test_mismatched_source_refused(self):
        self.record['metadata']['source_extraction'] = 'C:/other/source'
        self.write_manifest()
        with self.assertRaises(ValueError):
            import_preserved_pronom(self.root, **self.ids)

    def test_changed_log_refused(self):
        (self.run_dir / 'stdout.txt').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            import_preserved_pronom(self.root, **self.ids)

    def test_preserved_csv_tamper_refused(self):
        ref = import_preserved_pronom(self.root, **self.ids)
        manifest = json.loads((self.root / ref['manifest']).read_text(encoding='utf-8'))
        (self.root / manifest['source']['preserved_file']).write_bytes(b'changed')
        with self.assertRaises(ValueError):
            verify_standalone_reference(self.root, ref, **self.ids)


if __name__ == '__main__':
    unittest.main()
