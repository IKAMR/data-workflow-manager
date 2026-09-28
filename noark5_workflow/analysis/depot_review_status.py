from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
FILENAME = "depot_review_status.json"
STATUSES = ("approved", "rejected", "pending")
AREAS = ("period", "content", "documents", "formats")


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _path(report_path: Path) -> Path:
    return report_path.with_name(FILENAME)


def _new(report_path: Path) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "report_file": report_path.name,
        "report_sha256": _hash(report_path),
        "scopes": {},
        "history": [],
    }


def load_review_status(report_path: str | Path) -> dict[str, Any]:
    report_path = Path(report_path)
    if not report_path.is_file():
        raise FileNotFoundError(f"Depotrapport finnes ikke: {report_path}")
    path = _path(report_path)
    if not path.is_file():
        return _new(report_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Ukjent versjon av depot_review_status.json")
    if data.get("report_sha256") != _hash(report_path):
        raise ValueError("Vurderingsstatus tilhører en annen versjon av depotrapporten.")
    data.setdefault("scopes", {})
    data.setdefault("history", [])
    return data


def get_area_status(report_path: str | Path, *, scope_id: str, area: str) -> dict[str, Any] | None:
    if area not in AREAS:
        raise ValueError(f"Ukjent vurderingsområde: {area}")
    data = load_review_status(report_path)
    scope = (data.get("scopes") or {}).get(str(scope_id)) or {}
    value = scope.get(area)
    return dict(value) if isinstance(value, dict) else None


def set_area_status(
    report_path: str | Path,
    *,
    scope_id: str,
    scope_label: str,
    area: str,
    status: str,
    comment: str = "",
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report_path = Path(report_path)
    scope_id = str(scope_id or "").strip()
    scope_label = str(scope_label or scope_id).strip()
    status = str(status or "").strip()
    comment = str(comment or "").strip()
    if not scope_id:
        raise ValueError("Vurderingsstatus krever scope_id.")
    if area not in AREAS:
        raise ValueError(f"Ukjent vurderingsområde: {area}")
    if status not in STATUSES:
        raise ValueError(f"Ukjent vurderingsstatus: {status}")
    if status == "rejected" and not comment:
        raise ValueError("Minus-status krever kommentar.")

    data = load_review_status(report_path)
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    entry = {
        "scope_id": scope_id,
        "scope_label": scope_label,
        "area": area,
        "status": status,
        "comment": comment,
        "updated_at": now,
        "updated_by": dict(user or {}),
    }
    scopes = data.setdefault("scopes", {})
    scope = scopes.setdefault(scope_id, {})
    scope[area] = dict(entry)
    data.setdefault("history", []).append(dict(entry))
    _path(report_path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return entry
