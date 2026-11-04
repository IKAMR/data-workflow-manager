"""a13: source-preserving year comparison, report/evidence detail and Qt wiring.

Headless; no PySide6 required in CI. Uses small synthetic Work fixtures and
never requires a user's original Noark5 DOKUMENT or a legacy joblist.
"""
from __future__ import annotations

import ast
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.result_evidence_v018_a13 import (
    METRICS, annual_scopes, annual_table, archive_part_details, arkade_rows,
    describe_span, evidence_alerts, kdrs_rows, open_work_job, overview_rows,
    period_rows, pronom_rows, report_links, safe_json, technical_rows,
    kdrs_annual_scopes, kdrs_annual_table,
)

ROOT = Path(__file__).resolve().parents[1]


class A13EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def write(self, work, rel, data):
        path = work / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def make_job(self, name, uid, *, parts, job_id="JOB-001", archive_count=None):
        work = self.base / name / "dwm"
        work.mkdir(parents=True)
        self.write(work, "job.json", {"job_uid": uid, "job": {"job_id": job_id, "profile_id": "noark5"}})
        report = {
            "report_type": "noark5_depot_validation",
            "summary": {"archive_part_count": len(parts), "folder_count": 100},
            "archive_parts": parts,
            "assessment": {"status": "requires_clarification"},
            "technical_validation": {"status": "ok", "tests": [{"test_id": "kdrs.c13", "status": "ok", "legacy_job_id": "C13", "reconciliation_summary": {"checks": 2, "mismatches": 0}}]},
            "deviations": [{"requires_review": True, "summary": "Sjekk endringslogg"}],
            "period_reconciliation": {"declared_period": {"start_year": 2018, "end_year": 2020},
                                      "archive_parts": [{"archive_part": {"system_id": (p["archive_part"]["system_id"])},
                                                         "observed_period": {"first_year": 2018, "last_year": 2020}} for p in parts]},
        }
        self.write(work, "noark5_reports/depot_validation/JOB-001__RUN-001/depot_validation_report.json", report)
        (work / "noark5_reports/depot_validation/JOB-001__RUN-001/depot_validation_report.html").write_text("<html></html>")
        return open_work_job(job_id, name, work)

    def test_yearly_scopes_include_all_jobs_and_native_archive_parts(self):
        a = self.make_job("source-A", "u-a", parts=[{
            "archive_part": {"system_id": "A1", "title": "Saksarkiv"},
            "yearly_volume": {"folder": {"2018": 3, "2019": 2},
                              "registration": {"2018": 7, "2019": 9},
                              "journal": {"2018": 5, "2019": 1},
                              "document_description": {"2018": 2, "2019": 2},
                              "document_object": {"2018": 8, "2019": 3}}}])
        b = self.make_job("source-B", "u-b", parts=[{
            "archive_part": {"system_id": "B1", "title": "Migrert"},
            "yearly_volume": {"folder": {"2018": 4, "2019": 6},
                              "registration": {"2018": 3, "2019": 1},
                              "journal": {"2018": 3, "2019": 8},
                              "document_description": {"2018": 9, "2019": 1},
                              "document_object": {"2018": 2, "2019": 1}}}])
        scope = annual_scopes([a,b])
        self.assertEqual(len(scope), 5)
        self.assertNotEqual(scope[1].key,scope[3].key)
        both = annual_table([a,b], "all")
        self.assertEqual(both.source_count, 2)
        self.assertEqual(both.rows[0]["folder"], 7)
        self.assertEqual(both.rows[0]["registration"], 10)
        self.assertEqual(both.rows[0]["journal"], 8)
        self.assertEqual(both.rows[0]["document_description"], 11)
        self.assertEqual(both.rows[0]["document_object"], 10)
        single = annual_table([a,b],scope[2].key)
        self.assertEqual(single.rows[0]["folder"], 3)
        self.assertEqual(single.source_count, 1)
        self.assertEqual(len(overview_rows([a,b])),2)
        self.assertEqual(len(archive_part_details([a,b])),2)
        self.assertEqual(len(technical_rows([a,b])),2)
        self.assertEqual(len(report_links([a,b])),4)
        self.assertTrue(any("Sjekk endringslogg" in row for row in evidence_alerts([a,b])))

    def test_same_work_uuid_never_double_counts_annual_sums(self):
        one = self.make_job("repeat", "same-uid", parts=[{
            "archive_part": {"system_id": "A"},
            "yearly_volume": {m: {"2020": 4} for m, _ in METRICS}}])
        table = annual_table((one, one))
        self.assertEqual(table.rows[0]["folder"], 4)
        self.assertEqual(table.source_count, 1)
        self.assertEqual(len(annual_scopes((one, one))), 3)
        self.assertEqual(one.job.work_operations, one.job.work)

    def test_multi_job_totals_disclose_possible_overlap(self):
        part = {"archive_part": {"system_id": "A"},
                "yearly_volume": {m: {"2020": 4} for m, _ in METRICS}}
        left = self.make_job("before", "uid-before", parts=[part])
        right = self.make_job("after", "uid-after", parts=[part])
        table = annual_table((left, right))
        self.assertEqual(table.rows[0]["folder"], 8)
        self.assertTrue(any("ikke automatisk unike" in warning for warning in table.warnings))

    def test_missing_registration_never_substitutes_journal(self):
        known = {"archive_part": {"system_id": "A"},
                 "yearly_volume": {"folder": {"2020": 1}, "registration": {"2020": 2},
                                   "journal": {"2020": 3}, "document_description": {"2020": 4},
                                   "document_object": {"2020": 5}}}
        unknown = {"archive_part": {"system_id": "B"},
                   "yearly_volume": {"folder": {"2020": 10}, "journal": {"2020": 20},
                                     "document_description": {"2020": 1}, "document_object": {"2020": 2}}}
        a = self.make_job("part-missing", "uid", parts=[known, unknown])
        overall = annual_table([a])
        self.assertEqual(overall.rows[0]["folder"], 11)
        self.assertIsNone(overall.rows[0]["registration"])
        self.assertEqual(overall.rows[0]["journal"], 23)
        self.assertTrue(any("Registreringer per år" in warning for warning in overall.warnings))

    def test_absent_single_year_not_zero_when_other_series_has_year(self):
        part = {"archive_part": {"system_id": "A"},
                "yearly_volume": {"folder": {"2020": 1, "2022": 3},
                                  "registration": {"2021": 2}}}
        shot = self.make_job("sparse", "uid", parts=[part])
        result = annual_table([shot])
        row = next(row for row in result.rows if row["year"] == 2021)
        self.assertIsNone(row["folder"])
        self.assertEqual(row["registration"], 2)
        self.assertIsNone(row["document_object"])
        self.assertEqual(len(result.observed_years),3)

    def test_invalid_and_missing_json_do_not_change_originals(self):
        a = self.make_job("immutable", "uid", parts=[])
        before = {p: p.stat().st_mtime_ns for p in a.job.work.rglob("*") if p.is_file()}
        self.assertIsNone(safe_json(a.job.work, "not-found.json"))
        self.assertIsNone(safe_json(a.job.work, "../outside.json"))
        self.assertEqual(annual_table([a]).rows, ())
        after = {p: p.stat().st_mtime_ns for p in a.job.work.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_symlink_and_oversize_json_rejected(self):
        a = self.make_job("secure", "uid", parts=[])
        outside = self.base / "outside.json"
        outside.write_text('{"secret":123}',encoding="utf-8")
        link = a.job.work / "linked.json"
        try:
            link.symlink_to(outside)
        except (OSError,NotImplementedError):
            self.skipTest("Symlink er ikke tilgjengelig")
        self.assertIsNone(safe_json(a.job.work,"linked.json"))
        self.write(a.job.work,"data.json",{"v":123})
        self.assertIsNone(safe_json(a.job.work,"data.json",max_bytes=2))

    def test_arkade_pronom_and_kdrs_imported_from_work_only(self):
        a = self.make_job("external", "uid", parts=[])
        root = "external_evidence/arkade5/2026-abcd"
        self.write(a.job.work,root+"/manifest.json",{"import_id":"2026-abcd","source":{"sha256":"abc"}})
        self.write(a.job.work,root+"/normalized/arkade5_results.json",{
            "summary":{"number_of_tests_run":"1 av 1"},
            "tests":[{"test_id":"N5.62","test_name":"Endringslogg-referanser",
                      "source_status":"error","number_of_errors":2,
                      "results":[{"message":"Ugyldig arkivenhet"}]}]})
        self.write(a.job.work,root+"/normalized/pronom_statistics.json",{
            "evidence_type":"arkade5_pronom_format_statistics", "source":{"sha256":"ff"},
            "csv":{"rows":[{"Format-ID":"fmt/354","Antall":"1","Filtype":"PDF/A"},
                           {"Format-ID":"fmt/101","Antall":"6","Filtype":"XML"},
                           {"Format-ID":"x-fmt/280","Antall":"7","Filtype":"XSD"}]}})
        self.write(a.job.work,"external_evidence/kdrs_query/kdrs-12/manifest.json",{
            "import_id":"kdrs-12","files":[{"report_type":"u2","original_name":"KDRS.tsv","sha256":"abcdef"}]})
        arts=arkade_rows([a])
        self.assertEqual(len(arts),1)
        self.assertEqual(arts[0]["errors"],2)
        self.assertEqual(len(pronom_rows([a])),3)
        self.assertEqual(sum(x["count"] for x in pronom_rows([a])),14)
        queries=kdrs_rows([a])
        self.assertEqual(len(queries),1)
        self.assertEqual(queries[0]["source"],"KDRS.tsv")
        self.assertEqual(queries[0]["sha256"],"abcdef")
        self.assertEqual(len(period_rows([a])),1)

    def test_kdrs_annual_sources_do_not_merge_with_dwm_or_other_imports(self):
        shot = self.make_job("kdrs-kilde", "uid-a", parts=[{
            "archive_part": {"system_id": "DWM"},
            "yearly_volume": {"folder": {"2020": 100}, "registration": {"2020": 200}}}])
        imported = ({"job": shot.job, "import_id": "kdrs-u01", "report_type": "u01",
                    "source_files": ("u01.tsv",), "scope_id": "whole", "scope_label": "Hele uttrekket",
                    "source": {"series": {
                        "folders_by_creation_year": {"2020": 3, "2021": None},
                        "registrations_by_creation_year": {"2020": 9},
                        "journalposts_by_journal_year": {"2020": 2},
                        "change_log_events_by_year": {"2022": 400}},
                        "conflicts": ["Mapper 2021: motstrid"]}},)
        with patch('app.result_evidence_v018_a13.kdrs_period_sources', return_value=imported):
            scope = kdrs_annual_scopes([shot])
            self.assertEqual(len(scope),1)
            data = kdrs_annual_table([shot],scope[0].key)
        self.assertEqual(data.rows[0]['folder'],3)
        self.assertEqual(data.rows[0]['registration'],9)
        self.assertEqual(data.rows[0]['journal'],2)
        self.assertIsNone(data.rows[0]['document_object'])
        self.assertEqual(data.rows[1]['folder'],None)
        self.assertNotIn(2022,data.observed_years)
        self.assertEqual(annual_table([shot]).rows[0]['folder'],100)
        self.assertIn('Mapper 2021: motstrid',data.warnings)

    def test_period_fields_are_not_approved_by_observation(self):
        a = self.make_job("period", "uid", parts=[])
        rows=period_rows([a])
        self.assertEqual(rows[0]["assessment"],{})
        self.assertEqual(describe_span(rows[0]["declared"]),"2018–2020")
        self.assertEqual(describe_span({"span":{"first_year":2018,"last_year":2020}}),"2018–2020")

    def test_missing_or_offline_work_not_falsely_reported_as_zero(self):
        self.assertIsNone(open_work_job("JOB-001","offline",self.base / "disconnected"))
        a = self.make_job("missing-depot", "uid", parts=[])
        for p in (a.job.work / "noark5_reports").rglob("depot_validation_report.json"):
            p.unlink()
        new = open_work_job("JOB-001","missing-depot",a.job.work)
        self.assertIsNone(new.depot)
        self.assertEqual(annual_table([new]).rows,())
        self.assertTrue(any("Ingen lesbar depotrapport" in w for w in annual_table([new]).warnings))

    def test_qt_gui_stays_python_and_reuses_legacy_services(self):
        gui = (ROOT / "gui_qt" / "result_center_v018_a13.py").read_text(encoding="utf-8")
        window = (ROOT / "gui_qt" / "main_window.py").read_text(encoding="utf-8")
        report = (ROOT / "gui_qt" / "report_selected_v018_a12.py").read_text(encoding="utf-8")
        ast.parse(gui);ast.parse(window)
        for label in ("Årsfordeling", "Periodevurdering", "Tekniske kontroller", "Arkade 5",
                      "PRONOM", "KDRS Query", "Depotrapporter", "Evidensfiler", "Velg uttrekk"):
            self.assertIn(label, gui)
        for feature in ("YearBarChart", "year_scope", "save_part_assessment", "save_assessment",
                        "select_evidence", "exact_candidates", "set_data", "QPainter"):
            self.assertIn(feature, gui)
        self.assertIn("from .result_center_v018_a13 import ResultCenterWindow",window)
        self.assertIn("available_jobs=self.api.report_candidates()",window)
        self.assertIn("write_reconnectable_report",report)
        self.assertNotIn("customtkinter", gui)

if __name__ == '__main__':
    unittest.main()
