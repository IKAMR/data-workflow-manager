"""a3 bridge plus a8 source-bound paged findings from an ordinary DWM Work.

The historic a12 builder assumes an opt-in canonical-results projection exists.
The ordinary ten-operation workflow does not produce that projection.  This
adapter uses only the specifically selected job/report, the corresponding
normal XPath master and explicitly linked Arkade imports.  It neither scans
other jobs nor changes source evidence, test results or review decisions. On
large imports it writes ONLY a derived, integrity-bound SQLite index inside Work.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .qa_xpath_master_v023_a16 import project_xpath_master
from .qa_depot_stream_v023_a17 import project_depot_report
from .qa_control_coverage_v023_a18 import ControlCoverageError, reconcile_controls

from .qa_decision_v021_a12 import (
    MODEL, MAX_DEPO, MAX_ISSUES, MAX_JSON, ReportInputError, _assessments,
    _count, _extraction_label, _find_depot, _hash, _json, _kdrs, _parts,
    _rel, _source,
)


def _within_work_relative(work: Path, value: Any) -> str:
    """Convert a known Work-stored Windows relative path, never an absolute one."""
    if not isinstance(value, str) or not value.strip():
        raise ReportInputError("Missing relative evidence filename")
    clean = value.replace("\\", "/")
    path = _rel(work, clean)
    return path.relative_to(work).as_posix()


def _arkade_findings(tests: list, source_ref: str) -> list[dict]:
    """Keep only actual reported errors/warnings, not successful test results."""
    findings: list[dict] = []
    for test in tests:
        if not isinstance(test, dict):
            raise ReportInputError("Malformed Arkade test record")
        test_id = str(test.get("test_id") or "").strip()
        if not test_id:
            raise ReportInputError("Arkade test record without test_id")
        reported = str(test.get("source_status") or "").lower()
        reported = {"failed": "error", "warn": "warning"}.get(reported, reported)
        result_issues = 0
        details = test.get("results") or []
        if not isinstance(details, list):
            raise ReportInputError("Invalid Arkade result detail list")
        for detail in details:
            if not isinstance(detail, dict):
                continue
            typ = str(detail.get("result_type") or "").lower()
            if typ not in ("error", "warning", "warn", "failed", "failure"):
                continue
            level = "WARNING" if typ in ("warning", "warn") else "ERROR"
            loc = detail.get("location") or {}
            if not isinstance(loc, dict):
                loc = {}
            numbers = loc.get("line_numbers") or []
            if not isinstance(numbers, list):
                numbers = []
            trail = detail.get("result_set_path") or []
            if not isinstance(trail, list):
                trail = []
            findings.append({
                "source": "Arkade 5", "test_id": test_id, "severity": level,
                "message": str(detail.get("message") or "Arkade reports an issue without details"),
                "context": " / ".join(str(x) for x in trail),
                "file": str(loc.get("file_name") or loc.get("string") or ""),
                "lines": [n for n in numbers if type(n) is int and n > 0],
                "source_ref": source_ref, "requires_review": True,
            })
            result_issues += 1
        # Do not drop a non-OK test even if the normalized document has no
        # detailed issue message.  Such a row is a *reported* status, not a
        # new engine decision.
        if result_issues == 0 and (reported in ("error", "warning") or
                                   _count(test.get("number_of_errors")) not in (None, 0)):
            findings.append({
                "source": "Arkade 5", "test_id": test_id,
                "severity": "WARNING" if reported == "warning" else "ERROR",
                "message": "Arkade reports a non-OK test; check its original source report.",
                "context": "", "file": "", "lines": [],
                "source_ref": source_ref, "requires_review": True,
            })
        if len(findings) > MAX_ISSUES:
            raise ReportInputError("Too many Arkade findings for this report")
    return findings


def _linked_arkade(work: Path, depot: dict, job_id: str, manifest: list[dict],
                   selected: str | None, job_uid: str = '') -> dict:
    ext = depot.get("external_validation") or {}
    ark = ext.get("arkade5") or {}
    if not isinstance(ark, dict):
        raise ReportInputError("Invalid Arkade evidence in depot report")
    source_imports = ark.get("imports") or []
    if not isinstance(source_imports, list):
        raise ReportInputError("Invalid Arkade import list in depot report")
    if not source_imports:
        return {"status": "not_available", "source": None,
                "summary": {}, "test_count": None, "findings": []}
    candidates = []
    for item in source_imports:
        if not isinstance(item, dict):
            raise ReportInputError("Malformed Arkade import reference")
        source_rel = _within_work_relative(work, item.get("normalized_file"))
        candidates.append((source_rel, item))
    if selected:
        wanted = _within_work_relative(work, selected)
        candidates = [x for x in candidates if x[0] == wanted]
        if not candidates:
            raise ReportInputError("Chosen Arkade evidence is not linked to this depot report")
    if len(candidates) != 1:
        raise ReportInputError(
            "Several Arkade imports in this report; select one explicitly before QA export"
        )
    normalized_rel, reported = candidates[0]
    if not normalized_rel.startswith("external_evidence/arkade5/") or not normalized_rel.endswith(
            "/normalized/arkade5_results.json"):
        raise ReportInputError("Unexpected Arkade normalized path")
    base = normalized_rel.rsplit("/normalized/", 1)[0]
    manifest_rel = base + "/manifest.json"
    meta = _json(_rel(work, manifest_rel))
    if meta.get("format_version") != 2 or meta.get("import_id") != base.split("/")[-1]:
        raise ReportInputError("Arkade import identity mismatch")
    imported_for = str((meta.get("imported_by") or {}).get("job_id") or "")
    if imported_for and imported_for != job_id:
        raise ReportInputError("Arkade import belongs to another Work job")
    meta_rel = _within_work_relative(work, meta.get("normalized_file"))
    if meta_rel != normalized_rel:
        raise ReportInputError("Arkade manifest points to a different normalized report")
    expected_hash = str(reported.get("source_sha256") or "")
    declared_hash = str((meta.get("source") or {}).get("sha256") or "")
    if len(expected_hash) != 64 or expected_hash != declared_hash:
        raise ReportInputError("Arkade source SHA-256 differs from selected depot report")
    source_rel = _within_work_relative(work, (meta.get("source") or {}).get("preserved_file"))
    from noark5_workflow.analysis.canonical_external_import_v0115_a10 import (
        MAX_SOURCE_ARKADE, MAX_SOURCE_NORMALIZED,
    )
    manifest.append({"kind": "external_manifest", **_source(work, manifest_rel)})
    manifest.append({"kind": "external_original", **_source(
        work, source_rel, expected_hash, limit=MAX_SOURCE_ARKADE)})
    # a8: a source above 20 MiB is valid if its preserved original is verified.
    # Never force a full JSON decode just to populate an interactive KS view.
    manifest.append({"kind": "external", **_source(work, normalized_rel,
                                                    limit=MAX_SOURCE_ARKADE)})
    normalized_path = _rel(work, normalized_rel)
    indexed = None
    if normalized_path.stat().st_size <= MAX_JSON:
        normalized = _json(normalized_path, MAX_JSON)
    else:
        normalized = None
    if normalized is None:
        from .qa_paged_v023_a8 import build_arkade_index
        indexed = build_arkade_index(work, normalized_rel,
                                     original_sha256=expected_hash,
                                     job_uid=job_uid or job_id,
                                     preserved_relative=source_rel)
    if normalized is not None and (normalized.get("format_version") != 2 or
            normalized.get("evidence_type") != "arkade5_normalized_results"):
        # DWM normalized data evolved.  Accept an explicit normalized source
        # marker, never an arbitrary JSON file posing as Arkade.
        if not (normalized.get("format_version") == 2 and
                str(normalized.get("source_system") or "").lower() == "arkade 5" and
                isinstance(normalized.get("tests"), list)):
            raise ReportInputError("Unrecognized normalized Arkade report")
    if normalized is not None:
        norm_hash = str((normalized.get("source") or {}).get("sha256") or "")
        if norm_hash != expected_hash:
            raise ReportInputError("Arkade normalized report is not bound to preserved source")
        tests = normalized.get("tests")
        if not isinstance(tests, list):
            raise ReportInputError("Arkade tests must be a list")
        try:
            found_rows = _arkade_findings(tests, normalized_rel)
        except ReportInputError as exc:
            if str(exc) != "Too many Arkade findings for this report":
                raise
            from .qa_paged_v023_a8 import build_arkade_index
            indexed = build_arkade_index(work, normalized_rel,
                                         original_sha256=expected_hash,
                                         job_uid=job_uid or job_id,
                                         preserved_relative=source_rel)
    else:
        found_rows = []
    # PRONOM is a separate historical classification, not a Noark result.
    pronom = (meta.get("pronom_evidence") or {}).get("statistics") or {}
    if pronom.get("imported"):
        p_rel = _within_work_relative(work, pronom.get("normalized_file"))
        if p_rel != base + "/normalized/pronom_statistics.json":
            raise ReportInputError("Unexpected PRONOM import reference")
        original = _within_work_relative(work, pronom.get("preserved_file"))
        manifest.append({"kind": "external_original", **_source(
            work, original, str(pronom.get("sha256") or ""),
            limit=MAX_SOURCE_ARKADE)})
        manifest.append({"kind": "external", **_source(
            work, p_rel, limit=MAX_SOURCE_NORMALIZED)})
        p_path = _rel(work, p_rel)
        if p_path.stat().st_size <= MAX_JSON:
            pronom_type = _json(p_path).get("evidence_type")
        else:
            from .qa_paged_v023_a8 import streamed_json_marker
            pronom_type = streamed_json_marker(p_path, 'evidence_type')
        if pronom_type != "arkade5_pronom_format_statistics":
            raise ReportInputError("Invalid normalized PRONOM statistics")
    if indexed is not None:
        # All rows live in a SHA-bound SQLite index. The ordinary KS snapshot
        # receives a *labelled preview*, not an invented complete findings list.
        meta = {key: val for key, val in indexed.items() if key != 'preview'}
        return {"status": "reported_unverified", "source": normalized_rel,
                "summary": indexed.get('reported_summary') or {},
                "test_count": indexed['test_count'],
                "findings": indexed['preview'],
                "finding_count": indexed['finding_count'],
                "findings_complete": indexed['finding_count'] == len(indexed['preview']),
                "a8_paged_index": meta}
    return {"status": "reported_unverified", "source": normalized_rel,
            "summary": normalized.get("summary") or {}, "test_count": len(tests),
            "findings": found_rows, "finding_count": len(found_rows),
            "findings_complete": True, "a8_paged_index": None}


def build_saved_work_snapshot(work: str | Path, *, depot_report: str | None = None,
                              kdrs_qa: str | Path | None = None,
                              arkade_evidence: str | None = None) -> dict:
    """Compose the established a12 snapshot solely from the selected Work.

    No canonical-results.json is fabricated.  The depot report ties the
    original run folder, normal XPath master and external import references.
    Every evidence path is contained within Work and hashed; source is read-only.
    """
    root = Path(work).resolve(strict=True)
    job = _json(_rel(root, "job.json"))
    props = job.get("job") or {}
    if (job.get("file_type") != "dwm-work-job" or
            job.get("format_version") != 1 or not isinstance(props, dict)):
        raise ReportInputError("Selected directory is not a canonical DWM Work job")
    job_id = str(props.get("job_id") or "")
    uid = str(job.get("job_uid") or "")
    if not job_id or not uid or (props.get("job_uid") and props["job_uid"] != uid):
        raise ReportInputError("Missing or contradictory Work job identity")
    report_path, depot_rel = _find_depot(root, depot_report)
    # Windows can spell the same directory as a long user name or as its
    # short 8.3 alias (e.g. TORBJO~1.AAS).  Path.relative_to() compares
    # spelling, not filesystem identity.  Anchor the selected report to the
    # already verified Work-relative path before calling older QA helpers.
    # Do not treat two files with the same filename/content as interchangeable:
    # samefile() must confirm that they are the *same* on-disk file.
    work_report_path = _rel(root, depot_rel)
    try:
        if (report_path.is_symlink() or not work_report_path.is_file() or
                not work_report_path.samefile(report_path)):
            raise ReportInputError('Valgt depotrapport tilhører ikke angitt Work-evidens')
    except OSError as exc:
        raise ReportInputError('Kan ikke verifisere valgt depotrapport i Work') from exc
    report_path = work_report_path
    if not report_path.parent.name.startswith(job_id + "__"):
        raise ReportInputError("Depot report belongs to a different job")
    # A17: the established small-report path remains unchanged. For a large
    # original report, stream *all* JSON and retain precisely the fields used
    # by the KS projection. Compare the parser's byte digest with the Work
    # manifest's independent SHA-256 to prevent a mixed source revision.
    large_depot = report_path.stat().st_size > MAX_DEPO
    if large_depot:
        depot, parsed_depot_sha = project_depot_report(report_path)
    else:
        depot = _json(report_path, MAX_DEPO)
        parsed_depot_sha = None
    if depot.get("report_type") != "noark5_depot_validation":
        raise ReportInputError("Selected report is not a DWM depot validation report")
    # Only the full Work snapshot needs the XPath/depot source binding.
    from .qa_decision_v021_a12 import _xpath_master_binding
    xpath_binding = _xpath_master_binding(root, report_path, depot, job)
    master_rel = xpath_binding["master_relative_path"]
    # A16: read every byte of the exact normal XPath master while retaining
    # only the small test identity/state projection required by this bridge.
    # No 20 MiB cutoff and no unbounded JSON materialization.
    master = project_xpath_master(_rel(root, master_rel))
    if (master.get("format_version") != 1 or
            str((master.get("source") or {}).get("execution_profile")) != "normal" or
            not isinstance(master.get("tests"), list)):
        raise ReportInputError("The selected run has no normal XPath master results")
    reported_tests = ((depot.get("technical_validation") or {}).get("tests") or [])
    master_ids = {str(t.get("test_id") or "") for t in master["tests"] if isinstance(t, dict)}
    if not isinstance(reported_tests, list) or not master_ids:
        raise ReportInputError("Invalid DWM technical evidence")
    if len(master_ids) != len(master["tests"]):
        raise ReportInputError("Duplicate XPath master test identifiers")
    master_states = {str(t["test_id"]): str(t.get("status") or "").casefold()
                     for t in master["tests"]}
    if any(not isinstance(t, dict) or str(t.get("test_id") or "") not in master_ids
           for t in reported_tests):
        raise ReportInputError("Depot validation and XPath master refer to different tests")
    if any(str(t.get("status") or "").casefold() != master_states[t["test_id"]]
           for t in reported_tests):
        raise ReportInputError("Depot validation disagrees with the saved XPath master status")
    depot_record = _source(root, depot_rel,
                           limit=(1 << 63) - 1 if large_depot else MAX_DEPO)
    if parsed_depot_sha is not None and depot_record['sha256'] != parsed_depot_sha:
        raise ReportInputError('Depotrapporten ble endret mellom lesing og SHA-256-kontroll')
    manifest = [
        {"kind": "work_job", **_source(root, "job.json")},
        {"kind": "dwm_xpath_master", **_source(
            root, master_rel, limit=(1 << 63) - 1)},
        {"kind": "dwm_depot", **depot_record},
        *xpath_binding["artifact_manifests"],
    ]
    arkade = _linked_arkade(root, depot, job_id, manifest, arkade_evidence,
                             job_uid=uid)
    kdrs = _kdrs(root, depot, Path(kdrs_qa) if kdrs_qa else None, manifest)
    human = _assessments(root, report_path, manifest)
    parts = _parts(depot)
    counts = {key: _count(value) for key, value in (depot.get("summary") or {}).items()}
    if counts.get("archive_part_count") is not None and counts["archive_part_count"] != len(parts):
        raise ReportInputError("Archive part totals contradict the depot report")
    deviation_rows = [d for d in depot.get("deviations") or [] if isinstance(d, dict)]
    findings = [{
        "source": "DWM depotvalidering", "test_id": str(d.get("category") or "unknown"),
        "severity": str(d.get("severity") or "review").upper(),
        "message": str(d.get("summary") or "No description available"),
        "context": "", "file": "", "lines": [], "source_ref": depot_rel,
        "requires_review": bool(d.get("requires_review")),
    } for d in deviation_rows]
    findings.extend(arkade["findings"])
    for part in parts:
        if "aktiv" in str(part.get("status") or "").casefold():
            findings.append({
                "source": "DWM arkivdelstatus", "test_id": "arkivdel.active_period",
                "severity": "REVIEW",
                "message": "Archive part has an active period at delivery; human review required.",
                "context": part["title"] + " (" + part["system_id"] + ")",
                "file": "", "lines": [], "source_ref": depot_rel,
                "requires_review": True,
            })
    findings_complete = bool(arkade.get('findings_complete', True))
    complete_count = len(findings) + max(0, int(arkade.get('finding_count',
                            len(arkade['findings']))) - len(arkade['findings']))
    technical = depot.get("technical_validation") or {}
    if not isinstance(technical, dict):
        raise ReportInputError("Invalid technical validation block")
    # A18: status belongs to the original test engine. Never add DWM and
    # Arkade test totals into a fictitious compliance score; don't count
    # PRONOM format statistics as Noark validation tests. The linked Arkade
    # evidence is fully streamed and SHA-verified, even when the KS snapshot
    # contains only its A8 paginated findings preview.
    arkade_source = str(arkade.get('source') or '')
    selected_norm = [item for item in manifest if item.get('kind') == 'external'
                     and item.get('path') == arkade_source] if arkade_source else []
    selected_import = [item for item in (
        ((depot.get('external_validation') or {}).get('arkade5') or {}).get('imports') or [])
        if isinstance(item, dict)
        and str(item.get('normalized_file') or '').replace('\\', '/') == arkade_source
    ] if arkade_source else []
    if arkade_source and (len(selected_norm) != 1 or len(selected_import) != 1):
        raise ReportInputError('A18 mangler entydig SHA-kobling til valgt Arkade Noark-kilde')
    try:
        control_coverage = reconcile_controls(
            master=master, depot_tests=reported_tests,
            depot_summary=depot.get('summary') or {}, parts=parts,
            arkade_path=_rel(root, arkade_source) if arkade_source else None,
            arkade_source_sha256=selected_norm[0]['sha256'] if arkade_source else None,
            arkade_original_sha256=selected_import[0]['source_sha256'] if arkade_source else None,
            pronom_imported=any(item.get('kind') == 'external' and
                                str(item.get('path') or '').endswith('/pronom_statistics.json')
                                for item in manifest),
            depot_technical_status=str(technical.get('status') or ''),
        )
    except ControlCoverageError as exc:
        raise ReportInputError('A18 kontrollstatus kan ikke verifiseres: ' + str(exc)) from exc
    return {
        "model_id": MODEL,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "report_status": ("DRAFT_REVIEW_REQUIRED" if findings_complete
                          else "DRAFT_PARTIAL_PREVIEW_NOT_FOR_PUBLICATION"),
        "findings_complete": findings_complete,
        "full_finding_count": complete_count,
        "a8_paged_index": arkade.get('a8_paged_index'),
        "work_identity": {
            "job_uid": uid, "job_id": job_id, "job_name": str(props.get("name") or ""),
            "extraction_label": _extraction_label(props),
            "canonical_identity_scope": "verified_work_job_and_selected_depot_report",
        },
        "reported_identity": {
            "system_from_arkade_not_verified": arkade["summary"].get("system_name"),
            "period_from_arkade_not_verified": arkade["summary"].get("archival_period"),
            "archive_creators_from_canonical": None, "archive_owner_from_canonical": None,
            "noark_version_from_canonical": None,
        },
        "dwm_summary": counts,
        "dwm_technical": {
            "status": technical.get("status"), "summary": technical.get("summary") or {},
            "reconciliation": technical.get("reconciliation") or {},
        },
        "archive_parts": parts, "dwm_report_source": depot_rel,
        "xpath_source_binding": xpath_binding,
        "arkade": arkade, "kdrs_qa": kdrs, "human_context_events": [],
        "control_coverage": control_coverage,
        "existing_depot_assessment": human, "findings": findings,
        "review_required": True,
        "acceptance_from_archive_creator_registered": False,
        "depot_formal_decision_registered_by_a12": False,
        "journal_reference_registered_by_a12": False,
        "aip_produced_by_a12": False,
        "evidence_manifest": manifest,
        "limitations": [
            "Source evidence and original Work results are unchanged.",
            "No canonical result index was generated or inferred.",
            "Technical OK, historical RAF and professional approval remain separate.",
            *(["A17: Stor depotrapport er fullstendig validert og SHA-kontrollert, "
                "men KS-snapshotet gjengir bare relevante felter og teststatus. "
                "Originale testdetaljer leses fra uendret Work-evidens."]
              if large_depot else []),
            "No archive acceptance or formal depot decision has been registered.",
            *(["A8: preview only; all Arkade findings are in a source-verified "
                "paged index. Do not publish legacy KS bundles from this snapshot; "
                "use complete A260 CSV/JSONL exports."] if not findings_complete else []),
        ],
    }
