from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
import json

from gui.persistent_app_a26_2 import WorkflowApp


class V016A262ResultIdentityTests(unittest.TestCase):
    def _app(self, work: Path):
        app = object.__new__(WorkflowApp)
        app._expected_work_operations = lambda job: work
        app._path_exists = lambda path: Path(path).exists() if path else False
        return app

    def _job(self, work: Path, source: Path):
        return SimpleNamespace(
            work_operations=work,
            work_root=None,
            archive_root=None,
            output_root=None,
            source_root=None,
            source_extraction=source,
            active_extraction_root=source,
        )

    def _report(self, work: Path, run: str, source: str | None):
        folder = work / 'noark5_reports' / 'depot_validation' / run
        folder.mkdir(parents=True)
        report = folder / 'depot_validation_report.json'
        report.write_text('{}\n', encoding='utf-8')
        if source is not None:
            (folder / 'artifact_manifest.json').write_text(json.dumps({
                'schema_version': 2,
                'created_at': '2026-10-01T10:00:00+02:00',
                'operation_id': 'build_noark5_depot_report',
                'source_extraction': source,
            }), encoding='utf-8')
        return report

    def test_matching_source_report_is_reused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            work = root / 'repository_operations'
            source = root / 'content' / 'sip' / 'content' / 'one' / 'avleveringspakke'
            source.mkdir(parents=True)
            report = self._report(work, 'run-1', str(source))
            found, _, unavailable = self._app(work)._depot_report_for_job(self._job(work, source))
            self.assertEqual(found, report)
            self.assertIsNone(unavailable)

    def test_other_extraction_in_shared_work_is_not_reused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            work = root / 'repository_operations'
            source = root / 'content' / 'sip' / 'content' / 'one' / 'avleveringspakke'
            other = root / 'content' / 'sip' / 'content' / 'two' / 'avleveringspakke'
            source.mkdir(parents=True)
            other.mkdir(parents=True)
            self._report(work, 'run-2', str(other))
            found, _, unavailable = self._app(work)._depot_report_for_job(self._job(work, source))
            self.assertIsNone(found)
            self.assertIsNone(unavailable)

    def test_manifestless_legacy_report_is_not_claimed_for_job(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            work = root / 'repository_operations'
            source = root / 'content' / 'sip' / 'content' / 'one' / 'avleveringspakke'
            source.mkdir(parents=True)
            self._report(work, 'legacy', None)
            found, _, _ = self._app(work)._depot_report_for_job(self._job(work, source))
            self.assertIsNone(found)

    def test_main_activates_a26_2(self):
        main = (Path(__file__).resolve().parents[1] / 'main.py').read_text(encoding='utf-8')
        self.assertIn('from gui.persistent_app_a26_2 import run_gui', main)

    def test_version_is_a26_2(self):
        version = (Path(__file__).resolve().parents[1] / 'version.py').read_text(encoding='utf-8')
        self.assertRegex(version, r'VERSION\s*=\s*"0\.1\.6-a26(?:\.(?:[2-9]|[1-9]\d+))?"')


if __name__ == '__main__':
    unittest.main()
