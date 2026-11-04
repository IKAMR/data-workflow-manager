"""Read-only professional evidence and annual-volume views over independent Work jobs.

No Source, AIP, DOKUMENT or historical joblist traversal. The depot report
remains the source for DWM annual metrics; Arkade and KDRS Query stay separate
external sources. Missing annual series are UNKNOWN, never inferred as zero.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Any, Iterable

from app.result_center_v018_a12 import ResultOverview, discover_results

METRICS: tuple[tuple[str, str], ...] = (
    ("folder", "Mapper"),
    ("registration", "Registreringer"),
    ("journal", "Journalposter"),
    ("document_description", "Dokumentbeskrivelser"),
    ("document_object", "Dokumentobjekter"),
)
MAX_EVIDENCE_BYTES = 16_000_000
MAX_YEARS = 400


@dataclass(frozen=True)
class WorkJob:
    job_id: str
    name: str
    work: Path
    job_uid: str
    profile_id: str = "noark5"

    @property
    def work_operations(self) -> Path:
        """Compatibility with the established Work-local period assessment API."""
        return self.work

    @property
    def _effective_work_operations(self) -> Path:
        return self.work


@dataclass(frozen=True)
class WorkSnapshot:
    job: WorkJob
    results: ResultOverview

    @property
    def depot(self) -> dict[str, Any] | None:
        return self.results.depot_report


@dataclass(frozen=True)
class AnnualScope:
    key: str
    label: str
    job_uid: str = ""
    archive_part_id: str = ""


@dataclass(frozen=True)
class AnnualTable:
    scope: AnnualScope
    rows: tuple[dict[str, Any], ...]
    source_count: int
    warnings: tuple[str, ...]
    observed_years: tuple[int, ...]


def _root(value: str | Path) -> Path:
    return Path(value).resolve(strict=True)


def safe_json(work: str | Path, relative: str, *, max_bytes: int = MAX_EVIDENCE_BYTES) -> dict[str, Any] | None:
    """Only read a bounded JSON object strictly within this Work directory."""
    try:
        root = _root(work)
        file = root / relative.replace("\\", "/")
        target = file.resolve(strict=True)
        if not target.is_relative_to(root) or not target.is_file() or target.stat().st_size > max_bytes:
            return None
        document = json.loads(target.read_text(encoding="utf-8-sig"))
        return document if isinstance(document, dict) else None
    except (OSError, ValueError, TypeError, UnicodeError, RuntimeError):
        return None


def open_work_job(job_id: str, name: str, work: str | Path | None,
                  *, profile_id: str = "noark5") -> WorkSnapshot | None:
    if not work:
        return None
    overview = discover_results(work)
    if overview.work is None or not overview.work.is_dir():
        return None
    document = safe_json(overview.work, "job.json") or {}
    # Work UUID is authoritative. A missing UUID must not collapse distinct
    # jobs carrying the same local JOB-001 identity.
    uid = str(document.get("job_uid") or document.get("job_uuid") or "").strip()
    if not uid:
        uid = "work:" + str(overview.work).casefold()
    job = WorkJob(str(job_id), str(name), overview.work, uid, str(profile_id))
    return WorkSnapshot(job, overview)


def _parts(snapshot: WorkSnapshot) -> tuple[dict[str, Any], ...]:
    report = snapshot.depot or {}
    return tuple(part for part in report.get("archive_parts", ()) if isinstance(part, dict))


def _unique_work_snapshots(snapshots: Iterable[WorkSnapshot]) -> tuple[WorkSnapshot, ...]:
    """Avoid counting the same underlying Work twice in a selected group."""
    by_uid = {}
    for shot in snapshots:
        by_uid.setdefault(shot.job.job_uid, shot)
    return tuple(by_uid.values())


def annual_scopes(snapshots: Iterable[WorkSnapshot]) -> tuple[AnnualScope, ...]:
    snapshots = _unique_work_snapshots(snapshots)
    scopes: list[AnnualScope] = [AnnualScope("all", "Alle valgte uttrekk / arkivdeler")]
    for index, shot in enumerate(snapshots, 1):
        jobkey = "job:" + shot.job.job_uid
        label = f"{shot.job.job_id} – {shot.job.name}"
        scopes.append(AnnualScope(jobkey, label, shot.job.job_uid))
        for position, part in enumerate(_parts(shot), 1):
            meta = part.get("archive_part") or {}
            native_id = str(meta.get("system_id") or "")
            if not native_id:
                # Never use the title or the KDRS U2 index as a native ID.
                # The ordinal is only an internal display key for old reports.
                native_id = f"missing-id-{position}"
            part_label = str(meta.get("title") or meta.get("system_id") or f"Arkivdel {position}")
            scopes.append(AnnualScope(f"part:{shot.job.job_uid}:{native_id}",
                                      f"{label} / {part_label}", shot.job.job_uid, native_id))
    return tuple(scopes)


def _metric_values(part: dict[str, Any], metric: str) -> dict[int, int] | None:
    series = (part.get("yearly_volume") or {}).get(metric)
    if not isinstance(series, dict) or not series:
        return None
    parsed: dict[int, int] = {}
    for yr, raw in series.items():
        try:
            # Do not silently round floats, accept booleans or parse years 2099 as 0.
            year = int(yr)
            if isinstance(raw, bool) or str(raw).strip() != str(int(raw)):
                return None
            count = int(raw)
        except (TypeError, ValueError, OverflowError):
            return None
        if not 1000 <= year <= 9999 or count < 0:
            return None
        parsed[year] = count
    return parsed


def annual_table(snapshots: Iterable[WorkSnapshot], scope_key: str = "all") -> AnnualTable:
    snapshots = _unique_work_snapshots(snapshots)
    scopes = {scope.key: scope for scope in annual_scopes(snapshots)}
    if scope_key not in scopes:
        raise ValueError("Ukjent årsomfang: " + str(scope_key))
    scope = scopes[scope_key]
    selected: list[tuple[WorkSnapshot, dict[str, Any]]] = []
    warnings: list[str] = []
    if not scope.job_uid and len(snapshots) > 1:
        warnings.append("Årstotaler for flere uttrekk er summer av lagrede observasjoner. "
                        "Overlappende dokumenter og arkivenheter kan forekomme; "
                        "tallene er ikke automatisk unike på tvers av uttrekk.")
    for shot in snapshots:
        if scope.job_uid and shot.job.job_uid != scope.job_uid:
            continue
        if shot.depot is None:
            warnings.append(f"{shot.job.name}: Ingen lesbar depotrapport (ukjent, ikke null).")
            continue
        for position, part in enumerate(_parts(shot), 1):
            native_id = str((part.get("archive_part") or {}).get("system_id") or f"missing-id-{position}")
            if scope.archive_part_id and scope.archive_part_id != native_id:
                continue
            selected.append((shot, part))
    if not selected:
        warnings.append("Ingen arkivdeler med lagret årsgrunnlag for dette utvalget.")
    observed_years: set[int] = set()
    series_by_part: list[dict[str, dict[int, int] | None]] = []
    for shot, part in selected:
        by_metric = {}
        for metric, label in METRICS:
            values = _metric_values(part, metric)
            if values is None:
                part_name = str((part.get("archive_part") or {}).get("title") or "Ukjent arkivdel")
                warnings.append(f"{shot.job.name} / {part_name}: {label} per år mangler eller er ugyldig.")
            else:
                observed_years.update(values)
            by_metric[metric] = values
        series_by_part.append(by_metric)
    if len(observed_years) > MAX_YEARS:
        warnings.append("Årsgrunnlaget omfatter for mange forskjellige år og er avkortet.")
    years = sorted(observed_years)[:MAX_YEARS]
    rows = []
    for year in years:
        row: dict[str, Any] = {"year": year}
        for metric, _ in METRICS:
            # One missing entry or missing series must not be interpreted as 0.
            values = [part[metric] for part in series_by_part]
            row[metric] = sum(value[year] for value in values) if (
                values and all(value is not None and year in value for value in values)
            ) else None
        rows.append(row)
    return AnnualTable(scope, tuple(rows), len(selected), tuple(dict.fromkeys(warnings)), tuple(years))


def _str(value: Any, empty: str = "–") -> str:
    return str(value) if value is not None and value != "" else empty


def overview_rows(snapshots: Iterable[WorkSnapshot]) -> tuple[dict[str, Any], ...]:
    records = []
    for shot in snapshots:
        depot = shot.depot or {}
        summary = depot.get("summary") or {}
        technical = depot.get("technical_validation") or {}
        assessment = depot.get("assessment") or {}
        external = ((depot.get("external_validation") or {}).get("arkade5") or {})
        arkade = external.get("summary") or {}
        records.append({
            "job": shot.job,
            "report_path": shot.results.depot_report_path,
            "archive_parts": summary.get("archive_part_count"),
            "folders": summary.get("folder_count"),
            "registrations": summary.get("registration_count"),
            "journalposts": summary.get("journalpost_count"),
            "document_objects": summary.get("document_object_count"),
            "technical_status": technical.get("status") if depot else None,
            "assessment_status": assessment.get("status") if depot else None,
            "deviations": tuple(v for v in depot.get("deviations", ()) if isinstance(v, dict)),
            "arkade_imports": arkade.get("imports") if depot else None,
        })
    return tuple(records)


def archive_part_details(snapshots: Iterable[WorkSnapshot]) -> tuple[dict[str, Any], ...]:
    details = []
    for shot in snapshots:
        recon = ((shot.depot or {}).get("period_reconciliation") or {})
        by_native = {
            str((record.get("archive_part") or {}).get("system_id") or ""): record
            for record in recon.get("archive_parts", ()) if isinstance(record, dict)
        }
        for part in _parts(shot):
            meta = part.get("archive_part") or {}
            sid = str(meta.get("system_id") or "")
            details.append({
                "job": shot.job, "system_id": sid,
                "title": _str(meta.get("title"), "Uten tittel"),
                "archive_part": part,
                "period_evidence": by_native.get(sid),
                "report_path": shot.results.depot_report_path,
            })
    return tuple(details)


def technical_rows(snapshots: Iterable[WorkSnapshot]) -> tuple[dict[str, Any], ...]:
    rows = []
    for shot in snapshots:
        validation = ((shot.depot or {}).get("technical_validation") or {})
        for item in validation.get("tests", ()):
            if not isinstance(item, dict):
                continue
            rec = item.get("reconciliation_summary") or {}
            rows.append({
                "job": shot.job,
                "test_id": str(item.get("test_id") or ""),
                "legacy_id": str(item.get("legacy_job_id") or ""),
                "noark_point": str(item.get("test_point") or ""),
                "status": str(item.get("status") or "unknown"),
                "checks": rec.get("checks"),
                "mismatches": rec.get("mismatches"),
                "details": item,
                "file": shot.results.depot_report_path,
            })
    return tuple(rows)


def _arkade_manifests(shot: WorkSnapshot) -> list[tuple[dict[str, Any], Path]]:
    if shot.results.work is None:
        return []
    root = shot.results.work
    group = root / "external_evidence" / "arkade5"
    if not group.is_dir() or group.is_symlink():
        return []
    manifests = []
    try:
        import_dirs = sorted((p for p in group.iterdir() if p.is_dir() and not p.is_symlink()),
                             key=lambda p: p.name.casefold())[:250]
    except OSError:
        return []
    for folder in import_dirs:
        relative = "external_evidence/arkade5/" + folder.name + "/manifest.json"
        manifest = safe_json(root, relative)
        if manifest is not None:
            manifests.append((manifest, folder))
    return manifests


def arkade_rows(snapshots: Iterable[WorkSnapshot]) -> tuple[dict[str, Any], ...]:
    rows = []
    for shot in snapshots:
        for manifest, folder in _arkade_manifests(shot):
            document = safe_json(shot.job.work, str((folder / "normalized" / "arkade5_results.json").relative_to(shot.job.work)))
            if not document:
                continue
            summary = document.get("summary") or {}
            for test in document.get("tests", ()):
                if not isinstance(test, dict):
                    continue
                items = test.get("results") or []
                rows.append({
                    "job": shot.job,
                    "import_id": str(manifest.get("import_id") or folder.name),
                    "version": _str(document.get("source_version")),
                    "tested_at": _str(summary.get("date_of_testing")),
                    "source_sha256": (manifest.get("source") or {}).get("sha256"),
                    "test_id": _str(test.get("test_id")),
                    "title": _str(test.get("test_name")),
                    "status": _str(test.get("source_status"), "unknown"),
                    "errors": test.get("number_of_errors"),
                    "findings": len(items),
                    "details": test,
                    "file": (folder / "normalized" / "arkade5_results.json").resolve(),
                })
    return tuple(rows)


def pronom_rows(snapshots: Iterable[WorkSnapshot]) -> tuple[dict[str, Any], ...]:
    rows = []
    for shot in snapshots:
        for manifest, folder in _arkade_manifests(shot):
            document = safe_json(shot.job.work, str((folder / "normalized" / "pronom_statistics.json").relative_to(shot.job.work)))
            if not document or document.get("evidence_type") != "arkade5_pronom_format_statistics":
                continue
            csv = document.get("csv") or {}
            for line in csv.get("rows", ()):
                if not isinstance(line, dict):
                    continue
                raw = line.get("Antall")
                try:
                    count = int(str(raw).replace(" ", ""))
                except (TypeError, ValueError):
                    count = None
                if count is not None and count < 0:
                    count = None
                rows.append({
                    "job": shot.job,
                    "import_id": str(manifest.get("import_id") or folder.name),
                    "format_id": str(line.get("Format-ID") or line.get("PUID") or ""),
                    "format": str(line.get("Filtype") or line.get("Format") or ""),
                    "version": str(line.get("Formatversjon") or ""),
                    "raf": str(line.get("RAF-220301") or ""),
                    "count": count,
                    "source_sha256": (document.get("source") or {}).get("sha256"),
                    "details": line,
                    "file": (folder / "normalized" / "pronom_statistics.json").resolve(),
                })
    return tuple(rows)


def kdrs_rows(snapshots: Iterable[WorkSnapshot]) -> tuple[dict[str, Any], ...]:
    rows = []
    for shot in snapshots:
        root = shot.job.work / "external_evidence" / "kdrs_query"
        if not root.is_dir() or root.is_symlink():
            continue
        try:
            directories = sorted((p for p in root.iterdir() if p.is_dir() and not p.is_symlink()),
                                 key=lambda p: p.name.casefold())[:200]
        except OSError:
            continue
        for directory in directories:
            manifest = safe_json(shot.job.work, str((directory / "manifest.json").relative_to(shot.job.work)))
            if not manifest:
                continue
            for item in manifest.get("reports", ()) or manifest.get("files", ()):
                if not isinstance(item, dict):
                    continue
                rows.append({
                    "job": shot.job,
                    "import_id": str(manifest.get("import_id") or directory.name),
                    "report_type": str(item.get("report_type") or item.get("type") or ""),
                    "source": str(item.get("original_name") or item.get("source_file") or ""),
                    "sha256": str(item.get("sha256") or item.get("source_sha256") or ""),
                    "details": item,
                    "file": (directory / "manifest.json").resolve(),
                })
            if not (manifest.get("reports") or manifest.get("files")):
                rows.append({"job": shot.job, "import_id": str(manifest.get("import_id") or directory.name),
                             "report_type": "(import)", "source": str(manifest.get("source") or ""),
                             "sha256": "", "details": manifest, "file": (directory / "manifest.json").resolve()})
    return tuple(rows)


def period_rows(snapshots: Iterable[WorkSnapshot]) -> tuple[dict[str, Any], ...]:
    rows = []
    for shot in snapshots:
        model = shot.depot or {}
        recon = model.get("period_reconciliation") or {}
        declared = recon.get("declared_period") or {}
        observed = recon.get("observed_series") or {}
        assessment = safe_json(shot.job.work, f"noark5_reports/period_assessments/{shot.job.job_id}.json") or {}
        rows.append({"job": shot.job, "scope": "Uttrekk", "native_id": "",
                     "declared": declared, "observed": observed,
                     "assessment": assessment, "details": recon,
                     "file": shot.results.depot_report_path})
        assessed_parts = assessment.get("archive_part_assessments") or {}
        for row in recon.get("archive_parts", ()):
            if not isinstance(row, dict):
                continue
            meta = row.get("archive_part") or {}
            sid = str(meta.get("system_id") or "")
            rows.append({"job": shot.job, "scope": str(meta.get("title") or sid or "Arkivdel"),
                         "native_id": sid, "declared": {},
                         "observed": row.get("observed_period") or {},
                         "assessment": assessed_parts.get(sid) or {}, "details": row,
                         "file": shot.results.depot_report_path})
    return tuple(rows)


def describe_span(entry: Any) -> str:
    if not isinstance(entry, dict):
        return "Ukjent"
    if "start_year" in entry and "end_year" in entry:
        a,b = entry.get("start_year"),entry.get("end_year")
    elif "first_year" in entry and "last_year" in entry:
        a,b = entry.get("first_year"),entry.get("last_year")
    elif "span" in entry and isinstance(entry["span"], dict):
        return describe_span(entry["span"])
    else:
        return "Ukjent"
    return f"{a}–{b}" if a is not None and b is not None else "Ukjent"


def report_links(snapshots: Iterable[WorkSnapshot]) -> tuple[dict[str, Any], ...]:
    result = []
    for shot in snapshots:
        for item in shot.results.by_category["Depotrapporter"]:
            result.append({"job": shot.job, "filename": item.title,
                           "relative_path": item.relative_path,
                           "date": item.modified_at, "file": item.path})
    return tuple(sorted(result, key=lambda r: r["date"], reverse=True))


def evidence_alerts(snapshots: Iterable[WorkSnapshot]) -> tuple[str, ...]:
    alerts = []
    for shot in snapshots:
        prefix = shot.job.job_id + " / " + shot.job.name + ": "
        alerts.extend(prefix + warning for warning in shot.results.warnings)
        for deviation in (shot.depot or {}).get("deviations", ()):
            if isinstance(deviation, dict) and deviation.get("requires_review"):
                alerts.append(prefix + str(deviation.get("summary") or deviation.get("category") or "Vurderingspunkt"))
    return tuple(alerts)


def kdrs_period_sources(snapshots: Iterable[WorkSnapshot]) -> tuple[dict[str, Any], ...]:
    """Expose preserved KDRS Standard/U1/U2 annual facts *without merging* them.

    Uses the established semantic mapping and period-evidence reader. KDRS U2
    numbered parts are intentionally NOT interpreted as DWM native part IDs.
    """
    result: list[dict[str, Any]] = []
    for shot in snapshots:
        if not kdrs_rows((shot,)):
            continue
        try:
            from noark5_workflow.external_evidence.kdrs_query_mapping import build_mapped_pool
            from noark5_workflow.reporting.period_kdrs_evidence_a18 import period_evidence_from_pool
            evidence = period_evidence_from_pool(build_mapped_pool(shot.job.work))
        except (ImportError, OSError, ValueError, TypeError, KeyError):
            continue
        for run in evidence.get("runs") or []:
            for scope in run.get("scopes") or []:
                result.append({"job": shot.job, "import_id": str(run.get("import_id") or ""),
                               "report_type": str(run.get("report_type") or ""),
                               "source_files": tuple(run.get("sources") or ()),
                               "scope_id": str(scope.get("scope_id") or ""),
                               "scope_label": str(scope.get("label") or ""),
                               "source": scope})
    return tuple(result)


def kdrs_annual_scopes(snapshots: Iterable[WorkSnapshot], sources=None) -> tuple[AnnualScope, ...]:
    result = []
    if sources is None:
        sources = kdrs_period_sources(snapshots)
    for item in sources:
        key = ":".join(("kdrs", item["job"].job_uid, item["import_id"], item["report_type"],
                        item["scope_id"]))
        result.append(AnnualScope(key, f"KDRS {item['report_type']} / {item['job'].name} / "
                                       f"{item['scope_label']} [{item['import_id']}]",
                                  item["job"].job_uid))
    return tuple(result)


def kdrs_annual_table(snapshots: Iterable[WorkSnapshot], scope_key: str, sources=None) -> AnnualTable:
    """Source-specific KDRS counts, not automatically approved DWM XPath totals."""
    if sources is None:
        sources = kdrs_period_sources(snapshots)
    scopes = {scope.key: scope for scope in kdrs_annual_scopes(snapshots, sources)}
    if scope_key not in scopes:
        raise ValueError("KDRS-kilden finnes ikke lenger")
    scope = scopes[scope_key]
    matched = None
    for item in sources:
        key = ":".join(("kdrs", item["job"].job_uid, item["import_id"], item["report_type"],
                        item["scope_id"]))
        if scope_key == key:
            matched = item
            break
    if matched is None:
        raise ValueError("KDRS-importen er endret")
    orig = matched["source"]
    # Never merge løpende journal, offentlig journal and journalpost's own
    # journal date into a single inferred period or duplicate count.
    mapping = {
        "folder": "folders_by_creation_year",
        "registration": "registrations_by_creation_year",
        "journal": "journalposts_by_journal_year",
    }
    series = orig.get("series") or {}
    years: set[int] = set()
    for metric in mapping.values():
        for key in (series.get(metric) or {}):
            try:
                y = int(key)
            except (ValueError, TypeError):
                continue
            if 1000 <= y <= 9999:
                years.add(y)
    records = []
    for year in sorted(years)[:MAX_YEARS]:
        record = {"year": year}
        for metric, _ in METRICS:
            source_metric = mapping.get(metric)
            raw = (series.get(source_metric) or {}).get(str(year)) if source_metric else None
            record[metric] = raw if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0 else None
        records.append(record)
    warnings = ("KDRS Query er ekstern evidens. Mapper/saker kan ha annen semantikk enn DWM-mapper. "
                "Årsserier fra ulike kilder/importer og endringslogg blir ikke slått sammen.",)
    warnings += tuple(orig.get("conflicts") or ())
    return AnnualTable(scope, tuple(records), 1, warnings, tuple(sorted(years)[:MAX_YEARS]))
