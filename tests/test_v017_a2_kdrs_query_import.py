from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.external_evidence.kdrs_query import (
    KdrsQueryImportError,
    detect_report_type,
    import_kdrs_query_reports,
    load_kdrs_query_import,
    migrate_legacy_kdrs_query_storage,
)
from noark5_workflow.external_evidence.result_bank import build_external_result_bank
from noark5_workflow.core.job import Job
from noark5_workflow.core.work_paths import resolve_dwm_work_root, resolve_work_operations_base
from noark5_workflow.reporting.depot_metadata import (
    import_info_xml,
    load_depot_metadata,
    metadata_store_path,
    migrate_metadata_storage,
    save_depot_metadata,
)


STANDARD = """KDRS Query resultat
N5.04 Arkiv: 1
Tittel: Testarkiv
N5.11 Mapper pr. år:
2008: 3
2009: 4
N5.18 Registreringer pr. år (opprettet dato):
2008: 10
2009: 20
"""

U01 = """U1. N5.101 Konsentrert opptelling for hele Noark 5-uttrekket
N5.05/06 Arkivdeler: 2
N5.10/12/14 Mapper: 7; Sak: 7; Møte: 0
"""

U02 = """U2. N5.102 Konsentrert opptelling pr. arkivdel for hele Noark 5-uttrekket
Arkivdel 1: Del A
Beskrivelse: A
[.2] Mappe typer: Alle: 3
Arkivdel 2: Del B
Beskrivelse: B
[.2] Mappe typer: Alle: 4
"""


