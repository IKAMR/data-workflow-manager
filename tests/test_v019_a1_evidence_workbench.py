"""v0.1.9-a1: source provenance, verified coverage and safe export contracts."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from app.evidence_workbench_v019_a1 import (
    CoverageRow, SourceRow, arkade_coverage, export_inventory, source_inventory,
)


def _shot(root: Path, *, uid="fixed-uuid", label="Uttrekk", depot=True):
    work = root / "work"
    work.mkdir(parents=True, exist_ok=True)
    report_file = work / "noark5_reports" / "depot.json"
    report_file.parent.mkdir(exist_ok=True)
    report_file.write_text("{}", encoding="utf-8")
    report = {"technical_validation": {"status": "completed_with_findings", "tests": [
        {"test_id": "dwm-1", "status": "ok"}, {"test_id": "dwm-2", "status": "warning"},
    ]}} if depot else None
    return SimpleNamespace(
        job=SimpleNamespace(job_uid=uid, job_id="JOB-001", name=label, work=work),
        results=SimpleNamespace(depot_report_path=report_file), depot=report,
    )


def _providers(work: Path, *, missing_pronom_count=False):
    a = work / "external_evidence" / "arkade5" / "IMP-1" / "normalized" / "arkade5_results.json"
    a.parent.mkdir(parents=True, exist_ok=True)
    a.write_text('{"tests": []}', encoding="utf-8")
    p = a.with_name("pronom_statistics.json")
    p.write_text("{}", encoding="utf-8")
    k = work / "external_evidence" / "kdrs_query" / "K-1" / "manifest.json"
    k.parent.mkdir(parents=True, exist_ok=True)
    k.write_text("{}", encoding="utf-8")
    return {
        "technical": lambda shots: (),
        "arkade": lambda shots: (
            {"import_id": "IMP-1", "errors": 2, "status": "fail", "file": a,
             "source_sha256": "sha-a"},
            {"import_id": "IMP-1", "errors": 0, "status": "ok", "file": a,
             "source_sha256": "sha-a"},
        ),
        "pronom": lambda shots: (
            {"import_id": "IMP-1", "count": 14, "file": p, "source_sha256": "sha-p"},
            {"import_id": "IMP-1", "count": None if missing_pronom_count else 4,
             "file": p, "source_sha256": "sha-p"},
        ),
        "kdrs": lambda shots: (
            {"import_id": "K-1", "report_type": "Standard", "sha256": "source-1", "file": k},
            {"import_id": "K-1", "report_type": "U1", "sha256": "source-2", "file": k},
        ),
        "reports": lambda shots: (
            {"filename": "resultat.html", "file": shots[0].results.depot_report_path},
        ),
    }


class EvidenceWorkbenchV019A1Tests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.shot = _shot(self.root)
        self.providers = _providers(self.shot.job.work)

    def _read_json(self, work, relative):
        try:
            return json.loads((Path(work) / relative).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def test_inventory_never_combines_native_and_external_observations(self):
        rows = source_inventory((self.shot,), readers=self.providers)
        self.assertEqual(len(rows), 5)
        self.assertEqual([r.source for r in rows], [
            "DWM – tekniske kontroller", "Arkade 5 – Noark 5",
            "Arkade 5 – PRONOM", "KDRS Query", "Depotrapporter",
        ])
        self.assertEqual([r.count for r in rows], [2, 2, 18, 2, 1])
        self.assertEqual(rows[1].details["reported_errors"], 2)
        self.assertEqual(rows[3].details["rapporttyper"], ["Standard", "U1"])
        self.assertIn("ikke faglig godkjent", rows[3].status)

    def test_unknown_pronom_count_is_not_summed_as_zero(self):
        rows = source_inventory((self.shot,), readers=_providers(
            self.shot.job.work, missing_pronom_count=True))
        self.assertIsNone(rows[2].count)
        self.assertEqual(rows[2].details["format_rows"], 2)
        self.assertEqual(rows[2].status, "Ufullstendig formatstatistikk")

    def test_missing_imports_show_unknown_not_zero(self):
        providers = {key: (lambda shots: ()) for key in self.providers}
        rows = source_inventory((self.shot,), readers=providers)
        self.assertIsNone(rows[1].count)
        self.assertIsNone(rows[2].count)
        self.assertIsNone(rows[3].count)
        self.assertIsNone(rows[4].count)
        self.assertEqual(rows[0].count, 2)

    def test_missing_depot_report_does_not_claim_success(self):
        other = _shot(self.root / "different", uid="another", depot=False)
        rows = source_inventory((other,), readers={key: lambda shots: () for key in self.providers})
        self.assertEqual(rows[0].status, "Mangler rapportgrunnlag")
        self.assertIsNone(rows[0].count)

    def test_duplicate_work_uid_counted_once(self):
        twin = SimpleNamespace(job=SimpleNamespace(job_uid=self.shot.job.job_uid,
            job_id="JOB-002", name="Another reference", work=self.shot.job.work),
            results=self.shot.results, depot=self.shot.depot)
        rows = source_inventory((self.shot, twin), readers=self.providers)
        self.assertEqual(len(rows), 5)
        self.assertTrue(all("JOB-001" in r.job_label for r in rows))

    def test_external_reference_outside_work_is_not_openable(self):
        outside = self.root / "outside.json"
        outside.write_text("{}", encoding="utf-8")
        providers = dict(self.providers)
        providers["arkade"] = lambda shots: ({"import_id": "X", "file": outside, "errors": 1},)
        rows = source_inventory((self.shot,), readers=providers)
        self.assertIsNone(rows[1].file)

    def test_coverage_uses_existing_verified_relation_map(self):
        normalized = self.shot.job.work / "external_evidence" / "arkade5" / "IMP-1" / "normalized" / "arkade5_results.json"
        normalized.write_text('{"tests": [{"test_id": "N5.62"}]}', encoding="utf-8")
        records = lambda shots: (
            {"file": normalized, "import_id": "IMP-1", "source_sha256": "sha-a"},
            {"file": normalized, "import_id": "IMP-1", "source_sha256": "sha-a"},
        )
        seen = []
        def builder(data):
            seen.append(data)
            return {"items": [
                {"arkade_test_id": "N5.62", "arkade_test_name": "Endringslogg",
                 "arkade_status": "FEIL", "classification": "partial",
                 "reason": "Dokumentert delvis dekning", "dwm_candidates": [
                     {"dwm_test_id": "dwm-7"}, {"dwm_test_id": "dwm-9"}]},
            ]}
        rows = arkade_coverage((self.shot,), rows_reader=records,
                               json_reader=self._read_json, coverage_builder=builder)
        self.assertEqual(len(seen), 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].relation, "partial")
        self.assertEqual(rows[0].dwm_test_ids, ("dwm-7", "dwm-9"))
        self.assertEqual(rows[0].arkade_status, "FEIL")
        self.assertEqual(rows[0].sha256, "sha-a")
        # _work_file returns a canonical, security-checked path.  On Windows,
        # TemporaryDirectory may reside behind a junction or path alias, so
        # compare canonical paths instead of mixing resolved and raw paths.
        self.assertEqual(rows[0].file, normalized.resolve(strict=True))
        self.assertTrue(rows[0].file.is_relative_to(self.shot.job.work.resolve(strict=True)))

    def test_coverage_does_not_infer_relation_from_matching_test_id(self):
        file = self.shot.job.work / "external_evidence" / "arkade5" / "IMP-1" / "normalized" / "arkade5_results.json"
        rows = arkade_coverage((self.shot,), rows_reader=lambda shots: ({
            "file": file, "import_id": "IMP-1"},), json_reader=self._read_json,
            coverage_builder=lambda data: {"items": [{"arkade_test_id": "N5.62",
                "classification": "unmapped", "dwm_candidates": []}]})
        self.assertEqual(rows[0].relation, "unmapped")
        self.assertEqual(rows[0].dwm_test_ids, ())

    def test_export_csv_json_html_with_separate_source_references(self):
        rows = source_inventory((self.shot,), readers=self.providers)
        dest = self.root / "export"
        dest.mkdir()
        for suffix in ("csv", "json", "html"):
            target = export_inventory(dest / ("audit." + suffix), rows, (self.shot,),
                                      json_reader=self._read_json)
            self.assertTrue(target.is_file())
            content = target.read_text(encoding="utf-8-sig")
            self.assertIn("Arkade 5", content)
            self.assertIn("KDRS Query", content)
        document = json.loads((dest / "audit.json").read_text(encoding="utf-8"))
        self.assertEqual(document["format"], "dwm-evidence-inventory-v1")
        self.assertEqual(len(document["records"]), 5)
        self.assertEqual(document["records"][2]["antall"], 18)

    def test_csv_quotes_formula_like_import_labels(self):
        target = self.root / "safe.csv"
        record = SourceRow("uid", "=HYPERLINK(\"https://example.org\")", "DWM", "",
                           "", 3, "tester", "", None, {})
        export_inventory(target, (record,), (self.shot,), json_reader=self._read_json)
        content = target.read_text(encoding="utf-8-sig")
        self.assertIn("'=HYPERLINK", content)

    def test_html_escapes_untrusted_source_names(self):
        target = self.root / "escaped.html"
        record = SourceRow("uid", "JOB-1 <script>alert(1)</script>", "DWM", "", "", None,
                           "tester", "", None, {})
        export_inventory(target, (record,), (self.shot,), json_reader=self._read_json)
        content = target.read_text(encoding="utf-8")
        self.assertNotIn("<script>", content)
        self.assertIn("&lt;script&gt;", content)
        self.assertIn("Ukjent", content)

    def test_export_refuses_implicit_overwrite(self):
        path = self.root / "already.csv"
        path.write_text("unchanged", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            export_inventory(path, (), (self.shot,), json_reader=self._read_json)
        self.assertEqual(path.read_text(), "unchanged")
        export_inventory(path, (), (self.shot,), overwrite=True,
                         json_reader=self._read_json)
        self.assertNotEqual(path.read_text(), "unchanged")

    def test_export_never_writes_inside_work(self):
        with self.assertRaisesRegex(ValueError, "Source, Work eller AIP"):
            export_inventory(self.shot.job.work / "bad.csv", (), (self.shot,),
                             json_reader=self._read_json)
        self.assertFalse((self.shot.job.work / "bad.csv").exists())

    def test_export_never_writes_inside_source_or_aip(self):
        source = self.root / "source"
        aip = self.root / "aip"
        source.mkdir()
        aip.mkdir()
        (self.shot.job.work / "job.json").write_text(json.dumps({"job": {
            "source_extraction": str(source), "archive_root": str(aip),
        }}), encoding="utf-8")
        for directory in (source, aip):
            with self.subTest(directory=directory):
                path = directory / "prohibited.json"
                with self.assertRaisesRegex(ValueError, "Source, Work eller AIP"):
                    export_inventory(path, (), (self.shot,), json_reader=self._read_json)
                self.assertFalse(path.exists())

    def test_export_requires_existing_directory(self):
        with self.assertRaisesRegex(ValueError, "eksisterende eksportmappe"):
            export_inventory(self.root / "no-directory" / "bad.csv", (), (self.shot,),
                             json_reader=self._read_json)

    def test_export_refuses_unexpected_extensions(self):
        with self.assertRaisesRegex(ValueError, "CSV, HTML eller JSON"):
            export_inventory(self.root / "bad.txt", (), (self.shot,),
                             json_reader=self._read_json)

    def test_qt_compatibility_contract_keeps_legacy_report_engines(self):
        qt = (Path(__file__).resolve().parents[1] / "gui_qt" / "result_center_v019_a1.py").read_text(
            encoding="utf-8")
        main = (Path(__file__).resolve().parents[1] / "gui_qt" / "main_window.py").read_text(
            encoding="utf-8")
        self.assertIn(".result_center_v018_a13 import ResultCenterWindow", qt)
        self.assertIn(".result_center_v019_a1 import ResultCenterWindow", main)
        self.assertIn('"Kildeoversikt"', qt)
        self.assertIn('"Arkade-dekning"', qt)
        self.assertIn('"KDRS Query"', qt)
        # The new view subclasses the old result center; existing period and
        # KDRS evidence selection actions remain inherited rather than duplicated.
        self.assertIn("class ResultCenterWindow(_PreviousResultCenter)", qt)
        self.assertIn("dialog = EvidenceResultCenter(", main)


if __name__ == "__main__":
    unittest.main()
