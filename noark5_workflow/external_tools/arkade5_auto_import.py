from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from noark5_workflow.external_evidence.arkade5 import (
    import_arkade5_report,
    list_arkade5_imports,
)
from noark5_workflow.external_evidence.arkade5_pronom import (
    attach_arkade5_pronom_evidence,
)
from noark5_workflow.core.work_paths import resolve_dwm_work_root
from .arkade5_jobs import (
    ARKADE5_NOARK5,
    ARKADE5_PRONOM,
    Arkade5BatchRunSummary,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()




_MONTHS_NO = {
    "januar": 1, "februar": 2, "mars": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12,
}


def _arkade_testing_date(report_path: Path) -> str:
    """Return YYYYMMDD from Arkade Summary DateOfTesting/TimeOfTesting."""
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return ""
    summary = payload.get("Summary") if isinstance(payload, dict) else None
    if not isinstance(summary, dict):
        return ""
    raw = str(summary.get("DateOfTesting") or summary.get("TimeOfTesting") or "").strip()
    if not raw:
        return ""
    match = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", raw)
    if match:
        year, month, day = map(int, match.groups())
        return f"{year:04d}{month:02d}{day:02d}"
    match = re.search(r"(\d{1,2})\.?\s+([A-Za-zæøåÆØÅ]+)\s+(\d{4})", raw)
    if match:
        day = int(match.group(1))
        month = _MONTHS_NO.get(match.group(2).casefold())
        year = int(match.group(3))
        if month:
            return f"{year:04d}{month:02d}{day:02d}"
    return ""


def _repair_undated_import(manifest: dict, *, report_path: Path, dwm_work: Path) -> dict:
    """Migrate an auto-import from undated-* when Arkade exposes TimeOfTesting.

    Arkade 5 v2.13.1 uses Summary.TimeOfTesting.  The older importer still
    understands DateOfTesting, so this compatibility step keeps the source hash
    untouched while giving the DWM import its real test date.
    """
    old_id = str(manifest.get("import_id") or "")
    if not old_id.startswith("undated-"):
        return manifest
    date = _arkade_testing_date(report_path)
    if not date:
        return manifest
    suffix = old_id.split("-", 1)[1]
    new_id = f"{date}-{suffix}"
    root = dwm_work / "external_evidence" / "arkade5"
    old_root = root / old_id
    new_root = root / new_id
    if old_root.is_dir() and old_root != new_root:
        if new_root.exists():
            shutil.rmtree(old_root)
        else:
            old_root.rename(new_root)

    def replace_id(value):
        if isinstance(value, str):
            return value.replace(old_id, new_id)
        if isinstance(value, dict):
            return {k: replace_id(v) for k, v in value.items()}
        if isinstance(value, list):
            return [replace_id(v) for v in value]
        return value

    manifest = replace_id(dict(manifest))
    manifest["import_id"] = new_id
    source_summary = manifest.get("source_summary")
    if isinstance(source_summary, dict) and not source_summary.get("date_of_testing"):
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8-sig"))
            raw_summary = payload.get("Summary") if isinstance(payload, dict) else {}
            raw_time = str((raw_summary or {}).get("TimeOfTesting") or "").strip()
            if raw_time:
                source_summary["date_of_testing"] = raw_time
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass

    manifest_path = new_root / "manifest.json"
    if manifest_path.parent.is_dir():
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    normalized_file = manifest.get("normalized_file")
    if normalized_file:
        normalized_path = dwm_work / str(normalized_file)
        try:
            normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
            summary = normalized.get("summary") if isinstance(normalized, dict) else None
            if isinstance(summary, dict) and not summary.get("date_of_testing"):
                raw_time = str(((summary.get("source_raw") or {}).get("TimeOfTesting") or "")).strip()
                if raw_time:
                    summary["date_of_testing"] = raw_time
                    normalized_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass
    return manifest


def _record_detailed_pronom_inventory(*, dwm_work: Path, import_id: str, output_dir: Path) -> None:
    """Record Arkade's detailed filformatinfo as present but intentionally not imported."""
    inventory = output_dir / "filformatinfo"
    if not inventory.is_file() or not import_id:
        return
    manifest_path = dwm_work / "external_evidence" / "arkade5" / import_id / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return
    evidence = manifest.setdefault("pronom_evidence", {})
    detailed = evidence.setdefault("detailed_file_inventory", {})
    detailed.update({
        "found": True,
        "imported": False,
        "original_name": inventory.name,
        "original_path": str(inventory),
        "size_bytes": inventory.stat().st_size,
        "sha256": _sha256(inventory),
    })
    detailed.setdefault(
        "policy",
        "Dokumenteres som eksisterende kilde, men importeres ikke i dette inkrementet. "
        "Filnivådata håndteres senere fordi dokumentfiler kan forekomme i flere generasjoner/representasjoner.",
    )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _existing_by_sha(work_operations: Path) -> dict[str, dict]:
    return {
        str((row.get("source") or {}).get("sha256") or "").casefold(): row
        for row in list_arkade5_imports(work_operations)
        if str((row.get("source") or {}).get("sha256") or "").strip()
    }


def _latest_import_id(work_operations: Path) -> str:
    rows = list_arkade5_imports(work_operations)
    if not rows:
        return ""
    return str(rows[0].get("import_id") or "")


def _pronom_anchor(output_dir: Path) -> Path | None:
    """Return a file in the PRONOM output directory for the existing attach API.

    ``attach_arkade5_pronom_evidence`` searches the parent directory of the
    supplied path.  Supplying the generated statistics file therefore keeps
    the existing import format intact while allowing a26.8's separate
    ``noark5`` and ``pronom`` Arkade output folders.
    """
    patterns = (
        "*filformatinfo-statistikk*.csv",
        "*filformatinfo*.csv",
    )
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(path for path in output_dir.glob(pattern) if path.is_file())
        if candidates:
            break
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


@dataclass(frozen=True)
class Arkade5AutoImportItem:
    job_id: str
    kind: str
    status: str
    source: str = ""
    import_id: str = ""
    message: str = ""


@dataclass(frozen=True)
class Arkade5AutoImportSummary:
    reports_found: int
    imported: int
    already_imported: int
    failed: int
    pronom_attached: int
    pronom_unattached: int
    pronom_failed: int
    items: tuple[Arkade5AutoImportItem, ...]

    @property
    def successful_changes(self) -> int:
        return self.imported + self.pronom_attached


def import_arkade5_run_outputs(
    summary: Arkade5BatchRunSummary,
    *,
    on_progress: Callable[[str], None] | None = None,
) -> Arkade5AutoImportSummary:
    """Import evidence produced by the exact Arkade CLI runs in ``summary``.

    No filesystem-wide correlation is performed.  The Noark report paths were
    captured by the runner as newly created by that invocation, so DWM can bind
    the evidence directly to the job/work area that launched Arkade.
    """
    items: list[Arkade5AutoImportItem] = []
    import_ids_by_job: dict[str, list[str]] = {}
    existing_cache: dict[str, dict[str, dict]] = {}

    def progress(text: str) -> None:
        if on_progress is not None:
            on_progress(text)

    def existing(work: Path) -> dict[str, dict]:
        dwm_work = resolve_dwm_work_root(work)
        key = str(dwm_work.resolve()).casefold()
        if key not in existing_cache:
            existing_cache[key] = _existing_by_sha(dwm_work)
        return existing_cache[key]

    # First import only the new Noark reports generated by these exact runs.
    for row in summary.runs:
        plan = row.plan
        if not row.ok or plan is None or plan.operation != ARKADE5_NOARK5:
            continue
        reports = tuple(Path(path) for path in row.generated_reports)
        if not reports:
            items.append(
                Arkade5AutoImportItem(
                    job_id=plan.job_id,
                    kind="noark5",
                    status="no_new_report",
                    message="Arkade-kjøringen fullførte, men DWM fant ingen ny Noark 5 JSON-rapport fra denne kjøringen.",
                )
            )
            continue

        for report in reports:
            progress(f"Importerer nytt Arkade 5-resultat for {plan.job_id}: {report.name} …")
            try:
                digest = _sha256(report).casefold()
                known = existing(plan.work_operations)
                manifest = known.get(digest)
                if manifest is None:
                    dwm_work = resolve_dwm_work_root(plan.work_operations)
                    manifest = import_arkade5_report(
                        report,
                        work_operations=dwm_work,
                        imported_by={
                            "mode": "arkade5_cli_auto_import",
                            "job_id": plan.job_id,
                            "run_id": plan.run_id,
                            "tool_version": plan.tool_version,
                        },
                    )
                    manifest = _repair_undated_import(
                        manifest, report_path=report, dwm_work=dwm_work
                    )
                    manifest_digest = str((manifest.get("source") or {}).get("sha256") or digest).casefold()
                    if manifest_digest:
                        known[manifest_digest] = manifest
                    status = "imported"
                else:
                    status = "already_imported"

                import_id = str(manifest.get("import_id") or "")
                if import_id:
                    import_ids_by_job.setdefault(plan.job_id, []).append(import_id)
                items.append(
                    Arkade5AutoImportItem(
                        job_id=plan.job_id,
                        kind="noark5",
                        status=status,
                        source=str(report),
                        import_id=import_id,
                    )
                )
            except Exception as exc:
                items.append(
                    Arkade5AutoImportItem(
                        job_id=plan.job_id,
                        kind="noark5",
                        status="failed",
                        source=str(report),
                        message=str(exc),
                    )
                )

    # Then attach PRONOM evidence to the import created by the same job/run.
    # For a PRONOM-only run, reuse the newest existing Arkade import for that
    # job if one exists; otherwise leave it explicitly unattached.
    for row in summary.runs:
        plan = row.plan
        if not row.ok or plan is None or plan.operation != ARKADE5_PRONOM:
            continue

        import_ids = list(dict.fromkeys(import_ids_by_job.get(plan.job_id, ())))
        if not import_ids:
            latest = _latest_import_id(resolve_dwm_work_root(plan.work_operations))
            if latest:
                import_ids = [latest]

        anchor = _pronom_anchor(plan.output_dir)
        if not import_ids or anchor is None:
            reason = (
                "Ingen Arkade-import finnes å koble PRONOM-resultatet til."
                if not import_ids
                else "Fant ingen PRONOM-statistikkfil i Arkade-output."
            )
            items.append(
                Arkade5AutoImportItem(
                    job_id=plan.job_id,
                    kind="pronom",
                    status="unattached",
                    source=str(plan.output_dir),
                    message=reason,
                )
            )
            continue

        # One PRONOM run represents the same extraction. Attach it to the
        # newest import produced/selected for this job, not to historical runs.
        import_id = import_ids[0]
        progress(f"Kobler PRONOM-resultat til Arkade-evidens for {plan.job_id} …")
        try:
            result = attach_arkade5_pronom_evidence(
                anchor,
                work_operations=resolve_dwm_work_root(plan.work_operations),
                import_id=import_id,
            )
            attached = bool(result.get("statistics_imported"))
            _record_detailed_pronom_inventory(
                dwm_work=resolve_dwm_work_root(plan.work_operations),
                import_id=import_id,
                output_dir=plan.output_dir,
            )
            items.append(
                Arkade5AutoImportItem(
                    job_id=plan.job_id,
                    kind="pronom",
                    status="attached" if attached else "unattached",
                    source=str(plan.output_dir),
                    import_id=import_id,
                    message="" if attached else str(result.get("status") or "PRONOM-statistikk ble ikke importert."),
                )
            )
        except Exception as exc:
            items.append(
                Arkade5AutoImportItem(
                    job_id=plan.job_id,
                    kind="pronom",
                    status="failed",
                    source=str(plan.output_dir),
                    import_id=import_id,
                    message=str(exc),
                )
            )

    result = Arkade5AutoImportSummary(
        reports_found=sum(item.kind == "noark5" and bool(item.source) for item in items),
        imported=sum(item.status == "imported" for item in items),
        already_imported=sum(item.status == "already_imported" for item in items),
        failed=sum(item.status == "failed" for item in items),
        pronom_attached=sum(item.kind == "pronom" and item.status == "attached" for item in items),
        pronom_unattached=sum(item.kind == "pronom" and item.status == "unattached" for item in items),
        pronom_failed=sum(item.kind == "pronom" and item.status == "failed" for item in items),
        items=tuple(items),
    )
    progress(
        "Automatisk Arkade-import ferdig: "
        f"{result.imported} nye rapport(er), {result.already_imported} allerede importert, "
        f"{result.pronom_attached} PRONOM koblet, {result.failed + result.pronom_failed} feil."
    )
    return result