class V017A2KdrsQueryImportTests(unittest.TestCase):
    def _files(self, root: Path):
        standard = root / "sample-noark5-xpath-report.txt"
        u1 = root / "sample-noark5-xpath-report_U01.txt"
        u2 = root / "sample-noark5-xpath-report_U02.txt"
        standard.write_text(STANDARD, encoding="utf-8")
        u1.write_text(U01, encoding="utf-8")
        u2.write_text(U02, encoding="utf-8")
        return standard, u1, u2

    def test_detects_standard_u1_u2(self):
        with tempfile.TemporaryDirectory() as td:
            standard, u1, u2 = self._files(Path(td))
            self.assertEqual(detect_report_type(standard), "standard")
            self.assertEqual(detect_report_type(u1), "u01")
            self.assertEqual(detect_report_type(u2), "u02")

    def test_standard_prefers_original_legacy_test_when_catalog_point_is_shared(self):
        from noark5_workflow.external_evidence import kdrs_query as module

        by_job = {}
        by_point = {
            "N5.11": [
                {"legacy_job_id": "C09", "test_id": "kdrs.c09", "test_point": "N5.11"},
                {"legacy_job_id": "C09_R4", "test_id": "kdrs.c09_r4", "test_point": "N5.11"},
            ]
        }
        matched = module._match_catalog_row("N5.11 Mapper pr. år:", by_job, by_point)
        self.assertIsNotNone(matched)
        self.assertEqual(matched["test_id"], "kdrs.c09")

    def test_import_preserves_sources_and_normalizes_all_three(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            standard, u1, u2 = self._files(root)
            work = root / "work"
            manifest = import_kdrs_query_reports(
                (standard, u1, u2),
                work_operations=work,
                imported_by={"job_id": "JOB-002"},
            )

            self.assertEqual(manifest["report_types"], ["standard", "u01", "u02"])
            loaded = load_kdrs_query_import(work, manifest["import_id"])
            self.assertEqual(set(loaded["normalized"]), {"standard", "u01", "u02"})

            std = loaded["normalized"]["standard"]
            mapped = {row["test_id"] for row in std["sections"]}
            self.assertIn("kdrs.c01", mapped)
            self.assertIn("kdrs.c09", mapped)
            self.assertIn("kdrs.c16", mapped)

            u2_data = loaded["normalized"]["u02"]
            self.assertEqual(u2_data["summary"]["archive_part_count"], 2)
            self.assertEqual(u2_data["sections"][0]["archive_part_title"], "Del A")
            self.assertEqual(u2_data["sections"][1]["archive_part_title"], "Del B")

            effective_work = resolve_dwm_work_root(work)
            for row in manifest["files"]:
                preserved = effective_work / row["preserved_file"]
                self.assertTrue(preserved.is_file())
                self.assertTrue(row["sha256"])
            self.assertFalse((work / "external_evidence").exists())
            self.assertTrue((effective_work / "external_evidence").is_dir())


    def test_metadata_uses_configured_dwm_subfolder_and_reads_legacy_location(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            work = root / "repository_operations"
            work.mkdir(parents=True)
            job = Job("JOB-002", work_operations=work, name="test")
            effective = resolve_dwm_work_root(work)

            target = metadata_store_path(job)
            self.assertEqual(target, effective / "metadata" / "depot_metadata.json")
            payload = {
                "source_imports": [],
                "current": {"label": "Riktig DWM-plassering"},
                "review": {},
            }
            saved = save_depot_metadata(job, payload)
            self.assertEqual(saved, target)
            self.assertFalse((work / "metadata" / "depot_metadata.json").exists())

            # A short-lived a1/a2 bug wrote metadata directly below
            # repository_operations. It remains readable so operator edits are
            # not lost, while all subsequent saves go to the DWM folder.
            target.unlink()
            legacy = work / "metadata" / "depot_metadata.json"
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_text(
                json.dumps({
                    "file_type": "dwm-depot-metadata",
                    "format_version": 2,
                    "job_id": "JOB-002",
                    "current": {"label": "Legacy LABEL"},
                    "source_imports": [],
                    "review": {},
                }),
                encoding="utf-8",
            )
            self.assertEqual(load_depot_metadata(job)["current"]["label"], "Legacy LABEL")

    def test_reimport_migrates_short_lived_legacy_kdrs_location_into_effective_job_subfolder(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            standard, u1, u2 = self._files(root)
            base = root / "repository_operations"
            effective = base / "dwm" / "a01"
            legacy_import = base / "external_evidence" / "kdrs_query" / "legacy-one"
            legacy_import.mkdir(parents=True)
            (legacy_import / "marker.txt").write_text("legacy", encoding="utf-8")

            migration = migrate_legacy_kdrs_query_storage(
                work_operations=effective,
                legacy_work_operations=base,
            )
            self.assertEqual(migration["migrated_imports"], 1)

            import_kdrs_query_reports(
                (standard, u1, u2),
                work_operations=effective,
                legacy_work_operations=base,
            )

            self.assertEqual(
                (effective / "external_evidence" / "kdrs_query" / "legacy-one" / "marker.txt").read_text(encoding="utf-8"),
                "legacy",
            )
            self.assertFalse((effective / "dwm").exists())

    def test_u1_u2_ignore_echoed_query_definition_before_actual_output(self):
        from noark5_workflow.external_evidence.kdrs_query import normalize_kdrs_query_output

        u1_text = (
            'U01\nN5.101 definition\n"U1. N5.101 Konsentrert opptelling", " ",\n'
            'U1. N5.101 Konsentrert opptelling for hele Noark 5-uttrekket\n'
            'N5.05/06 Arkivdeler: 2\n'
        )
        u1 = normalize_kdrs_query_output(
            u1_text, report_type="u01", source_file="u1.txt",
            source_sha256="x", source_encoding="utf-8",
        )
        self.assertGreater(u1["summary"]["definition_line_count"], 0)
        self.assertTrue(u1["sections"][0]["raw_text"].startswith("U1. N5.101"))
        self.assertNotIn('"U1. N5.101', u1["sections"][0]["raw_text"])

        u2_text = (
            'U02\n"U2. N5.102 definition", " ",\n'
            'U2. N5.102 Konsentrert opptelling pr. arkivdel for hele Noark 5-uttrekket\n'
            'Arkivdel 1: Del A\nBeskrivelse: A\n'
            'Arkivdel 2: Del B\nBeskrivelse: B\n'
        )
        u2 = normalize_kdrs_query_output(
            u2_text, report_type="u02", source_file="u2.txt",
            source_sha256="y", source_encoding="utf-8",
        )
        self.assertEqual(u2["summary"]["archive_part_count"], 2)
        self.assertGreater(u2["summary"]["definition_line_count"], 0)
        self.assertEqual(u2["sections"][0]["archive_part_title"], "Del A")

    def test_result_bank_keeps_kdrs_query_as_external_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            standard, u1, u2 = self._files(root)
            work = root / "work"
            import_kdrs_query_reports((standard, u1, u2), work_operations=work)
            bank = build_external_result_bank(work)

            groups = [g for g in bank["groups"] if g["source_system"] == "KDRS Query"]
            self.assertEqual(len(groups), 1)
            self.assertGreaterEqual(groups[0]["summary"]["resources"], 5)
            for resource in groups[0]["resources"]:
                self.assertFalse(resource["authoritative_internal_master"])
                self.assertNotEqual(resource["relationship_to_internal"], "corroborates_internal")

    def test_rejects_two_files_of_same_report_type_in_one_import(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = root / "one.txt"
            second = root / "two.txt"
            first.write_text(STANDARD, encoding="utf-8")
            second.write_text(STANDARD, encoding="utf-8")
            with self.assertRaises(KdrsQueryImportError):
                import_kdrs_query_reports((first, second), work_operations=root / "work")

    def test_imported_info_xml_keeps_values_and_exact_source_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            job_root = root / "job"
            work = job_root / "repository_operations"
            work.mkdir(parents=True)
            source = root / "received" / "wrong_info.xml"
            source.parent.mkdir(parents=True)
            source.write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<mets:mets xmlns:mets="http://www.loc.gov/METS/" LABEL="Feil levert LABEL">\n'
                '  <mets:metsHdr><mets:metsDocumentID>info.xml</mets:metsDocumentID></mets:metsHdr>\n'
                '</mets:mets>\n',
                encoding="utf-8",
            )
            job = Job(
                "JOB-002", work_root=job_root, work_operations=work, name="test"
            )

            import_info_xml(job, source, overwrite_current=False, apply_current=True)
            payload = load_depot_metadata(job)
            self.assertEqual(payload["current"]["label"], "Feil levert LABEL")
            self.assertEqual(payload["source_imports"][0]["fields"]["label"], "Feil levert LABEL")

            effective = resolve_dwm_work_root(work)
            row = payload["source_imports"][0]
            preserved = effective / row["preserved_file"]
            manifest = effective / row["evidence_manifest"]
            self.assertTrue(preserved.is_file())
            self.assertEqual(preserved.read_bytes(), source.read_bytes())
            evidence = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(evidence["fields"]["label"], "Feil levert LABEL")
            self.assertEqual(evidence["sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(evidence["preservation_status"], "preserved")

    def test_legacy_metadata_migrates_non_destructively_with_source_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            job_root = root / "job"
            base = job_root / "repository_operations"
            effective = base / "dwm" / "a01"
            effective.mkdir(parents=True)
            source = root / "received" / "info.xml"
            source.parent.mkdir(parents=True)
            source.write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<mets:mets xmlns:mets="http://www.loc.gov/METS/" LABEL="Historisk LABEL">\n'
                '  <mets:metsHdr><mets:metsDocumentID>info.xml</mets:metsDocumentID></mets:metsHdr>\n'
                '</mets:mets>\n',
                encoding="utf-8",
            )
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            legacy = base / "metadata" / "depot_metadata.json"
            legacy.parent.mkdir(parents=True)
            legacy.write_text(
                json.dumps({
                    "file_type": "dwm-depot-metadata",
                    "format_version": 2,
                    "job_id": "JOB-002",
                    "source_imports": [{
                        "kind": "dias-mets",
                        "path": str(source),
                        "imported_at": "2026-10-07T11:02:10+02:00",
                        "size": source.stat().st_size,
                        "mtime_ns": source.stat().st_mtime_ns,
                        "sha256": digest,
                        "fields": {"label": "Historisk LABEL"},
                    }],
                    "current": {"label": "Korrigert depot-LABEL"},
                    "review": {},
                }),
                encoding="utf-8",
            )
            job = Job(
                "JOB-002", work_root=job_root, work_operations=effective, name="test"
            )

            self.assertEqual(resolve_work_operations_base(effective), base)
            result = migrate_metadata_storage(job)
            target = effective / "metadata" / "depot_metadata.json"
            self.assertTrue(result["migrated_legacy"])
            self.assertTrue(target.is_file())
            self.assertTrue(legacy.is_file())
            payload = load_depot_metadata(job)
            self.assertEqual(payload["current"]["label"], "Korrigert depot-LABEL")
            self.assertEqual(payload["source_imports"][0]["fields"]["label"], "Historisk LABEL")
            self.assertTrue((effective / payload["source_imports"][0]["preserved_file"]).is_file())

    def test_effective_job_subfolder_is_not_nested_with_another_dwm(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "repository_operations"
            effective = base / "dwm" / "a01"
            self.assertEqual(
                resolve_dwm_work_root(effective, settings={"app_work_subfolder": "dwm"}),
                effective,
            )
            self.assertEqual(
                resolve_work_operations_base(effective, settings={"app_work_subfolder": "dwm"}),
                base,
            )

    def test_metadata_editor_surfaces_preserved_source_evidence(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "gui"
            / "depot_metadata_editor_v017_a1.py"
        ).read_text(encoding="utf-8")
        self.assertIn("Evidensstatus:", source)
        self.assertIn("Bevart original:", source)
        self.assertIn("Evidensmanifest:", source)

    def test_gui_contract_exposes_kdrs_import_on_active_job_not_batch_dialog(self):
        import inspect
        from gui.job_batch_action_dialog_v017_a2 import V017A2JobBatchActionDialog
        from gui.jobs_window_v017_a2 import V017A2JobsWindow
        from gui.persistent_app_v017_a2 import WorkflowApp

        dialog_source = inspect.getsource(V017A2JobBatchActionDialog)
        jobs_source = inspect.getsource(V017A2JobsWindow)
        install_source = inspect.getsource(WorkflowApp._install_kdrs_query_header_button)
        app_source = inspect.getsource(WorkflowApp._v017_a2_import_kdrs_query)
        prepare_source = inspect.getsource(WorkflowApp._v017_a2_prepare_job_work_area)
        migrate_source = inspect.getsource(WorkflowApp._v017_a2_migrate_external_evidence)
        open_jobs_source = inspect.getsource(WorkflowApp._open_jobs)

        self.assertNotIn("KDRS Query", dialog_source)
        self.assertNotIn("on_import_kdrs_query", jobs_source)
        self.assertNotIn("on_import_kdrs_query", open_jobs_source)
        self.assertIn('text="KDRS Query"', install_source)
        self.assertIn("command=self._v017_a2_import_kdrs_query", install_source)
        self.assertIn("self.current_job", app_source)
        self.assertNotIn("len(selected)", app_source)
        self.assertIn("askopenfilenames", app_source)
        self.assertIn("import_kdrs_query_reports", app_source)
        self.assertIn("_apply_effective_work_operations", prepare_source)
        self.assertIn("migrate_legacy_kdrs_query_storage", migrate_source)
        self.assertIn("write_external_result_bank", migrate_source)


if __name__ == "__main__":
    unittest.main()
