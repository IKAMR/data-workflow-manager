"""DWM v0.2.2-a3: manual control findings and a unified QA review snapshot.

This extends the existing a12/a13/a14/a15 evidence pipeline.  It is not a
second validator, a new decision register, or an automatic archive approval.
All writes are explicit and append-only inside the correct job's Work.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import time
from typing import Any, Iterator
from uuid import uuid4

from .qa_decision_v021_a12 import _hash, _json, _rel, build_snapshot, MAX_DEPO, MAX_JSON, ReportInputError
from .qa_work_snapshot_v022_a3 import build_saved_work_snapshot
from .qa_delivery_v023_a11 import attach_delivery_to_snapshot
from .qa_review_v021_a13 import (
    ReviewError, _binding, _check_work_and_source, finding_key,
    latest_reviews, with_selected_reviews,
)

MANUAL_DIR = "noark5_evidence/qa_manual_findings_v022_a3"
MANUAL_MODEL = "ikamr.dwm.noark5.manual-finding-event.a3.v1"
MAX_MANUAL = None  # Kept for compatibility; no cumulative event-count ceiling.
MAX_BYTES = 14000
MAX_DESCRIPTION = 3000
SEVERITIES = ("ERROR", "WARNING", "REVIEW", "NOTE", "INFORMATION")


def _canonical(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def ensure_qa_evidence_parent(work: str | Path) -> Path:
    """Create the a3 event parent on explicit save only; never on a read.

    The ordinary workflow correctly has no noark5_evidence directory.
    Reject all symlinks before creating the local event parent.
    """
    root = Path(work).resolve(strict=True)
    parent = _rel(root, "noark5_evidence")
    if parent.exists():
        if parent.is_symlink() or not parent.is_dir():
            raise ReviewError("Unsafe Work evidence directory")
    else:
        parent.mkdir(mode=0o700)
    return parent


def _manual_dir(work: Path, *, create: bool = False) -> Path:
    root = Path(work).resolve(strict=True)
    folder = _rel(root, MANUAL_DIR)
    if folder.exists() and (not folder.is_dir() or folder.is_symlink()):
        raise ReviewError("Ugyldig katalog for manuelle avvik")
    if create:
        parent = ensure_qa_evidence_parent(root)
        if parent != folder.parent:
            raise ReviewError("Invalid manual finding parent")
        folder.mkdir(exist_ok=True)
    return folder


def _iter_manual_events(work: str | Path) -> Iterator[dict]:
    """Verify every immutable manual event without a 2,000-file limit.

    A missing directory means no manual observations. Unknown files,
    symbolic links, oversized events, changed checksums and invalid event
    identity fail closed, including events from older depot revisions.
    Filesystem enumeration order is deliberately not treated as chronology.
    """
    folder = _manual_dir(Path(work))
    if not folder.exists():
        return
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                path = Path(entry.path)
                if (path.suffix != ".json" or entry.is_symlink()
                        or not entry.is_file(follow_symlinks=False)):
                    raise ReviewError("Ukjent fil i manuelt avviksregister")
                if entry.stat(follow_symlinks=False).st_size > MAX_BYTES:
                    raise ReviewError("Manuelt avvik overskrider størrelsesgrensen")
                event = _json(path, MAX_BYTES)
                if event.get("model_id") != MANUAL_MODEL or event.get("event_id") != path.stem:
                    raise ReviewError("Ukjent avvikshendelse eller filidentitet")
                unsigned = {k: v for k, v in event.items() if k != "event_sha256"}
                if event.get("event_sha256") != sha256(_canonical(unsigned)).hexdigest():
                    raise ReviewError("Manuell avvikshendelse har endret innhold")
                if (event.get("severity") not in SEVERITIES
                        or not isinstance(event.get("message"), str)
                        or not event["message"].strip()
                        or len(event["message"]) > MAX_DESCRIPTION
                        or type(event.get("recorded_ns")) is not int):
                    raise ReviewError("Ugyldig manuell avvikshendelse")
                yield event
    except OSError as exc:
        raise ReviewError("Kan ikke lese komplett manuelt avviksregister") from exc


def _read_manual(work: Path) -> list[dict]:
    """Compatibility API: chronological results, unbounded in event count.

    The iterator above is the streaming path for large Work directories.
    Existing callers of this API retain their original ordering.
    """
    return sorted(_iter_manual_events(work),
                  key=lambda event: (event["recorded_ns"], event["event_id"]))


def manual_ledger_state(work: str | Path, *, job_uid: str = "",
                        depot_sha256: str = "") -> dict:
    """Verified, compact provenance for A12 index caching and export checks.

    Includes *all* manual events from the Work directory, even older ones.
    File hashes detect changes to physical evidence bytes, not just changed
    canonical fields. Also return the fingerprint of events belonging to the
    exact Work job and depot report; no list of file paths is published.
    """
    folder = _manual_dir(Path(work))
    files: list[tuple[str, str]] = []
    current: list[str] = []
    for event in _iter_manual_events(work):
        event_id = str(event["event_id"])
        # The event and the physical file have already been checked. Hash the
        # original bytes as well: JSON reformatting must invalidate the cache.
        files.append((event_id, _hash(folder / (event_id + ".json"))))
        if (event.get("job_uid") == job_uid
                and event.get("depot_report_sha256") == depot_sha256):
            current.append(event_id)
    digest = sha256()
    for eid, file_hash in sorted(files):
        digest.update((eid + ":" + file_hash + "\n").encode("utf-8"))
    identifiers = sha256()
    for eid in sorted(current):
        identifiers.update((eid + "\n").encode("utf-8"))
    return {"count": len(files), "sha256": digest.hexdigest(),
            "current_count": len(current),
            "current_ids_sha256": identifiers.hexdigest()}


def _as_finding(event: dict, report_path: str) -> dict:
    return {
        "source": "Manuell observasjon (DWM)",
        "test_id": "MAN-" + event["event_id"],
        "severity": event["severity"],
        "message": event["message"],
        "context": event.get("context", ""),
        "file": event.get("file", ""),
        "lines": [],
        "source_ref": report_path,
        "requires_review": True,
        "manual_event_id": event["event_id"],
        "created_utc": event.get("created_utc", ""),
        "manual_event_sha256": event.get("event_sha256", ""),
    }


def manual_findings(work: str | Path, snapshot: dict) -> list[dict]:
    """Only findings for the exact DWM job AND original depot report revision."""
    root, uid, source_sha = _check_work_and_source(Path(work), snapshot)
    _, _, report_path = _binding(snapshot)
    return [_as_finding(e, report_path) for e in _read_manual(root)
            if e.get("job_uid") == uid and e.get("depot_report_sha256") == source_sha]


def record_manual_finding(work: str | Path, snapshot: dict, *,
                          severity: str, message: str, context: str = "",
                          file: str = "", user: Any) -> dict:
    """Record a human observation; its severity is NOT a machine test result."""
    severity = str(severity or "").strip().upper()
    message = str(message or "").strip()
    context = str(context or "").strip()
    file = str(file or "").strip()
    if severity not in SEVERITIES:
        raise ReviewError("Ukjent avviksnivå")
    if not message or len(message) > MAX_DESCRIPTION:
        raise ReviewError("Beskrivelse er påkrevd (maksimalt 3000 tegn)")
    if len(context) > 1500 or len(file) > 1024:
        raise ReviewError("Kontekst eller kildefelt er for langt")
    if not hasattr(user, "as_dict") or not callable(user.as_dict) or not getattr(user, "user_id", None):
        raise ReviewError("Registrert brukerprofil kreves")
    author = user.as_dict()
    if not isinstance(author, dict):
        raise ReviewError("Ugyldig brukerprofil")
    root, uid, source_sha = _check_work_and_source(Path(work), snapshot)
    event_id = str(uuid4())
    event = {
        "model_id": MANUAL_MODEL,
        "event_id": event_id,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "recorded_ns": time.time_ns(),
        "job_uid": uid,
        "depot_report_sha256": source_sha,
        "severity": severity,
        "message": message,
        "context": context,
        "file": file,
        "author": author,
        "origin": "human_observation_not_machine_validation",
    }
    event["event_sha256"] = sha256(_canonical(event)).hexdigest()
    raw = json.dumps(event, ensure_ascii=False, indent=2) + "\n"
    if len(raw.encode("utf-8")) > MAX_BYTES:
        raise ReviewError("Avviksdata er for store")
    folder = _manual_dir(root, create=True)
    with (folder / (event_id + ".json")).open("x", encoding="utf-8") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return event


def _verified_raf_candidates(work: Path, snapshot: dict) -> list[dict]:
    """Flag only historic RAF 'Ikke gyldig', never pretend it is current policy.

    Candidate rows must be in the SHA-verified canonical external manifest and
    belong to the selected Arkade import.  Unknown/older imports are skipped.
    """
    selected = str((snapshot.get("arkade") or {}).get("source") or "")
    if not selected:
        return []
    prefix = "/".join(selected.replace("\\", "/").split("/")[:-2]) + "/"
    candidates = [entry for entry in snapshot.get("evidence_manifest") or []
                  if entry.get("kind") == "external"
                  and str(entry.get("path") or "").replace("\\", "/").startswith(prefix)
                  and str(entry.get("path") or "").replace("\\", "/").endswith("/pronom_statistics.json")]
    if len(candidates) != 1:
        return []
    entry = candidates[0]
    path = _rel(work, str(entry["path"]))
    if _hash(path) != entry.get("sha256"):
        raise ReviewError("PRONOM-kildefilen har endret seg")
    doc = _json(path, MAX_JSON)
    if doc.get("evidence_type") != "arkade5_pronom_format_statistics":
        return []
    rows = (doc.get("csv") or {}).get("rows") or []
    # The containing JSON already has a separately enforced size bound.
    # Its row count is not a validity criterion; legitimate large PRONOM
    # statistics must not be discarded at an arbitrary 2,500 rows.
    if not isinstance(rows, list):
        raise ReviewError("Ugyldig lagret PRONOM-statistikk")
    results = []
    for item in rows:
        if not isinstance(item, dict) or str(item.get("RAF-220301") or "").casefold() != "ikke gyldig":
            continue
        puid = str(item.get("Format-ID") or "").strip()
        count = str(item.get("Antall") or "").strip()
        if not puid or not count.isdecimal():
            continue
        results.append({
            "source": "Arkade 5 – historisk RAF-220301 (PRONOM)",
            "test_id": "RAF-220301:" + puid,
            "severity": "REVIEW",
            "message": "Historisk RAF-220301: Ikke gyldig – " + puid + ". Filobservasjoner: " + count + ". "
                       "Vurder mot dagens valgt regelprofil separat; ikke automatisk filfeil.",
            "context": str(item.get("Filtype") or "") + " / " + str(item.get("Formatversjon") or "Ukjent"),
            "file": str((doc.get("source") or {}).get("original_name") or ""),
            "lines": [],
            "source_ref": str(entry["path"]),
            "requires_review": True,
        })
    return results


def _dwm_unfinished_or_failed(work: Path, snapshot: dict) -> list[dict]:
    """Surface non-OK DWM XPath outcomes, which a12 otherwise only counts.

    A non-completed test is a review item, never a successful validation.
    The source is the same SHA-bound original depot report as the snapshot.
    """
    _, _, report_rel = _binding(snapshot)
    coverage = snapshot.get('control_coverage') or {}
    if coverage.get('model_id') == 'dwm.noark5.qa-control-coverage.v023-a18.v1':
        dwm = coverage.get('dwm_xpath') or {}
        # A18: these rows were already authenticated against the streamed
        # XPath master and depot report. Do NOT reopen a 24+ MiB report.
        tests = dwm.get('non_ok_reported_tests') or []
        missing = dwm.get('missing_from_depot_report') or []
    else:
        report = _json(_rel(work, report_rel), MAX_DEPO)
        tests = ((report.get("technical_validation") or {}).get("tests") or [])
        missing = []
    if not isinstance(tests, list) or len(tests) > 5000:
        raise ReviewError("Ugyldig DWM-kontrolltabell")
    found = []
    for test in tests:
        if not isinstance(test, dict):
            continue
        status = str(test.get("status") or "").strip().lower()
        if status in ("", "ok", "pass", "passed", "success", "legacy_disabled"):
            continue
        test_id = str(test.get("test_id") or test.get("legacy_job_id") or "").strip()
        if not test_id:
            continue
        severity = ("ERROR" if status in ("error", "fail", "failed") else
                    "WARNING" if status in ("warning", "warn") else "REVIEW")
        found.append({
            "source": "DWM – XPath-kontroll (lagret teknisk resultat)",
            "test_id": test_id,
            "severity": severity,
            "message": "DWM-kontroll har status " + status + ". Undersøk kildetesten og årsaken; "
                       "ikke tolket som automatisk depotvedtak.",
            "context": str(test.get("test_point") or ""),
            "file": "", "lines": [], "source_ref": report_rel,
            "requires_review": True,
        })
    if missing:
        found.append({
            'source': 'DWM – avstemming av XPath-kontroller',
            'test_id': 'dwm.master_not_reported_in_depot',
            'severity': 'REVIEW',
            'message': str(len(missing)) + ' tester i XPath-master mangler i depotrapportens testtabell.',
            'context': ', '.join(str(x) for x in missing[:30]),
            'file': '', 'lines': [], 'source_ref': report_rel,
            'requires_review': True,
        })
    return found


def attach_a3_findings(work: str | Path, snapshot: dict) -> dict:
    """Augment, don't modify original DWM/Arkade results."""
    merged = dict(snapshot)
    existing = list(snapshot.get("findings") or [])
    added = (manual_findings(work, snapshot)
             + _dwm_unfinished_or_failed(Path(work), snapshot)
             + _verified_raf_candidates(Path(work), snapshot))
    keys = {finding_key(f) for f in existing}
    for finding in added:
        key = finding_key(finding)
        if key not in keys:
            existing.append(finding)
            keys.add(key)
    merged["findings"] = existing
    if "full_finding_count" in merged:
        merged["full_finding_count"] += len(existing) - len(snapshot.get("findings") or [])
    merged["a3_finding_summary"] = {
        "original_findings": len(snapshot.get("findings") or []),
        "manual_findings": sum("manual_event_id" in f for f in added),
        "historic_raf_review_candidates": sum(f["source"].startswith("Arkade 5 – historisk") for f in added),
        "dwm_non_ok_tests": sum(f["source"].startswith("DWM – XPath") for f in added),
        "total_findings": len(existing),
        "note": "Funn inkluderer manuelle observasjoner og eventuelle kildebelagte historiske RAF-vurderingspunkter; ingen automatisk godkjenning.",
    }
    return merged


