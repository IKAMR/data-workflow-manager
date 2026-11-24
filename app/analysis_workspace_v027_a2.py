"""Read-only, scope-aware result projection for the new DWM Analyse surface.

The Work report is the source of facts.  No tests are rerun and no decisions
are persisted here.  Sources, methods and original JSON remain unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

MAX_REPORT = 32_000_000
MAX_FINDINGS = 32_000_000
MAX_STATISTICS = 2_000_000
MAX_CANDIDATES = 400
METRICS = (
    ('folder', 'Mapper (opprettet)'),
    ('registration', 'Registreringer (opprettet)'),
    ('journal', 'Journalposter (journaldato)'),
    ('document_description', 'Dokumentbeskrivelser (opprettet)'),
    ('document_object', 'Dokumentobjekter (opprettet)'),
)
AREAS = ('Struktur', 'Perioder og \u00e5r', 'Metadata og verdier',
         'Dokumenter og filformater', 'Bevaring og skjerming')
FIELD_NAMES = {'M051': 'Arkivdelstatus', 'M052': 'Saksstatus',
               'M053': 'Journalstatus', 'M054': 'Dokumentstatus'}


@dataclass(frozen=True)
class AnalysisSnapshot:
    work: Path
    job_id: str
    job_name: str
    job_uid: str
    report_path: Path
    report: dict[str, Any]
    metadata: dict[str, Any]
    findings: tuple[dict[str, Any], ...]
    findings_complete: bool
    format_statistics: dict[str, Any]

    @property
    def parts(self) -> tuple[dict[str, Any], ...]:
        return tuple(part for part in self.report.get('archive_parts', ())
                     if isinstance(part, dict))

    @property
    def archive_count(self) -> int | None:
        raw = (self.report.get('summary') or {}).get('archive_count')
        try:
            return int(raw) if raw is not None else None
        except (ValueError, TypeError):
            return None


def _json_file(path: Path, *, limit: int) -> dict[str, Any] | None:
    """Read a bounded regular file; a missing/invalid optional file is unknown."""
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            return None
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        return value if isinstance(value, dict) else None
    except (OSError, UnicodeError, ValueError):
        return None


def _candidates(root: Path, prefix: str) -> list[Path]:
    if root.is_symlink() or not root.is_dir():
        return []
    paths = []
    for n, child in enumerate(root.iterdir()):
        if n >= MAX_CANDIDATES:
            break
        if child.is_dir() and not child.is_symlink() and child.name.startswith(prefix):
            paths.append(child)
    return sorted(paths, key=lambda p: p.name, reverse=True)


def find_report(work: Path | str, job_id: str, job_uid: str = '') -> Path | None:
    """Select the latest matching, identity-checked DWM report within Work."""
    if not re.fullmatch(r'[\w-]{1,80}', job_id, flags=re.ASCII):
        return None
    root = Path(work) / 'noark5_reports' / 'depot_validation'
    for folder in _candidates(root, job_id + '__'):
        manifest = _json_file(folder / 'artifact_manifest.json', limit=128_000)
        # A mismatching manifest is never accepted as the active job's report.
        if manifest and (str(manifest.get('job_id') or '') != job_id
                         or (job_uid and str(manifest.get('job_uid') or '') != job_uid)):
            continue
        if job_uid and not manifest:
            continue
        report = folder / 'depot_validation_report.json'
        if (not report.is_symlink() and report.is_file()
                and report.stat().st_size <= MAX_REPORT):
            return report
    return None


def _read_findings(report_dir: Path, work: Path) -> tuple[tuple[dict[str, Any], ...], bool]:
    """Read complete source findings for part-level deviations, never guess."""
    path = report_dir / 'delivery-funn.jsonl'
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FINDINGS:
            return (), False
        found = []
        with path.open(encoding='utf-8-sig') as stream:
            for i, line in enumerate(stream):
                if i >= 250_000:
                    return (), False
                if not line.strip():
                    continue
                item = json.loads(line)
                if not isinstance(item, dict):
                    return (), False
                # Keep only the fields used for scope and evidence display.
                found.append({key: item.get(key) for key in (
                    'metadata_id', 'value', 'archive_part_id', 'object_id',
                    'xpath', 'file', 'lines', 'message', 'finding_uid')})
        return tuple(found), True
    except (OSError, UnicodeError, ValueError):
        return (), False


def _latest_format_statistics(work: Path) -> dict[str, Any]:
    source = work / 'external_evidence' / 'siegfried'
    for folder in _candidates(source, ''):
        item = _json_file(folder / 'pronom_statistics.json', limit=MAX_STATISTICS)
        if item and isinstance(item.get('format_groups'), list):
            return item
    return {}


def load_analysis(work: Path | str, job_id: str, job_name: str = '',
                  job_uid: str = '') -> AnalysisSnapshot:
    """Read Work only.  Require a report belonging to the selected job."""
    root = Path(work)
    if not root.is_dir() or root.is_symlink():
        raise FileNotFoundError('Work-mappen er ikke tilgjengelig.')
    report_path = find_report(root, job_id, job_uid)
    if report_path is None:
        raise FileNotFoundError('Ingen depotrapport for valgt jobb i Work.')
    report = _json_file(report_path, limit=MAX_REPORT)
    if not report or report.get('report_type') != 'noark5_depot_validation':
        raise ValueError('Lagret depotrapport har ukjent eller ugyldig format.')
    meta = _json_file(root / 'metadata' / 'depot_metadata.json', limit=2_000_000) or {}
    if str(meta.get('job_id') or '') not in ('', job_id):
        meta = {}
    findings, complete = _read_findings(report_path.parent, root)
    # The complete finding count is part of the persisted report contract.
    expected = (report.get('delivery_validation') or {}).get('finding_count')
    if expected is not None:
        try:
            complete = complete and len(findings) == int(expected)
        except (ValueError, TypeError):
            complete = False
    return AnalysisSnapshot(root, job_id, job_name, job_uid, report_path, report, meta,
                            findings, complete, _latest_format_statistics(root))


def part_identity(part: dict[str, Any]) -> dict[str, Any]:
    return part.get('archive_part') or {}


def part_title(part: dict[str, Any], index: int) -> str:
    return str(part_identity(part).get('title') or f'Arkivdel {index + 1}')


def selected_parts(snapshot: AnalysisSnapshot, part_index: int | None) -> tuple[dict[str, Any], ...]:
    if part_index is None:
        return snapshot.parts
    if not 0 <= part_index < len(snapshot.parts):
        return ()
    return (snapshot.parts[part_index],)


def annual_rows(snapshot: AnalysisSnapshot, part_index: int | None = None,
                year: str = '') -> tuple[tuple[str, tuple[int | None, ...]], ...]:
    """Distinct date series, never mix different date semantics into one total."""
    parts = selected_parts(snapshot, part_index)
    years = set()
    for part in parts:
        source = part.get('yearly_volume') or {}
        if not isinstance(source, dict):
            continue
        for key, _label in METRICS:
            values = source.get(key) or {}
            if isinstance(values, dict):
                years.update(str(k) for k in values if re.fullmatch(r'\d{4}', str(k)))
    if year:
        years = {y for y in years if y == year}
    result = []
    for y in sorted(years):
        counts = []
        for key, _label in METRICS:
            elements = []
            for part in parts:
                obj = (part.get('yearly_volume') or {}).get(key)
                if isinstance(obj, dict):
                    try:
                        elements.append(int(obj.get(y, 0)))
                    except (ValueError, TypeError):
                        elements.append(None)
                else:
                    elements.append(None)
            counts.append(sum(elements) if elements and all(v is not None for v in elements) else None)
        result.append((y, tuple(counts)))
    return tuple(result)


def summary_counts(snapshot: AnalysisSnapshot, part_index: int | None = None,
                   year: str = '') -> dict[str, int | None]:
    fields = {'folders': 'folder_count', 'registrations': 'registration_count',
              'journalposts': 'journalpost_count', 'objects': 'document_object_count'}
    if year:
        annual = dict(annual_rows(snapshot, part_index, year))
        values = annual.get(year)
        return {k: values[index] if values else None
                for k, index in [('folders', 0), ('registrations', 1),
                                 ('journalposts', 2), ('objects', 4)]}
    if part_index is None:
        source = snapshot.report.get('summary') or {}
    else:
        parts = selected_parts(snapshot, part_index)
        source = parts[0] if parts else {}
    return {key: _int_or_none(source.get(field)) for key, field in fields.items()}


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (ValueError, TypeError):
        return None


def _production_values(standard_version: str, metadata_id: str) -> tuple[str, ...]:
    """Lookup the versioned local registry without inventing unspecified rules."""
    registry = (Path(__file__).resolve().parents[1] / 'config' / 'noark5'
                / 'standards' / 'noark5_standard_values.json')
    document = _json_file(registry, limit=3_000_000) or {}
    version = (document.get('versions') or {}).get(standard_version) or {}
    entries = version.get('value_sets') or {}
    result = []
    for key, item in entries.items():
        if not isinstance(item, dict) or str(item.get('metadata_id') or '') != metadata_id:
            continue
        result.extend(str(value) for value in item.get('values') or () if isinstance(value, str))
    return tuple(dict.fromkeys(result))


def delivery_rules(snapshot: AnalysisSnapshot, part_index: int | None = None) -> tuple[dict[str, Any], ...]:
    """Never present whole-extract value counts as archive-part value counts."""
    source = (snapshot.report.get('delivery_validation') or {}).get('rules') or ()
    part_id = ''
    if part_index is not None:
        selected = selected_parts(snapshot, part_index)
        if not selected:
            return ()
        part_id = str(part_identity(selected[0]).get('system_id') or '')
    rows = []
    for rule in source:
        if not isinstance(rule, dict):
            continue
        mid = str(rule.get('metadata_id') or '')
        if part_index is None:
            observed = _int_or_none(rule.get('observed_count'))
            deviations = _int_or_none(rule.get('delivery_deviations'))
            distribution = rule.get('standard_value_counts') or {}
        else:
            observed = None  # the model has no per-part full value distribution
            deviations = (sum(f.get('metadata_id') == mid and f.get('archive_part_id') == part_id
                              for f in snapshot.findings) if snapshot.findings_complete and part_id
                          else None)
            distribution = {}  # do not reuse the full-extract distribution
        version = str((snapshot.report.get('delivery_validation') or {}).get('version') or '')
        rows.append({
            'metadata_id': mid, 'label': FIELD_NAMES.get(mid, str(rule.get('xml_field') or mid)),
            'observed': observed, 'deviations': deviations,
            'production_distribution': distribution if isinstance(distribution, dict) else {},
            'production_values': _production_values(version, mid),
            'delivery_values': tuple(rule.get('allowed_at_delivery') or ()),
            'version': version,
            'source_status': str(((snapshot.report.get('delivery_validation') or {})
                                  .get('source_reference') or {}).get('source_status') or ''),
            'status': str(rule.get('status') or ''),
            'source_page': rule.get('source_page'),
            'source_title': str(((snapshot.report.get('delivery_validation') or {})
                                .get('source_reference') or {}).get('title') or ''),
        })
    return tuple(rows)


def rule_findings(snapshot: AnalysisSnapshot, metadata_id: str,
                  part_index: int | None = None) -> tuple[dict[str, Any], ...]:
    if not snapshot.findings_complete:
        return ()
    chosen = selected_parts(snapshot, part_index)
    part_ids = ({str(part_identity(p).get('system_id') or '') for p in chosen}
                if part_index is not None else None)
    return tuple(f for f in snapshot.findings if f.get('metadata_id') == metadata_id
                 and (part_ids is None or str(f.get('archive_part_id') or '') in part_ids))


def format_rows(snapshot: AnalysisSnapshot) -> tuple[dict[str, Any], ...]:
    result = []
    for item in snapshot.format_statistics.get('format_groups') or ():
        if not isinstance(item, dict):
            continue
        result.append({
            'puid': str(item.get('puid') or ''),
            'name': str(item.get('format') or ''),
            'version': str(item.get('version') or ''),
            'count': _int_or_none(item.get('count')),
        })
    return tuple(sorted(result, key=lambda x: (-(x['count'] or 0), x['puid'])))


def observed_span(snapshot: AnalysisSnapshot, part_index: int | None = None) -> str:
    rows = annual_rows(snapshot, part_index)
    return f'{rows[0][0]}-{rows[-1][0]}' if rows else 'Ukjent'
