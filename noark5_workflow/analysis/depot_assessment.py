from __future__ import annotations

import hashlib
import json
import os
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from noark5_workflow.core.identity import UserIdentity


ASSESSMENT_STATUSES = (
    "accepted",
    "accepted_with_deviation",
    "requires_clarification",
    "new_extraction_required",
)
ASSESSMENT_FORMAT_VERSION = 1


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Forventet JSON-objekt i {path}.")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _timestamp(value: str | None = None) -> str:
    if value:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError("assessed_at må inneholde tidssone.")
        return parsed.isoformat(timespec="seconds")
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _validate_report(model: dict[str, Any], report_path: Path) -> None:
    if model.get("report_type") != "noark5_depot_validation":
        raise ValueError(f"{report_path} er ikke en Noark 5-depotvalideringsrapport.")
    if "assessment" not in model:
        raise ValueError(f"{report_path} mangler assessment-seksjon.")


def assessment_path_for(report_path: str | Path) -> Path:
    report_path = Path(report_path)
    return report_path.with_name("depot_assessment.json")


def assessed_report_path_for(report_path: str | Path) -> Path:
    report_path = Path(report_path)
    return report_path.with_name("depot_validation_report.assessed.json")


def assessed_html_path_for(report_path: str | Path) -> Path:
    report_path = Path(report_path)
    return report_path.with_name("depot_validation_report.assessed.html")


def load_depot_assessment(report_path: str | Path) -> dict[str, Any] | None:
    report_path = Path(report_path)
    assessment_path = assessment_path_for(report_path)
    if not assessment_path.is_file():
        return None

    stored = _read_json(assessment_path)
    current_hash = _sha256(report_path)
    stored_hash = str(stored.get("report", {}).get("sha256", ""))
    if not stored_hash or stored_hash != current_hash:
        raise ValueError(
            "Lagret depotvurdering tilhører ikke gjeldende rapportinnhold. "
            "Rapporten kan være erstattet eller endret."
        )
    return stored


def materialize_assessed_report(
    report_path: str | Path,
    assessment_document: dict[str, Any],
    *,
    render_html: bool = True,
) -> tuple[Path, Path | None]:
    report_path = Path(report_path)
    model = _read_json(report_path)
    _validate_report(model, report_path)

    current = assessment_document.get("current") or {}
    if not current:
        raise ValueError("Vurderingsdokumentet mangler current-vurdering.")

    assessed = deepcopy(model)
    existing = dict(assessed.get("assessment") or {})
    existing.update(
        {
            "status": current["status"],
            "automatic_decision": False,
            "reason": current["reason"],
            "reviewed_at": current["assessed_at"],
            "reviewed_by": current["user"],
            "assessment_id": current["assessment_id"],
        }
    )
    assessed["assessment"] = existing
    assessed["assessment_evidence"] = {
        "format_version": ASSESSMENT_FORMAT_VERSION,
        "report_sha256": assessment_document["report"]["sha256"],
        "assessment_file": str(assessment_path_for(report_path)),
        "history_count": len(assessment_document.get("history", [])),
    }

    json_path = assessed_report_path_for(report_path)
    _atomic_write_json(json_path, assessed)

    html_path: Path | None = None
    if render_html:
        from noark5_workflow.analysis.depot_report_builder import write_depot_report_html

        html_path = assessed_html_path_for(report_path)
        write_depot_report_html(assessed, html_path)

    return json_path, html_path


def record_depot_assessment(
    report_path: str | Path,
    *,
    status: str,
    reason: str,
    user: UserIdentity,
    assessed_at: str | None = None,
    render_html: bool = True,
) -> dict[str, Any]:
    report_path = Path(report_path)
    if not report_path.is_file():
        raise FileNotFoundError(report_path)
    if status not in ASSESSMENT_STATUSES:
        raise ValueError(
            f"Ugyldig vurderingsstatus {status!r}. "
            f"Tillatte verdier: {', '.join(ASSESSMENT_STATUSES)}."
        )
    reason = str(reason or "").strip()
    if not reason:
        raise ValueError("Depotets faglige vurdering må ha en begrunnelse.")
    if not isinstance(user, UserIdentity) or not user.user_id:
        raise ValueError("Depotvurdering krever en gyldig UserIdentity.")

    model = _read_json(report_path)
    _validate_report(model, report_path)
    report_hash = _sha256(report_path)
    sidecar = assessment_path_for(report_path)

    document: dict[str, Any]
    if sidecar.is_file():
        document = _read_json(sidecar)
        existing_hash = str(document.get("report", {}).get("sha256", ""))
        if existing_hash != report_hash:
            raise ValueError(
                "Eksisterende depotvurdering peker på en annen rapportversjon. "
                "Vurderingen blir ikke overskrevet."
            )
    else:
        document = {
            "depot_assessment_format_version": ASSESSMENT_FORMAT_VERSION,
            "report": {
                "filename": report_path.name,
                "sha256": report_hash,
                "report_type": model.get("report_type"),
                "source_presentation_file": model.get("evidence", {}).get(
                    "source_presentation_file"
                ),
            },
            "history": [],
        }

    entry = {
        "assessment_id": uuid.uuid4().hex,
        "status": status,
        "reason": reason,
        "assessed_at": _timestamp(assessed_at),
        "user": user.as_dict(),
    }
    document.setdefault("history", []).append(entry)
    document["current"] = entry
    _atomic_write_json(sidecar, document)

    assessed_json, assessed_html = materialize_assessed_report(
        report_path,
        document,
        render_html=render_html,
    )
    return {
        "assessment_file": str(sidecar),
        "assessed_report_json": str(assessed_json),
        "assessed_report_html": str(assessed_html) if assessed_html else None,
        "assessment": entry,
        "history_count": len(document["history"]),
    }


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
