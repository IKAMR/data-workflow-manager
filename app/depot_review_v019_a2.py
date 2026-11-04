"""Depot review workbench, independent of Qt and of the job-list file.

Reads an exact, immutable Work-local Noark 5 report. Reuses the established
whole-extraction depot assessment and period review services. Adds a separate
version-bound archive-part decision journal, keyed ONLY by native system-ID.
A completed workflow or a generated report is NEVER a professional approval.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

PART_FORMAT_VERSION = 1
PART_FILE = "depot_assessment_parts.json"
MAX_REPORT_BYTES = 16_000_000
MAX_DECISIONS_BYTES = 8_000_000
STATUS_LABELS = {
    "accepted": "Akseptert",
    "accepted_with_deviation": "Akseptert med avvik",
    "requires_clarification": "Krever avklaring",
    "new_extraction_required": "Nytt uttrekk kreves",
}


@dataclass(frozen=True)
class DepotReviewRow:
    job_uid: str
    job_id: str
    job_name: str
    native_id: str
    scope: str
    title: str
    report_path: Path | None
    technical_status: str
    professional_status: str
    period_status: str
    deviation_count: int | None
    updated_at: str
    history_count: int
    editable: bool
    details: dict[str, Any]
    warning: str = ""

    @property
    def key(self) -> tuple[str, str]:
        return (self.job_uid, self.native_id)


def _original_report(path: Path) -> dict[str, Any]:
    if path.name != "depot_validation_report.json" or not path.is_file():
        raise ValueError("Velg en original depotvalideringsrapport i Work.")
    if path.stat().st_size > MAX_REPORT_BYTES:
        raise ValueError("Rapporten er for stor for direkte depotvurdering.")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or data.get("report_type") != "noark5_depot_validation":
        raise ValueError("Filen er ikke en Noark 5-depotvalideringsrapport.")
    return data


def _hash_file(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1_048_576), b""):
            value.update(block)
    return value.hexdigest()


def _verified_report(work: Path, raw: Path | None) -> Path | None:
    if not raw:
        return None
    try:
        base = Path(work).resolve(strict=True)
        report = Path(raw).resolve(strict=True)
        if report.is_relative_to(base) and report.is_file() and report.name == "depot_validation_report.json":
            return report
    except (OSError, ValueError, RuntimeError):
        pass
    return None


def _native_part(data: dict[str, Any], system_id: str) -> dict[str, Any]:
    # An ordinal, title or KDRS U2 index is not an archive-part identity.
    matched = [part for part in data.get("archive_parts", ())
               if isinstance(part, dict)
               and str((part.get("archive_part") or {}).get("system_id") or "") == system_id]
    if len(matched) != 1:
        raise ValueError("Arkivdelens system-ID mangler, er duplisert eller finnes ikke i rapporten.")
    return matched[0]


def _part_id(value: str) -> str:
    result = str(value or "").strip()
    if not result or result in (".", "..") or len(result) > 256 or any(ord(c) < 32 for c in result):
        raise ValueError("Ugyldig arkivdel system-ID.")
    return result


def load_part_decisions(report_path: str | Path) -> dict[str, Any] | None:
    """Return decisions only for this exact, byte-identical report revision."""
    path = Path(report_path)
    sidecar = path.with_name(PART_FILE)
    if not sidecar.exists():
        return None
    if not sidecar.is_file() or sidecar.is_symlink() or sidecar.stat().st_size > MAX_DECISIONS_BYTES:
        raise ValueError("Lagret arkivdelvurdering har utrygg plassering eller st\u00f8rrelse.")
    document = json.loads(sidecar.read_text(encoding="utf-8-sig"))
    if (not isinstance(document, dict) or document.get("format_version") != PART_FORMAT_VERSION
            or not isinstance(document.get("parts"), dict)):
        raise ValueError("Ukjent format for arkivdelvurdering.")
    for key, value in document["parts"].items():
        if (not isinstance(key, str) or not isinstance(value, dict)
                or not isinstance(value.get("current"), dict)
                or not isinstance(value.get("history"), list)):
            raise ValueError("Arkivdelhistorikken har ugyldig innhold.")
    binding = document.get("report") or {}
    if binding.get("sha256") != _hash_file(path) or binding.get("filename") != path.name:
        raise ValueError("Arkivdelvurderingene gjelder en annen rapportversjon. Historikk er bevart.")
    return document


def record_part_decision(report_path: str | Path, system_id: str, *, status: str,
                         reason: str, user, assessed_at: str | None = None,
                         job_uid: str = "") -> dict[str, Any]:
    """Explicit audited decision for one native part, never the entire extraction.

    Uses the same four depot statuses and UserIdentity as the established
    whole-extraction assessment. Existing history and other parts are retained.
    No original report, Source, AIP or .n5jobs file is modified.
    """
    from noark5_workflow.analysis.depot_assessment import ASSESSMENT_STATUSES
    from noark5_workflow.core.identity import UserIdentity

    report = Path(report_path).resolve(strict=True)
    data = _original_report(report)
    identity = _part_id(system_id)
    part = _native_part(data, identity)
    if status not in ASSESSMENT_STATUSES:
        raise ValueError("Ugyldig depotvurderingsstatus.")
    note = str(reason or "").strip()
    if not note:
        raise ValueError("Faglig depotvurdering krever en begrunnelse.")
    if not isinstance(user, UserIdentity) or not user.user_id:
        raise ValueError("Faglig depotvurdering krever registrert brukeridentitet.")
    if assessed_at:
        moment = datetime.fromisoformat(assessed_at)
        if moment.tzinfo is None:
            raise ValueError("Vurderingstidspunktet m\u00e5 inneholde tidssone.")
    else:
        moment = datetime.now(timezone.utc)
    document = load_part_decisions(report)
    if document is None:
        document = {
            "format_version": PART_FORMAT_VERSION,
            "report": {"filename": report.name, "sha256": _hash_file(report),
                       "run_id": str(data.get("run_id") or ""), "job_uid": str(job_uid or "")},
            "parts": {},
        }
    if job_uid:
        stored_uid = str((document.get("report") or {}).get("job_uid") or "")
        if stored_uid and stored_uid != str(job_uid):
            raise ValueError("Arkivdelhistorikken tilhører en annen Work-jobbidentitet.")
        document["report"]["job_uid"] = str(job_uid)
    parts = document["parts"]
    previous = parts.get(identity) or {}
    entry = {
        "assessment_id": uuid4().hex,
        "status": status,
        "reason": note,
        "assessed_at": moment.isoformat(timespec="seconds"),
        "user": user.as_dict(),
    }
    history = list(previous.get("history") or [])
    history.append(entry)
    parts[identity] = {
        "system_id": identity,
        "title": str((part.get("archive_part") or {}).get("title") or identity),
        "current": entry,
        "history": history,
    }
    sidecar = report.with_name(PART_FILE)
    if sidecar.is_symlink():
        raise ValueError("Kan ikke overskrive en symbolsk lenke til vurderingsfil.")
    temp = sidecar.with_name("." + sidecar.name + "." + uuid4().hex + ".tmp")
    try:
        with temp.open("x", encoding="utf-8") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, sidecar)
    finally:
        if temp.exists():
            temp.unlink()
    return {"file": sidecar, "current": entry, "history_count": len(history)}


def _years(entry: Any) -> str:
    if not isinstance(entry, dict):
        return "Ukjent"
    span = entry.get("span") if isinstance(entry.get("span"), dict) else entry
    start = span.get("first_year", span.get("start_year"))
    end = span.get("last_year", span.get("end_year"))
    try:
        a, b = int(start), int(end)
    except (ValueError, TypeError):
        return "Ukjent"
    return f"{a}\u2013{b}" if 1000 <= a <= b <= 9999 else "Ukjent"


def _decision_information(saved: dict[str, Any] | None) -> tuple[str, str, int, dict]:
    if not saved or not isinstance(saved.get("current"), dict):
        return "Ikke vurdert", "", 0, {}
    current = saved["current"]
    status = STATUS_LABELS.get(current.get("status"), "Ukjent status")
    return status, str(current.get("assessed_at") or ""), len(saved.get("history") or []), current


def _period_details(period: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    if not period:
        return "Ikke vurdert", {}
    item = period.get("assessment") or {}
    status = str(item.get("status") or "ikke_vurdert")
    labels = {"ikke_vurdert": "Ikke vurdert", "undersokes": "Under unders\u00f8kelse",
              "godkjent": "Godkjent periode"}
    years = item.get("selected_years")
    if status == "godkjent" and not (isinstance(years, list) and len(years) == 2):
        return "Godkjenning mangler ytter\u00e5r", item
    return labels.get(status, "Ukjent periodestatus"), item


def build_depot_review_rows(snapshots: Iterable[Any], *, sources=()) -> tuple[DepotReviewRow, ...]:
    """Aggregate read-only evidence and recorded decisions; never decide for user."""
    from app.result_evidence_v018_a13 import period_rows
    from noark5_workflow.analysis.depot_assessment import load_depot_assessment

    distinct: dict[str, Any] = {}
    for shot in snapshots:
        distinct.setdefault(str(shot.job.job_uid), shot)
    shots = tuple(distinct.values())
    periods = {(p["job"].job_uid, p["native_id"]): p for p in period_rows(shots)}
    by_job: dict[str, list[dict]] = {}
    for source in sources:
        uid = str(getattr(source, "job_uid", ""))
        by_job.setdefault(uid, []).append({
            "kilde": str(getattr(source, "source", "")),
            "import_id": str(getattr(source, "import_id", "")),
            "status": str(getattr(source, "status", "")),
            "antall": getattr(source, "count", None),
            "enhet": str(getattr(source, "unit", "")),
            "sha256": str(getattr(source, "sha256", "")),
        })
    rows: list[DepotReviewRow] = []
    for shot in shots:
        uid = str(shot.job.job_uid)
        report = _verified_report(shot.job.work, shot.results.depot_report_path)
        model = shot.depot if report and isinstance(shot.depot, dict) else None
        whole_warning = ""
        parts_warning = ""
        overall = None
        parts_doc = None
        if report and model:
            try:
                overall = load_depot_assessment(report)
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
                whole_warning = "Historisk depotvurdering kan ikke knyttes til rapporten: " + str(error)
            try:
                parts_doc = load_part_decisions(report)
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
                parts_warning = "Arkivdelhistorikk kan ikke knyttes til rapporten: " + str(error)
        if not model:
            whole_warning = "Ingen tilgjengelig depotrapport for valgt Work."
        extraction_status, changed, history, current = _decision_information(overall)
        if whole_warning and model:
            extraction_status = "Historikk krever kontroll"
        period_status, period_saved = _period_details(periods.get((uid, "")))
        reconciliation = (model or {}).get("period_reconciliation") or {}
        deviations = (model or {}).get("deviations")
        overall_deviations = [d for d in deviations if isinstance(d, dict) and d.get("requires_review")] if isinstance(deviations, list) else []
        known_deviation_count = len(overall_deviations) if isinstance(deviations, list) else None
        sources_job = by_job.get(uid, [])
        core = {
            "rapport_sha256": _hash_file(report) if report and model else "",
            "work_root": str(Path(shot.job.work).resolve(strict=False)),
            "job_uid": uid,
            "job_id": shot.job.job_id,
            "rapport": str(report) if report else None,
            "teknisk_fullf\u00f8ring_er_ikke_godkjenning": True,
            "opprinnelig_automatisk_vurdering": (model or {}).get("assessment"),
            "rapportert_oversikt": (model or {}).get("summary"),
            "periode_oppgitt": _years(reconciliation.get("declared_period")),
            "periode_observert": reconciliation.get("observed_series"),
            "vurderingspunkter": overall_deviations,
            "evidenskilder": sources_job,
            "lagret_periodevurdering": period_saved,
            "faglig_beslutning": current,
        }
        rows.append(DepotReviewRow(
            uid, str(shot.job.job_id), str(shot.job.name), "", "uttrekk", "Hele uttrekket",
            report, str(((model or {}).get("technical_validation") or {}).get("status") or "Ukjent"),
            extraction_status, period_status, known_deviation_count,
            changed, history, bool(report and model and not whole_warning), core, whole_warning,
        ))
        if not model:
            continue
        observed_by_sid = {
            str((rec.get("archive_part") or {}).get("system_id")): rec
            for rec in reconciliation.get("archive_parts", ()) if isinstance(rec, dict)
            and (rec.get("archive_part") or {}).get("system_id")
        }
        parts = [part for part in model.get("archive_parts", ()) if isinstance(part, dict)]
        id_count = {}
        for part in parts:
            sid = str((part.get("archive_part") or {}).get("system_id") or "")
            id_count[sid] = id_count.get(sid, 0) + 1
        for number, part in enumerate(parts, 1):
            meta = part.get("archive_part") or {}
            native_id = str(meta.get("system_id") or "")
            valid = bool(native_id and id_count.get(native_id) == 1)
            key = native_id if valid else f"missing:{number}"
            saved_entry = ((parts_doc or {}).get("parts") or {}).get(native_id, {}) if valid else {}
            status, updated, count, decision = _decision_information(saved_entry)
            if parts_warning:
                status = "Historikk krever kontroll"
            period_row = periods.get((uid, native_id)) if valid else None
            part_period, part_saved = _period_details(period_row)
            part_recon = observed_by_sid.get(native_id, {}) if valid else {}
            part_deviations = part.get("deviations")
            part_deviation_count = (sum(bool(item.get("requires_review")) for item in part_deviations
                                        if isinstance(item, dict))
                                    if isinstance(part_deviations, list) else None)
            part_warning = parts_warning if model else whole_warning
            if not valid:
                part_warning += (" | " if part_warning else "") + "System-ID mangler eller er ikke entydig."
            rows.append(DepotReviewRow(
                uid, str(shot.job.job_id), str(shot.job.name), key, "arkivdel",
                str(meta.get("title") or native_id or f"Arkivdel {number}"), report,
                str(part.get("status") or "Ukjent"), status, part_period,
                part_deviation_count, updated, count,
                bool(report and valid and not parts_warning),
                {
                    **core, "native_system_id": native_id if valid else None,
                    "arkivdel": part,
                    "periode_observert_arkivdel": _years(part_recon.get("observed_period")),
                    "lagret_periodevurdering": part_saved,
                    "faglig_beslutning": decision,
                    "avvik_per_arkivdel": part_deviations if isinstance(part_deviations, list) else None,
                    "overordnede_vurderingspunkter_gjelder_ikke_automatisk_arkivdelen": True,
                    "eksterne_evidenskilder_er_opptalt_paa_uttrekksnivaa": True,
                }, part_warning,
            ))
    return tuple(rows)


def record_depot_review(row: DepotReviewRow, *, status: str, reason: str, user) -> dict[str, Any]:
    """Submit one explicit human decision through its scope-specific service."""
    if not row.editable or row.report_path is None:
        raise ValueError("Vurderingen er skrivebeskyttet fordi rapporten eller identiteten er ugyldig.")
    original = row.details.get("rapport_sha256")
    if _verified_report(Path(row.details.get("work_root") or ""), row.report_path) is None:
        raise ValueError("Rapporten ligger ikke lenger innenfor det godkjente Work-området.")
    if not original or _hash_file(row.report_path) != original:
        raise ValueError("Rapportinnholdet er endret. Oppdater visningen og kontroller grunnlaget.")
    if row.scope == "uttrekk":
        from noark5_workflow.analysis.depot_assessment import record_depot_assessment
        return record_depot_assessment(row.report_path, status=status, reason=reason,
                                       user=user, render_html=True)
    if row.scope == "arkivdel" and row.native_id and not row.native_id.startswith("missing:"):
        return record_part_decision(row.report_path, row.native_id, status=status, reason=reason,
                                    user=user, job_uid=row.job_uid)
    raise ValueError("Ukjent vurderingsomfang.")
