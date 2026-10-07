from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from noark5_workflow.core.job import Job
from noark5_workflow.reporting.depot_metadata import (
    acknowledge_metadata,
    import_selected_info_xml,
    export_info_xml,
    job_display_name,
    load_depot_metadata,
    metadata_review_state,
    scan_and_import_info_xml,
    scan_and_import_info_xml_for_jobs,
    suggest_label,
    update_current_metadata,
)

ROOT = Path(__file__).resolve().parents[1]


def _info_xml(label: str, owner: str = "") -> str:
    owner_agent = (
        f'<mets:agent TYPE="ORGANIZATION" ROLE="IPOWNER"><mets:name>{owner}</mets:name></mets:agent>'
        if owner else ""
    )
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<mets:mets xmlns:mets="http://www.loc.gov/METS/" LABEL="{label}">
  <mets:metsHdr>
    {owner_agent}
    <mets:altRecordID TYPE="SUBMISSIONAGREEMENT">Avtale 1</mets:altRecordID>
  </mets:metsHdr>
</mets:mets>
'''


def _job(root: Path, number: int = 1) -> Job:
    source = root / f"source-{number}"
    work = root / f"work-{number}"
    ops = work / "repository_operations"
    source.mkdir(parents=True)
    ops.mkdir(parents=True)
    return Job(
        f"JOB-{number:03d}",
        source_root=source,
        source_extraction=source,
        work_root=work,
        work_operations=ops,
        name=f"uttrekk-{number}",
        profile_id="noark5",
    )


class V017A1DepotMetadataTests(unittest.TestCase):
    def test_single_first_info_autofills_and_is_initially_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = _job(Path(tmp))
            info = Path(job.source_root) / "mail" / "info.xml"
            info.parent.mkdir()
            info.write_text(_info_xml("1502_023 ePhorte MEI"), encoding="utf-8")

            result = scan_and_import_info_xml(job)
            payload = load_depot_metadata(job)

            self.assertEqual(result["candidate_count"], 1)
            self.assertEqual(result["imported_new"], 1)
            self.assertEqual(payload["current"]["label"], "1502_023 ePhorte MEI")
            self.assertEqual(len(payload["source_imports"]), 1)
            self.assertFalse(metadata_review_state(job)["required"])

    def test_existing_depot_value_is_not_overwritten_by_new_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = _job(Path(tmp))
            update_current_metadata(job, {"label": "Depotets korrigerte LABEL"})
            info = Path(job.source_root) / "info.xml"
            info.write_text(_info_xml("Avsenders LABEL"), encoding="utf-8")

            scan_and_import_info_xml(job)
            payload = load_depot_metadata(job)

            self.assertEqual(payload["current"]["label"], "Depotets korrigerte LABEL")
            self.assertEqual(payload["source_imports"][0]["fields"]["label"], "Avsenders LABEL")
            self.assertTrue(metadata_review_state(job)["required"])

    def test_changed_info_xml_is_preserved_as_second_source_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = _job(Path(tmp))
            info = Path(job.source_root) / "info.xml"
            info.write_text(_info_xml("LABEL A", "Kommune A"), encoding="utf-8")
            scan_and_import_info_xml(job)
            info.write_text(_info_xml("LABEL B", "Kommune B"), encoding="utf-8")
            scan_and_import_info_xml(job)

            payload = load_depot_metadata(job)
            state = metadata_review_state(job)

            self.assertEqual(len(payload["source_imports"]), 2)
            self.assertEqual(payload["current"]["label"], "LABEL A")
            self.assertTrue(state["required"])
            self.assertTrue(any("Ulike kildeverdier" in reason for reason in state["reasons"]))

    def test_explicit_acknowledgement_clears_review_and_edit_reopens_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = _job(Path(tmp))
            update_current_metadata(job, {"label": "Kontrollert LABEL"})
            self.assertTrue(metadata_review_state(job)["required"])

            acknowledge_metadata(job)
            self.assertFalse(metadata_review_state(job)["required"])

            update_current_metadata(job, {"label": "Ny korrigert LABEL"})
            self.assertTrue(metadata_review_state(job)["required"])

    def test_set_scan_keeps_jobs_and_sources_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jobs = (_job(root, 1), _job(root, 2))
            (Path(jobs[0].source_root) / "info.xml").write_text(
                _info_xml("LABEL 1"), encoding="utf-8"
            )
            (Path(jobs[1].source_root) / "info.xml").write_text(
                _info_xml("LABEL 2"), encoding="utf-8"
            )

            results = scan_and_import_info_xml_for_jobs(jobs)

            self.assertEqual([item["candidate_count"] for item in results], [1, 1])
            self.assertEqual(load_depot_metadata(jobs[0])["current"]["label"], "LABEL 1")
            self.assertEqual(load_depot_metadata(jobs[1])["current"]["label"], "LABEL 2")


    def test_semantic_info_detection_accepts_renamed_mets_info_xml(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = _job(Path(tmp))
            candidate = Path(job.source_root) / "mail" / "1502_12345678_info.xml"
            candidate.parent.mkdir()
            candidate.write_text(
                '''<?xml version="1.0" encoding="UTF-8"?>
