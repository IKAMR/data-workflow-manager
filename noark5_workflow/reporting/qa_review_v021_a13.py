"""v0.2.1-a13: explicit, append-only professional annotations for a12 findings.

These are *annotations*, never validation results, producer acceptance, formal
approval, or rules. Every entry binds to the exact original DWM depot report
revision and to a stable fingerprint of the source finding. Old report revisions
remain in Work history but must not silently appear in a new report.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from .qa_decision_v021_a12 import _hash, _json, _rel, ReportInputError

REVIEW_DIR = "noark5_evidence/qa_review_events_v021_a13"
EVENT_MODEL = "ikamr.dwm.noark5.finding-review-event.a13.v1"
MAX_EVENTS = 2000
MAX_EVENT_BYTES = 20000
MAX_COMMENT = 5000
STATUSES = {
    "requires_clarification": "Krever avklaring",
    "context_documented": "Kontekst dokumentert",
    "acceptable_deviation": "Akseptabelt avvik - faglig merknad, ikke godkjenning",
    "not_relevant": "Ikke relevant - begrunnet",
}


class ReviewError(ValueError):
    pass


def finding_key(finding: dict[str, Any]) -> str:
    """Fingerprint a single original source finding, including its context."""
    if not isinstance(finding, dict):
        raise ReviewError("Funn er ikke et objekt")
    fields = ("source", "test_id", "severity", "message", "context", "file", "source_ref", "lines")
    canonical = {key: finding.get(key) for key in fields}
    if not canonical["source"] or not canonical["test_id"] or not canonical["message"]:
        raise ReviewError("Funn mangler nødvendig kilde, test-ID eller melding")
    value = json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256(value.encode("utf-8")).hexdigest()


def _binding(snapshot: dict) -> tuple[str, str, str]:
    if snapshot.get("model_id") != "ikamr.dwm.noark5.qa-decision.a12.v1":
        raise ReviewError("Ukjent a12-rapportgrunnlag")
    uid = str((snapshot.get("work_identity") or {}).get("job_uid") or "")
    matches = [x for x in snapshot.get("evidence_manifest") or [] if x.get("kind") == "dwm_depot"]
    if not uid or len(matches) != 1:
        raise ReviewError("Manglende jobbidentitet eller entydig depotrapport")
    row = matches[0]
    digest, path = row.get("sha256"), row.get("path")
    if not isinstance(digest, str) or len(digest) != 64 or not isinstance(path, str):
        raise ReviewError("Mangler kildeversjon for original depotrapport")
    return uid, digest, path


def _check_work_and_source(work: Path, snapshot: dict) -> tuple[Path, str, str]:
    work = Path(work).resolve(strict=True)
    uid, source_sha, relative = _binding(snapshot)
    job = _json(_rel(work, "job.json"))
    actual_uid = str(job.get("job_uid") or (job.get("job") or {}).get("job_uid") or "")
    if actual_uid != uid:
        raise ReviewError("Work-jobb stemmer ikke med valgt rapportgrunnlag")
    original = _rel(work, relative)
    if not original.is_file() or _hash(original) != source_sha:
        raise ReviewError("Depotrapporten er endret: last inn resultatgrunnlag på nytt")
    return work, uid, source_sha


def _events_directory(work: Path, *, create: bool = False) -> Path:
    root = Path(work).resolve(strict=True)
    folder = _rel(root, REVIEW_DIR)
    if folder.exists() and (not folder.is_dir() or folder.is_symlink()):
        raise ReviewError("Ugyldig katalog for faglige vurderingshendelser")
    parent = folder.parent
    if create:
        if parent.is_symlink() or not parent.is_dir():
            raise ReviewError("Mangler sikker Work/evidenskatalog")
        folder.mkdir(exist_ok=True)
    return folder


def _read_events(work: Path) -> list[dict]:
    folder = _events_directory(work)
    if not folder.exists():
        return []
    paths = list(folder.iterdir())
    if len(paths) > MAX_EVENTS:
        raise ReviewError("For mange vurderingshendelser; gjennomgå historikken")
    result = []
    for path in paths:
        if path.suffix != ".json" or not path.is_file() or path.is_symlink():
            raise ReviewError("Ukjent fil i vurderingshistorikken")
        if path.stat().st_size > MAX_EVENT_BYTES:
            raise ReviewError("Vurderingshendelse er for stor")
        event = _json(path, MAX_EVENT_BYTES)
        if event.get("model_id") != EVENT_MODEL or path.stem != event.get("event_id"):
            raise ReviewError("Ukjent eller endret vurderingshendelse")
        checksum = event.get("event_sha256")
        unsigned = {k: v for k, v in event.items() if k != "event_sha256"}
        expected = sha256(json.dumps(unsigned, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()
        if checksum != expected or type(event.get("recorded_ns")) is not int:
            raise ReviewError("Vurderingshendelsens integritet kunne ikke bekreftes")
        if event.get("status") not in STATUSES or not isinstance(event.get("comment"), str):
            raise ReviewError("Ugyldig faglig vurderingsstatus eller kommentar")
        if len(event["comment"]) > MAX_COMMENT or not event["comment"].strip():
            raise ReviewError("Ugyldig kommentar i vurderingshistorikken")
        if not all(type(event.get(flag)) is bool for flag in ("include_in_ks", "include_in_depot")):
            raise ReviewError("Ukjent rapportvalg i vurderingshistorikken")
        result.append(event)
    result.sort(key=lambda row: (row["recorded_ns"], str(row.get("event_id"))))
    return result


def latest_reviews(work: str | Path, snapshot: dict) -> dict[str, Any]:
    """Only exact source revision + exact finding fingerprints are current."""
    uid, sha, _ = _binding(snapshot)
    allowed = {finding_key(x) for x in snapshot.get("findings") or []}
    state: dict[str, dict] = {}
    older = 0
    unrelated = 0
    for event in _read_events(Path(work)):
        if event.get("job_uid") != uid:
            unrelated += 1
            continue
        if event.get("depot_report_sha256") != sha:
            older += 1
            continue
        key = event.get("finding_key")
        if key not in allowed:
            older += 1
            continue
        state[key] = event
    return {"current": state, "older_or_changed": older, "other_job": unrelated}


def record_review(work: str | Path, snapshot: dict, finding: dict, *,
                  status: str, comment: str, user: Any,
                  include_in_ks: bool = True, include_in_depot: bool = True,
                  recorded_at: str | None = None) -> dict:
    """Write one immutable Work event; never modify the existing original report."""
    if status not in STATUSES:
        raise ReviewError("Ukjent faglig vurderingsstatus")
    comment = str(comment or "").strip()
    if not comment or len(comment) > MAX_COMMENT:
        raise ReviewError("Faglig kommentar må være utfylt (maksimalt 5000 tegn)")
    if type(include_in_ks) is not bool or type(include_in_depot) is not bool:
        raise ReviewError("Ugyldig rapportvalg")
    if not hasattr(user, "as_dict") or not callable(user.as_dict) or not getattr(user, "user_id", None):
        raise ReviewError("Registrert brukerprofil er nødvendig for faglig vurdering")
    author = user.as_dict()
    if not isinstance(author, dict):
        raise ReviewError("Brukerprofil kunne ikke dokumenteres")
    key = finding_key(finding)
    if key not in {finding_key(row) for row in snapshot.get("findings") or []}:
        raise ReviewError("Funn tilhører ikke valgt rapportgrunnlag")
    root, uid, source_sha = _check_work_and_source(Path(work), snapshot)
    if recorded_at is not None:
        timestamp = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ReviewError("Vurderingstidspunktet krever tidssone")
    else:
        timestamp = datetime.now(timezone.utc)
    event_id = str(uuid4())
    event = {
        "model_id": EVENT_MODEL,
        "event_id": event_id,
        "created_utc": timestamp.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "recorded_ns": time.time_ns(),
        "job_uid": uid,
        "depot_report_sha256": source_sha,
        "finding_key": key,
        "finding_source": str(finding.get("source")),
        "test_id": str(finding.get("test_id")),
        "status": status,
        "comment": comment,
        "include_in_ks": include_in_ks,
        "include_in_depot": include_in_depot,
        "author": author,
    }
    event["event_sha256"] = sha256(json.dumps(event, ensure_ascii=False, sort_keys=True,
                                           separators=(",", ":")).encode("utf-8")).hexdigest()
    directory = _events_directory(root, create=True)
    path = directory / (event_id + ".json")
    if len(list(directory.iterdir())) >= MAX_EVENTS:
        raise ReviewError("For mange vurderingshendelser")
    raw = json.dumps(event, ensure_ascii=False, indent=2) + "\n"
    if len(raw.encode("utf-8")) > MAX_EVENT_BYTES:
        raise ReviewError("Vurderingshendelse overstiger størrelsesgrensen")
    # O_EXCL guarantees that neither an existing event nor a symlink is replaced.
    with path.open("x", encoding="utf-8") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return event


def with_selected_reviews(work: str | Path, snapshot: dict) -> dict:
    """Copy a12 evidence, adding only comments explicitly selected for a report.

    Not-selected comments stay in Work and are not included in the exported
    JSON or HTML. Original technical observations and a12 status remain intact.
    """
    details = latest_reviews(work, snapshot)
    current = details["current"]
    rows = []
    for finding in snapshot.get("findings") or []:
        key = finding_key(finding)
        event = current.get(key)
        if event and (event["include_in_ks"] or event["include_in_depot"]):
            rows.append({
                "finding_key": key,
                "test_id": event["test_id"],
                "finding_source": event["finding_source"],
                "status": event["status"],
                "comment": event["comment"],
                "created_utc": event["created_utc"],
                "author": event["author"],
                "include_in_ks": event["include_in_ks"],
                "include_in_depot": event["include_in_depot"],
                "event_id": event["event_id"],
            })
    result = deepcopy(snapshot)
    result["a13_review_rows"] = rows
    result["a13_review_summary"] = {
        "reviewed_findings": len(current),
        "selected_for_ks": sum(x["include_in_ks"] for x in rows),
        "selected_for_depot": sum(x["include_in_depot"] for x in rows),
        "historical_events_not_applied": details["older_or_changed"],
        "policy": "Faglig merknad er ikke teknisk pass, arkivskaperaksept eller formelt depotvedtak.",
    }
    return result


def review_html(snapshot: dict, *, for_depot: bool) -> str:
    """Use existing a12 HTML styling; escape all user-provided text."""
    from html import escape
    chosen = [row for row in snapshot.get("a13_review_rows") or []
              if row["include_in_depot" if for_depot else "include_in_ks"]]
    if "a13_review_summary" not in snapshot:
        return ""
    body = ["<h2>10. Valgte faglige kommentarer (a13)</h2>",
            "<p>Kommentarer er registrert av bruker og er ikke en overstyring av testresultat "
            "eller en automatisk godkjenningsbeslutning.</p>"]
    if not chosen:
        body.append("<p>Ingen faglige kommentarer er valgt for denne rapporten. "
                    "Det betyr ikke at funnene er ferdig behandlet.</p>")
    else:
        body.append("<div class='table-wrap'><table><thead><tr><th>Test / kilde</th>"
                    "<th>Faglig vurdering</th><th>Kommentar</th><th>Registrert</th></tr></thead><tbody>")
        for item in chosen:
            author = item.get("author") or {}
            actor = str(author.get("name") or author.get("display_name") or author.get("username") or author.get("user_id") or "Bruker")
            cells = (str(item["test_id"]) + " / " + str(item["finding_source"]),
                     STATUSES.get(item["status"], "Ukjent"), item["comment"],
                     actor + " · " + str(item["created_utc"]))
            body.append("<tr>" + "".join("<td>"+escape(str(x),quote=True)+"</td>" for x in cells)+"</tr>")
        body.append("</tbody></table></div>")
    summary = snapshot["a13_review_summary"]
    if summary["historical_events_not_applied"]:
        body.append("<p>Merknad: " + str(summary["historical_events_not_applied"]) +
                    " eldre vurderingshendelser gjelder andre kildeversjoner/funn og er ikke brukt.</p>")
    return "".join(body)
