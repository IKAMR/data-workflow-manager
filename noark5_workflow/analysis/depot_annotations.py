from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from noark5_workflow.core.identity import UserIdentity


ANNOTATION_TYPES = (
    "note",
    "deviation",
    "question",
    "follow_up",
    "accepted_deviation",
)
ANNOTATION_STATUSES = ("active", "resolved", "closed")
SCHEMA_VERSION = 1
ANNOTATIONS_FILENAME = "depot_annotations.json"


def _report_hash(report_path: Path) -> str:
    return hashlib.sha256(report_path.read_bytes()).hexdigest()


def _annotations_path(report_path: Path) -> Path:
    return report_path.with_name(ANNOTATIONS_FILENAME)


def _new_store(report_path: Path) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "report_file": report_path.name,
        "report_sha256": _report_hash(report_path),
        "annotations": [],
    }


def load_depot_annotations(report_path: str | Path) -> dict[str, Any]:
    """Load annotations bound to one exact depot report instance.

    This module has no GUI dependency. GUI, CLI and future server runtimes can
    call the same functions and therefore share one annotation contract.
    """
    report_path = Path(report_path)
    if not report_path.is_file():
        raise FileNotFoundError(f"Depotrapport finnes ikke: {report_path}")

    path = _annotations_path(report_path)
    if not path.is_file():
        return _new_store(report_path)

    store = json.loads(path.read_text(encoding="utf-8"))
    if store.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Ukjent versjon av depot_annotations.json")
    if store.get("report_sha256") != _report_hash(report_path):
        raise ValueError(
            "Kommentarene tilhører en annen versjon av depotrapporten. "
            "Rapporten må vurderes på nytt før kommentarene kan brukes."
        )
    if not isinstance(store.get("annotations"), list):
        raise ValueError("Ugyldig depot_annotations.json: annotations må være en liste")
    return store


def record_depot_annotation(
    report_path: str | Path,
    *,
    annotation_type: str,
    text: str,
    user: UserIdentity,
    view_id: str,
    target_type: str = "view",
    target_id: str = "",
    target_label: str = "",
    status: str = "active",
) -> dict[str, Any]:
    """Append one structured annotation without mutating the depot report."""
    report_path = Path(report_path)
    annotation_type = str(annotation_type or "").strip()
    text = str(text or "").strip()
    view_id = str(view_id or "").strip()
    target_type = str(target_type or "").strip() or "view"
    target_id = str(target_id or "").strip()
    target_label = str(target_label or "").strip()
    status = str(status or "").strip()

    if annotation_type not in ANNOTATION_TYPES:
        raise ValueError(f"Ukjent kommentartype: {annotation_type}")
    if status not in ANNOTATION_STATUSES:
        raise ValueError(f"Ukjent kommentarstatus: {status}")
    if not text:
        raise ValueError("Kommentaren kan ikke være tom.")
    if not view_id:
        raise ValueError("Kommentaren må knyttes til en resultatvisning.")
    if not isinstance(user, UserIdentity):
        raise ValueError("Kommentar krever gyldig brukeridentitet.")

    store = load_depot_annotations(report_path)
    annotation = {
        "annotation_id": str(uuid.uuid4()),
        "annotation_type": annotation_type,
        "status": status,
        "text": text,
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "user": user.as_dict(),
        "target": {
            "view_id": view_id,
            "target_type": target_type,
            "target_id": target_id,
            "target_label": target_label,
        },
    }
    store["annotations"].append(annotation)
    path = _annotations_path(report_path)
    path.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return annotation


def list_depot_annotations(
    report_path: str | Path,
    *,
    view_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    status: str | None = None,
    annotation_type: str | None = None,
    user_id: str | None = None,
    username: str | None = None,
    text_search: str | None = None,
) -> list[dict[str, Any]]:
    """Return annotations with optional filters; usable unchanged from GUI or CLI.

    Filters are deliberately transport-neutral. A future CLI can expose the same
    parameters without duplicating annotation-selection logic. Empty/None filters
    mean "all". Text search is case-insensitive and searches comment text plus
    the stored target label.
    """
    annotations = list(load_depot_annotations(report_path).get("annotations", []))
    search = str(text_search or "").strip().casefold()

    def matches(item: dict[str, Any]) -> bool:
        target = item.get("target") or {}
        user = item.get("user") or {}
        if view_id is not None and target.get("view_id") != view_id:
            return False
        if target_type is not None and target.get("target_type") != target_type:
            return False
        if target_id is not None and target.get("target_id") != target_id:
            return False
        if status is not None and item.get("status") != status:
            return False
        if annotation_type is not None and item.get("annotation_type") != annotation_type:
            return False
        if user_id is not None and user.get("user_id") != user_id:
            return False
        if username is not None and user.get("username") != username:
            return False
        if search:
            haystack = " ".join((
                str(item.get("text") or ""),
                str(target.get("target_label") or ""),
                str(target.get("target_id") or ""),
            )).casefold()
            if search not in haystack:
                return False
        return True

    return [item for item in annotations if matches(item)]