<mets:mets xmlns:mets="http://www.loc.gov/METS/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xsi:schemaLocation="http://www.loc.gov/METS/ http://schema.arkivverket.no/METS/info.xsd"
 LABEL="Molde ePhorte">
  <mets:metsHdr><mets:metsDocumentID>info.xml</mets:metsDocumentID></mets:metsHdr>
</mets:mets>
''',
                encoding="utf-8",
            )

            result = scan_and_import_info_xml(job)

            self.assertEqual(result["candidate_count"], 1)
            self.assertEqual(load_depot_metadata(job)["current"]["label"], "Molde ePhorte")

    def test_semantic_info_detection_accepts_uuid_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = _job(Path(tmp))
            candidate = Path(job.work_root) / "mail" / "550e8400-e29b-41d4-a716-446655440000.xml"
            candidate.parent.mkdir()
            candidate.write_text(
                '''<?xml version="1.0" encoding="UTF-8"?>
<mets:mets xmlns:mets="http://www.loc.gov/METS/" LABEL="UUID metadata">
  <mets:metsHdr><mets:metsDocumentID>info.xml</mets:metsDocumentID></mets:metsHdr>
</mets:mets>
''',
                encoding="utf-8",
            )

            result = scan_and_import_info_xml(job)
            self.assertEqual(result["candidate_count"], 1)

    def test_semantic_info_detection_rejects_ordinary_mets_xml(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = _job(Path(tmp))
            candidate = Path(job.source_root) / "mets.xml"
            candidate.write_text(
                '''<?xml version="1.0" encoding="UTF-8"?>
<mets:mets xmlns:mets="http://www.loc.gov/METS/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xsi:schemaLocation="http://www.loc.gov/METS/ http://schema.arkivverket.no/METS/mets.xsd"
 LABEL="Inner package METS">
  <mets:metsHdr><mets:metsDocumentID>mets.xml</mets:metsDocumentID></mets:metsHdr>
</mets:mets>
''',
                encoding="utf-8",
            )

            result = scan_and_import_info_xml(job)
            self.assertEqual(result["candidate_count"], 0)

    def test_document_payload_folders_are_pruned_case_insensitively(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = _job(Path(tmp))
            for name in ("DOKUMENT", "dokumenter", "Documents"):
                candidate = Path(job.source_root) / name / "1502_payload_info.xml"
                candidate.parent.mkdir(exist_ok=True)
                candidate.write_text(_info_xml("Should not be scanned"), encoding="utf-8")

            result = scan_and_import_info_xml(job)
            self.assertEqual(result["candidate_count"], 0)


    def test_explicit_info_file_can_be_imported_outside_automatic_search_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = _job(root)
            update_current_metadata(job, {"label": "Depotets LABEL"})
            external = root / "received-by-email" / "1502_info.xml"
            external.parent.mkdir()
            external.write_text(
                '''<?xml version="1.0" encoding="UTF-8"?>
<mets:mets xmlns:mets="http://www.loc.gov/METS/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xsi:schemaLocation="http://www.loc.gov/METS/ http://schema.arkivverket.no/METS/info.xsd"
 LABEL="Avsenders LABEL">
  <mets:metsHdr>
    <mets:metsDocumentID>info.xml</mets:metsDocumentID>
    <mets:agent TYPE="ORGANIZATION" ROLE="IPOWNER"><mets:name>Kommune A</mets:name></mets:agent>
  </mets:metsHdr>
