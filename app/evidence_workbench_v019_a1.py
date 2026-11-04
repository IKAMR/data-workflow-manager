"""Read-only evidence provenance and mapped Arkade 5 / DWM coverage for Qt.

The established Work readers remain authoritative.  This module only projects
persisted results; it never reads a Noark 5 Source, performs a new analysis,
changes a job, or promotes third-party results to DWM master values.
"""
from __future__ import annotations

import csv
import html
import json
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Iterable, Mapping


@dataclass(frozen=True)
class SourceRow:
    job_uid: str
    job_label: str
    source: str
    import_id: str
    status: str
    count: int | None
    unit: str
    sha256: str
    file: Path | None
    details: dict[str, Any]


@dataclass(frozen=True)
class CoverageRow:
    job_uid: str
    job_label: str
    import_id: str
    test_id: str
    test_name: str
    arkade_status: str
    relation: str
    dwm_test_ids: tuple[str, ...]
    reason: str
    file: Path | None
    sha256: str


def _unique(snapshots: Iterable[Any]) -> tuple[Any, ...]:
    """Never double count the same Work UUID via two joblist references."""
    unique: dict[str, Any] = {}
    for shot in snapshots:
        unique.setdefault(str(shot.job.job_uid), shot)
    return tuple(unique.values())


def _work_file(shot: Any, path: Any) -> Path | None:
    """Accept only an existing regular file still located inside Work."""
    if not path:
        return None
    try:
        root = Path(shot.job.work).resolve(strict=True)
        candidate = Path(path).resolve(strict=True)
        if candidate.is_file() and candidate.is_relative_to(root):
            return candidate
    except (OSError, TypeError, ValueError, RuntimeError):
        pass
    return None


def _readers() -> dict[str, Callable[..., Any]]:
    from app.result_evidence_v018_a13 import (
        arkade_rows, kdrs_rows, pronom_rows, report_links, technical_rows,
    )
    return {
        "arkade": arkade_rows,
        "kdrs": kdrs_rows,
        "pronom": pronom_rows,
        "reports": report_links,
        "technical": technical_rows,
    }


def _label(job: Any) -> str:
    return f"{job.job_id} – {job.name}"