def build_review_snapshot_v022_a3(*, work: str | Path, depot_report: str | None = None,
                                   kdrs_qa: str | Path | None = None,
                                   arkade_evidence: str | None = None) -> dict:
    """Use the established a12/a13/a14/a15 reporting and review models."""
    from .qa_context_v021_a14 import enrich_snapshot
    from .qa_checklist_v021_a15 import attach_checklist
    work = Path(work)
    # The ordinary 10-step workflow does not create the optional canonical
    # projection.  In its absence, read the exact Work/depot/master/import
    # files without writing a surrogate canonical file or re-running tests.
    canonical = _rel(work.resolve(strict=True), "noark5_evidence/canonical-results.json")
    builder = build_snapshot if canonical.is_file() else build_saved_work_snapshot
    base = builder(work=work, depot_report=depot_report,
                   kdrs_qa=Path(kdrs_qa) if kdrs_qa else None,
                   arkade_evidence=arkade_evidence)
    extended = attach_a3_findings(work, attach_delivery_to_snapshot(work, base))
    reviewed = with_selected_reviews(work, extended)
    enriched = enrich_snapshot(work, reviewed)
    return attach_checklist(work, enriched)


def finding_summary(work: str | Path, snapshot: dict) -> dict:
    """A review-status summary without conflating QA with technical PASS."""
    reviews = latest_reviews(work, snapshot)["current"]
    findings = list(snapshot.get("findings") or [])
    return {
        "total": len(findings),
        "reviewed": sum(finding_key(f) in reviews for f in findings),
        "unreviewed": sum(finding_key(f) not in reviews for f in findings),
        "errors": sum(f.get("severity") == "ERROR" for f in findings),
        "warnings": sum(f.get("severity") == "WARNING" for f in findings),
        "review_points": sum(f.get("severity") == "REVIEW" for f in findings),
        "manual": sum("manual_event_id" in f for f in findings),
        "automatic_approval": False,
    }