</mets:mets>
''',
                encoding="utf-8",
            )

            import_selected_info_xml(job, external)
            payload = load_depot_metadata(job)

            self.assertEqual(payload["current"]["label"], "Depotets LABEL")
            self.assertEqual(payload["current"]["owner_org"], "Kommune A")
            self.assertEqual(payload["source_imports"][0]["path"], str(external.resolve()))
            self.assertEqual(payload["source_imports"][0]["fields"]["label"], "Avsenders LABEL")
            self.assertTrue(metadata_review_state(job)["required"])

    def test_explicit_info_file_rejects_ordinary_inner_mets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = _job(root)
            ordinary = root / "somewhere" / "mets.xml"
            ordinary.parent.mkdir()
            ordinary.write_text(
                '''<?xml version="1.0" encoding="UTF-8"?>
<mets:mets xmlns:mets="http://www.loc.gov/METS/" LABEL="Inner METS">
  <mets:metsHdr><mets:metsDocumentID>mets.xml</mets:metsDocumentID></mets:metsHdr>
</mets:mets>
''',
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                import_selected_info_xml(job, ordinary)

    def test_dialog_is_set_based_and_has_no_single_file_picker(self):
        source = (ROOT / "gui" / "depot_metadata_dialog_v017_a1.py").read_text(encoding="utf-8")
        self.assertIn("DEPOTMETADATA - VALGTE JOBBER", source)
        self.assertIn("Finn metadata...", source)
        self.assertIn("self._jobs", source)
        self.assertIn("Kildeverdier / historikk", source)
        self.assertNotIn("askopenfilename", source)


    def test_untouched_job_has_no_metadata_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = _job(Path(tmp))
            state = metadata_review_state(job)
            self.assertFalse(state["required"])
            self.assertEqual(state["reasons"], ())

    def test_candidate_roots_exclude_archive_and_output(self):
        source = (ROOT / "noark5_workflow" / "reporting" / "depot_metadata.py").read_text(encoding="utf-8")
        block = source.split("def _candidate_roots", 1)[1].split("def _find_info_xml", 1)[0]
        self.assertIn("job.source_root", block)
        self.assertIn("job.work_root", block)
        self.assertNotIn("job.archive_root", block)
        self.assertNotIn("job.output_root", block)

    def test_metadata_scan_is_off_gui_thread_and_exposes_progress(self):
        source = (ROOT / "gui" / "depot_metadata_dialog_v017_a1.py").read_text(encoding="utf-8")
        self.assertIn("threading.Thread(", source)
        self.assertIn('name="depot-metadata-discovery"', source)
        self.assertIn("Søker metadata:", source)
        self.assertIn("Avbryt søk", source)

    def test_job_list_exposes_metadata_review_marker(self):
        source = (ROOT / "gui" / "jobs_window_v017_a1.py").read_text(encoding="utf-8")
        self.assertIn("metadata_review_state", source)
        self.assertIn("⚠ Depotmetadata må avklares", source)
        self.assertIn("✓ Depotmetadata avklart", source)


    def test_missing_label_gets_non_persistent_identity_suggestion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "1502_023_ephorte-mei_noark5" / "content" / "sip" / "content" / "mei-2023-11-28_09-48-45-000787" / "avleveringspakke"
            work = root / "work"
            source.mkdir(parents=True)
            (work / "repository_operations").mkdir(parents=True)
            job = Job(
                "JOB-001", source_root=source, source_extraction=source,
                work_root=work, work_operations=work / "repository_operations",
                name="mei-2023-11-28_09-48-45-000787", profile_id="noark5",
            )

            suggestion = suggest_label(job)

            self.assertEqual(suggestion, "1502_023 ePhorte mei (YYYY-YYYY)")
            self.assertEqual(load_depot_metadata(job)["current"]["label"], "")

    def test_label_suggestion_keeps_visible_period_placeholder_when_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "1502_023_ephorte-mei_noark5"
            work = root / "work"
            ops = work / "repository_operations"
            source.mkdir(parents=True)
            ops.mkdir(parents=True)
            job = Job(
                "JOB-001", source_root=source, source_extraction=source,
                work_root=work, work_operations=ops,
                name="mei-2023-11-28_09-48-45-000787", profile_id="noark5",
            )
            self.assertEqual(
                suggest_label(job),
                "1502_023 ePhorte mei (YYYY-YYYY)",
            )

    def test_label_suggestion_uses_saved_reviewed_period_and_strips_storage_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "1502_024_ephorte-mk_2TB_2023_noark5" / "content" / "sip" / "content" / "mk_2TB_2023-11-22_16-47-49-000854" / "avleveringspakke"
            work = root / "work"
            ops = work / "repository_operations"
            source.mkdir(parents=True)
            ops.mkdir(parents=True)
            job = Job(
                "JOB-002", source_root=source, source_extraction=source,
                work_root=work, work_operations=ops,
                name="mk_2TB_2023-11-22_16-47-49-000854", profile_id="noark5",
            )
            report_dir = ops / "report"
            report_dir.mkdir()
            (report_dir / "depot_period_assessment.json").write_text(
                '{"scopes":{"__ALL_ARCHIVE_PARTS__":{"start_year":2008,"end_year":2019}}}',
                encoding="utf-8",
            )

            self.assertEqual(suggest_label(job), "1502_024 ePhorte mk (2008–2019)")

    def test_saved_placeholder_label_is_refreshed_from_materialized_year_series(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "1502_023_ephorte-mei_noark5"
            work = root / "work"
            ops = work / "repository_operations"
            source.mkdir(parents=True)
            ops.mkdir(parents=True)
            job = Job(
                "JOB-001", source_root=source, source_extraction=source,
                work_root=work, work_operations=ops,
                name="mei-2023-11-28_09-48-45-000787", profile_id="noark5",
            )
            update_current_metadata(job, {"label": "1502_023 ePhorte mei (YYYY-YYYY)"})
            report = ops / "dwm" / "report" / "noark5_depot_report.json"
            report.parent.mkdir(parents=True)
            report.write_text(
                '{"archive_parts":[{"is_all_archive_parts":true,"yearly_volume":{'
                '"folder":{"2007":4,"2008":2074,"2019":1489,"2020":15},'
                '"journal":{"2007":62,"2008":7894,"2019":15246,"2020":410},'
                '"document_description":{"2007":82,"2008":16381,"2020":409,"2099":11034},'
                '"document_object":{"2007":48,"2008":28331,"2020":1152,"2099":24007}'
                '}}]}',
                encoding="utf-8",
            )

            self.assertEqual(suggest_label(job), "1502_023 ePhorte mei (2008–2019)")

    def test_label_action_can_refresh_saved_placeholder_value(self):
        source = (ROOT / "gui" / "depot_metadata_dialog_v017_a1.py").read_text(encoding="utf-8")
        self.assertIn("current_by_job = {", source)
        self.assertIn('current = current_by_job.get(job.job_id, "")', source)
        self.assertIn("suggestion and suggestion != current", source)
        self.assertNotIn("if var is None or var.get().strip():", source)

    def test_label_dialog_exposes_explicit_use_suggestion_action(self):
        source = (ROOT / "gui" / "depot_metadata_dialog_v017_a1.py").read_text(encoding="utf-8")
        self.assertIn("Foreslå LABEL", source)
        self.assertIn("_suggest_labels_for_visible_rows", source)
        self.assertIn("Bruk forslag", source)
        self.assertIn("suggest_label(job)", source)
        self.assertIn("overskriver aldri eksisterende depotverdier automatisk", source)

    def test_same_metadata_dialog_supports_single_extraction_mode(self):
        source = (ROOT / "gui" / "depot_metadata_dialog_v017_a1.py").read_text(encoding="utf-8")
        self.assertIn("len(self._jobs) == 1", source)
        self.assertIn("DEPOTMETADATA - ETT UTREKK", source)
        self.assertIn("Depotmetadata - ett uttrekk", source)


    def test_label_suggestion_runs_with_progress_and_explicit_apply_choice(self):
        source = (ROOT / "gui" / "depot_metadata_dialog_v017_a1.py").read_text(encoding="utf-8")
        self.assertIn('name="depot-label-suggestion"', source)
        self.assertIn("Foreslår LABEL:", source)
        self.assertIn("askyesnocancel", source)
        self.assertIn("Ja = bruk forslagene og lagre dem", source)
        self.assertIn("Nei = bruk forslagene i feltene uten å lagre ennå", source)

    def test_job_display_name_prefers_label_without_changing_job_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = _job(Path(tmp))
            original = job.name
            self.assertEqual(job_display_name(job), original)
            update_current_metadata(job, {"label": "1502_023 ePhorte mei (2008–2019)"})
            self.assertEqual(job_display_name(job), "1502_023 ePhorte mei (2008–2019)")
            self.assertEqual(job.name, original)

    def test_jobs_window_renders_label_as_human_facing_name(self):
        source = (ROOT / "gui" / "jobs_window_v017_a1.py").read_text(encoding="utf-8")
        self.assertIn("job_display_name", source)
        self.assertIn('view["name"].configure(text=job_display_name(job))', source)



    def test_single_extraction_editor_exposes_mets_and_depot_fields(self):
        source = (ROOT / "gui" / "depot_metadata_editor_v017_a1.py").read_text(encoding="utf-8")
        self.assertIn("REDIGER METADATA - ETT UTREKK", source)
        self.assertIn('("label", "LABEL / uttrekksidentitet", "METS / info.xml")', source)
        self.assertIn('("submission_agreement", "Submission Agreement / leveransespesifikasjon", "METS / info.xml")', source)
        self.assertIn('("delivery_information", "Informasjon om innleveringen / fritekst", "Depotmetadata / tillegg")', source)
        self.assertIn("source_values(payload, key)", source)
        self.assertIn("update_current_metadata(self.job, self._values())", source)
        self.assertIn("Finn/importer metadata...", source)
        self.assertIn("Velg info.xml...", source)
        self.assertIn("filedialog.askopenfilename", source)
        self.assertIn("import_selected_info_xml(self.job, Path(filename))", source)


    def test_exported_info_xml_roundtrips_current_mets_fields(self):
        from noark5_workflow.operations.dias_mets import read_meta_from_mets
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = _job(root)
            values = {
                "label": "1502_024 ePhorte mk (2005-2007)",
                "system": "ePhorte",
                "system_version": "4.2",
                "period_start": "2005-05-02",
                "period_end": "2007-12-31",
                "owner_org": "1502 - Molde kommune",
                "creator": "Documaster AS",
                "archivist_org": "1502 - Molde kommune",
                "submitter_org": "1502 - Molde kommune",
                "submission_agreement": "18/690-2/2018-10-09",
                "producer_org": "Documaster AS",
                "producer_software": "Documaster AS",
                "preserver": "Torbjørn Aasen",
            }
            target = export_info_xml(job, root / "shared_info.xml", values=values)
            self.assertTrue(target.is_file())
            parsed = read_meta_from_mets(target)
            for key, value in values.items():
                if value:
                    self.assertEqual(parsed.get(key), value, key)

    def test_single_editor_exposes_reusable_info_xml_export(self):
        source = (ROOT / "gui" / "depot_metadata_editor_v017_a1.py").read_text(encoding="utf-8")
        self.assertIn("Eksporter info.xml...", source)
        self.assertIn("filedialog.asksaveasfilename", source)
        self.assertIn("export_info_xml(self.job, Path(filename), values=self._values())", source)
        self.assertIn("Metadata er eksportert som en gjenbrukbar info.xml.", source)
        self.assertIn("DIAS pakke-ID, TAR-referanse, størrelse eller checksum", source)

    def test_single_selected_job_routes_to_full_editor_without_blocking_scan(self):
        source = (ROOT / "gui" / "persistent_app_v017_a1.py").read_text(encoding="utf-8")
        branch = source[
            source.index("def _v017_a1_edit_metadata"):
            source.index("def _v017_a1_report_selected")
        ]
        self.assertIn("if len(selected) == 1:", branch)
        self.assertIn("self._open_active_metadata_editor()", branch)
        self.assertIn("DepotMetadataDialog(", branch)
        self.assertNotIn("self._v017_a1_scan_metadata(selected)", branch)

    def test_active_job_header_uses_depot_label_and_has_metadata_action(self):
        source = (ROOT / "gui" / "persistent_app_v017_a1.py").read_text(encoding="utf-8")
        self.assertIn('text="Metadata"', source)
        self.assertIn("command=self._open_active_metadata_editor", source)
        self.assertIn("job_display_name(self.current_job)", source)
        self.assertIn("AKTIV JOBB:", source)

    def test_v017_first_commit_version_is_a1(self):
        # tests/run_tests.py deliberately decorates Path.read_text(version.py)
        # with historical VERSION markers for legacy compatibility tests.
        # Load the real module instead of asserting the monkeypatched text view.
        import importlib.util

        version_path = ROOT / "version.py"
        spec = importlib.util.spec_from_file_location("dwm_version_v017_a1", version_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.APP_NAME, "Data Workflow Manager")
        self.assertEqual(module.VERSION, "0.1.7-a1")


if __name__ == "__main__":
    unittest.main()