def _count(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    try:
        return int(str(value).strip()) if str(value).strip().isdigit() else None
    except (TypeError, ValueError):
        return None


def _group(records: Iterable[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for rec in records:
        grouped[(str(rec.get("import_id") or "Ukjent import"), str(rec.get("file") or ""))].append(rec)
    return grouped


def source_inventory(snapshots: Iterable[Any], *, readers: Mapping[str, Callable] | None = None) -> tuple[SourceRow, ...]:
    """One row per source/import/work; unknown quantities are *not* zero.

    DWM, Arkade, PRONOM and KDRS results remain distinct even if their numbers
    happen to agree.  Imported evidence is not a professional approval.
    """
    providers = readers if readers is not None else _readers()
    rows: list[SourceRow] = []
    for shot in _unique(snapshots):
        uid = str(shot.job.job_uid)
        label = _label(shot.job)
        report = shot.depot if isinstance(shot.depot, dict) else None
        technical = (report.get("technical_validation") or {}) if report else {}
        if not isinstance(technical, dict):
            technical = {}
        tests = technical.get("tests")
        report_file = _work_file(shot, getattr(shot.results, "depot_report_path", None))
        rows.append(SourceRow(
            uid, label, "DWM – tekniske kontroller", "Lagrende depotrapport",
            str(technical.get("status") or "Ukjent") if report else "Mangler rapportgrunnlag",
            len(tests) if isinstance(tests, list) else None, "tester",
            "", report_file, {"technical_validation": technical, "job_uid": uid},
        ))

        arkade = _group(providers["arkade"]((shot,)))
        for (import_id, _), items in arkade.items():
            numeric_errors = [_count(item.get("errors")) for item in items]
            errors_known = all(value is not None for value in numeric_errors)
            error_total = sum(numeric_errors) if errors_known else None
            rows.append(SourceRow(
                uid, label, "Arkade 5 – Noark 5", import_id,
                f"{error_total} rapporterte feil" if error_total is not None else "Feilantall delvis ukjent",
                len(items), "tester", str(items[0].get("source_sha256") or ""),
                _work_file(shot, items[0].get("file")),
                {"arkade_statuses": [str(item.get("status") or "Ukjent") for item in items],
                 "reported_errors": error_total, "job_uid": uid},
            ))
        if not arkade:
            rows.append(SourceRow(uid, label, "Arkade 5 – Noark 5", "–",
                                  "Ingen importert testgrunnlag", None, "tester", "", None, {}))

        pronom = _group(providers["pronom"]((shot,)))
        for (import_id, _), items in pronom.items():
            counts = [_count(item.get("count")) for item in items]
            total = sum(counts) if all(c is not None for c in counts) else None
            rows.append(SourceRow(
                uid, label, "Arkade 5 – PRONOM", import_id,
                "Formatstatistikk tilgjengelig" if total is not None else "Ufullstendig formatstatistikk",
                total, "filer", str(items[0].get("source_sha256") or ""),
                _work_file(shot, items[0].get("file")),
                {"format_rows": len(items), "job_uid": uid},
            ))
        if not pronom:
            rows.append(SourceRow(uid, label, "Arkade 5 – PRONOM", "–",
                                  "Ingen importert formatstatistikk", None, "filer", "", None, {}))

        kdrs = _group(providers["kdrs"]((shot,)))
        for (import_id, _), items in kdrs.items():
            kinds = sorted({str(item.get("report_type") or "Ukjent") for item in items})
            rows.append(SourceRow(
                uid, label, "KDRS Query", import_id, "Ekstern evidens – ikke faglig godkjent",
                len(items), "rapportreferanser", "",
                _work_file(shot, items[0].get("file")),
                {"rapporttyper": kinds,
                 "kilde_sha256": [str(item.get("sha256") or "") for item in items],
                 "job_uid": uid},
            ))
        if not kdrs:
            rows.append(SourceRow(uid, label, "KDRS Query", "–",
                                  "Ingen importert evidens", None, "rapportreferanser", "", None, {}))

        reports = providers["reports"]((shot,))
        rows.append(SourceRow(
            uid, label, "Depotrapporter", "Lagret Work",
            "Lagrede rapporter" if reports else "Ingen lagret rapport funnet",
            len(reports) if reports else None, "rapportfiler", "",
            _work_file(shot, reports[0].get("file")) if reports else None,
            {"rapportnavn": [str(item.get("filename") or "") for item in reports[:50]],
             "job_uid": uid},
        ))
    return tuple(rows)


def arkade_coverage(snapshots: Iterable[Any], *,
                    rows_reader: Callable | None = None,
                    json_reader: Callable | None = None,
                    coverage_builder: Callable | None = None) -> tuple[CoverageRow, ...]:
    """Re-use verified legacy relation mapping, never guess from N5 IDs.

    All normalized inputs must be read from the selected Work only.
    """
    if rows_reader is None or json_reader is None:
        from app.result_evidence_v018_a13 import arkade_rows, safe_json
        rows_reader = rows_reader or arkade_rows
        json_reader = json_reader or safe_json
    if coverage_builder is None:
        from noark5_workflow.external_evidence.arkade5_coverage import build_arkade5_coverage
        coverage_builder = build_arkade5_coverage

    output: list[CoverageRow] = []
    for shot in _unique(snapshots):
        by_file: dict[Path, list[dict[str, Any]]] = defaultdict(list)
        for record in rows_reader((shot,)):
            file = _work_file(shot, record.get("file"))
            if file is not None:
                by_file[file].append(record)
        for file, records in by_file.items():
            root = Path(shot.job.work).resolve(strict=True)
            # ``json_reader`` applies the same bounds and symlink protections
            # as all other persisted-result readers in v0.1.8.
            normalized = json_reader(root, str(file.relative_to(root)))
            if not normalized:
                continue
            try:
                coverage = coverage_builder(normalized)
            except (OSError, TypeError, ValueError, KeyError):
                continue
            for item in coverage.get("items") or ():
                candidates = item.get("dwm_candidates") or ()
                output.append(CoverageRow(
                    str(shot.job.job_uid), _label(shot.job),
                    str(records[0].get("import_id") or ""),
                    str(item.get("arkade_test_id") or ""),
                    str(item.get("arkade_test_name") or ""),
                    str(item.get("arkade_status") or "Ukjent"),
                    str(item.get("classification") or "unmapped"),
                    tuple(str(c.get("dwm_test_id")) for c in candidates
                          if isinstance(c, dict) and c.get("dwm_test_id")),
                    str(item.get("reason") or ""), file,
                    str(records[0].get("source_sha256") or ""),
                ))
    return tuple(output)


def _safe_export_target(target: Path, shots: Iterable[Any], *, json_reader: Callable) -> Path:
    """Block exports into any Work, Source, Work content or AIP subtree."""
    target = Path(target).expanduser().resolve(strict=False)
    if target.suffix.lower() not in {".csv", ".html", ".json"}:
        raise ValueError("Velg CSV, HTML eller JSON som eksportformat.")
    if not target.parent.is_dir():
        raise ValueError("Velg en eksisterende eksportmappe.")
    for shot in _unique(shots):
        data = json_reader(shot.job.work, "job.json") or {}
        definition = data.get("job") if isinstance(data.get("job"), dict) else data
        protected = [shot.job.work]
        for key in ("source_root", "source_extraction", "source_tar", "source_unzipped",
                    "archive_root", "work_root", "work_content", "work_operations",
                    "output_root"):
            raw = definition.get(key)
            if isinstance(raw, str) and raw.strip():
                protected.append(raw)
        for value in protected:
            try:
                base = Path(value).expanduser().resolve(strict=False)
                if target == base or target.is_relative_to(base):
                    raise ValueError("Eksport er ikke tillatt i Source, Work eller AIP.")
            except (OSError, RuntimeError):
                continue
    return target


def _export_rows(rows: Iterable[SourceRow]) -> tuple[dict[str, Any], ...]:
    return tuple({
        "job_uid": row.job_uid, "uttrekk": row.job_label, "kilde": row.source,
        "import_id": row.import_id, "status": row.status, "antall": row.count,
        "enhet": row.unit, "sha256": row.sha256,
        "lagret_fil": str(row.file) if row.file else "",
    } for row in rows)


def export_inventory(target: str | Path, records: Iterable[SourceRow], snapshots: Iterable[Any],
                     *, overwrite: bool = False, json_reader: Callable | None = None) -> Path:
    """Explicit user export of a read-only provenance overview.

    No implicit overwrite. A generated report never modifies Work job data.
    """
    if json_reader is None:
        from app.result_evidence_v018_a13 import safe_json
        json_reader = safe_json
    shots = _unique(snapshots)
    destination = _safe_export_target(Path(target), shots, json_reader=json_reader)
    if destination.exists() and not overwrite:
        raise FileExistsError(f"Eksportfilen finnes allerede: {destination}")
    data = _export_rows(records)
    headers = ("job_uid", "uttrekk", "kilde", "import_id", "status",
               "antall", "enhet", "sha256", "lagret_fil")
    if destination.suffix.lower() == ".csv":
        from io import StringIO
        out = StringIO()
        writer = csv.DictWriter(out, fieldnames=headers, delimiter=";", lineterminator="\n")
        writer.writeheader()
        # Treat arbitrary source names and paths as data when opened in Excel.
        # Prevent formula interpretation even if an imported label begins =/+/−/@.
        for record in data:
            escaped = {}
            for key, value in record.items():
                if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                    value = "'" + value
                escaped[key] = value
            writer.writerow(escaped)
        payload = out.getvalue()
    elif destination.suffix.lower() == ".json":
        payload = json.dumps({"format": "dwm-evidence-inventory-v1",
                              "generated_utc": datetime.now(timezone.utc).isoformat(),
                              "approval": "Ingen faglig godkjenning eller automatisk kildeavstemming",
                              "records": data}, ensure_ascii=False, indent=2) + "\n"
    else:
        head = "".join(f"<th>{html.escape(name)}</th>" for name in headers)
        content = "\n".join("<tr>" + "".join(
            f"<td>{html.escape('Ukjent' if name == 'antall' and row[name] is None else str(row[name]))}</td>"
            for name in headers) + "</tr>" for row in data)
        payload = ("<!doctype html><html lang='nb'><head><meta charset='utf-8'>"
                   "<title>DWM – evidensoversikt</title>"
                   "<style>body{font:14px system-ui;margin:2em}table{border-collapse:collapse}"
                   "td,th{padding:.45em;border:1px solid #999;text-align:left}"
                   "thead{background:#eee}</style></head><body>"
                   "<h1>DWM – evidensoversikt</h1><p>Kilder, importerte resultater og "
                   "rapportfiler er holdt adskilt. Dette er ikke en faglig godkjenning.</p>"
                   "<table><thead><tr>" + head + "</tr></thead><tbody>" + content
                   + "</tbody></table></body></html>\n")
    # Atomic replacement after explicit overwrite confirmation.  For new files,
    # exclusive creation guarantees a competing file is never silently lost.
    if overwrite:
        tmpname = None
        try:
            with NamedTemporaryFile("w", encoding="utf-8-sig" if destination.suffix.lower() == ".csv"
                                     else "utf-8", dir=destination.parent, prefix=".dwm-export-",
                                     suffix=".tmp", delete=False, newline="") as fp:
                tmpname = fp.name
                fp.write(payload)
            os.replace(tmpname, destination)
        finally:
            if tmpname and Path(tmpname).exists():
                Path(tmpname).unlink()
    else:
        try:
            with destination.open("x", encoding="utf-8-sig" if destination.suffix.lower() == ".csv"
                                  else "utf-8", newline="") as fp:
                fp.write(payload)
        except OSError:
            # Do not erase a pre-existing file on an exclusive-create failure.
            raise
    return destination
