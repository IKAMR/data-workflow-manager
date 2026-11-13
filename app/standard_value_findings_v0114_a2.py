"""Read-only detail model for saved Noark 5 standard-value evidence.

A finding is one reported field/version status, NOT one distinct value.
Nothing here searches, modifies, or claims source XML occurrences.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class StandardValueFinding:
    job_uid: str
    job_name: str
    test_id: str
    test_point: str
    field: str
    version: str
    extra: dict[str, int]
    detail: dict[str, Any]
    report_path: Path | None

    @property
    def extra_total(self) -> int:
        return sum(self.extra.values())


def _extra(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    out = {}
    for key, number in value.items():
        if isinstance(number, bool):
            continue
        try:
            amount = int(number)
        except (TypeError, ValueError, OverflowError):
            continue
        if amount >= 0:
            out[str(key)] = amount
    return out


def _traverse(value: Any, trail: tuple[str, ...] = ()):
    if not isinstance(value, Mapping):
        return
    if value.get('status') == 'additional_observed_values':
        yield trail, value
        return
    for key, child in value.items():
        if isinstance(child, Mapping):
            yield from _traverse(child, trail + (str(key),))
        elif isinstance(child, list):
            for index, part in enumerate(child):
                if isinstance(part, Mapping):
                    yield from _traverse(part, trail + (str(key), str(index + 1)))


def extract_standard_value_findings(report: Mapping[str, Any] | None, *,
                                    job_uid: str = '', job_name: str = '',
                                    report_path: str | Path | None = None,
                                    limit: int = 1000) -> tuple[StandardValueFinding, ...]:
    """Extract exact stored statuses, never infer them from an aggregate count."""
    if not isinstance(report, Mapping):
        return ()
    rows = (report.get('standard_values') or {}).get('tests', [])
    if not isinstance(rows, list):
        return ()
    output = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        for trail, data in _traverse(row.get('checks') or {}):
            if len(output) >= limit:
                return tuple(output)
            version = ''
            if 'versions' in trail:
                index = trail.index('versions')
                if index + 1 < len(trail):
                    version = trail[index + 1]
            field = trail[0] if trail else ''
            output.append(StandardValueFinding(
                str(job_uid), str(job_name), str(row.get('test_id') or row.get('legacy_job_id') or ''),
                str(row.get('test_point') or ''), field, version,
                _extra(data.get('additional_observed_values')), dict(data),
                Path(report_path) if report_path else None,
            ))
    return tuple(output)


def findings_from_snapshots(snapshots: Iterable[Any]) -> tuple[StandardValueFinding, ...]:
    result = []
    for shot in snapshots:
        depot = shot.depot or {}
        result.extend(extract_standard_value_findings(
            depot, job_uid=shot.job.job_uid, job_name=shot.job.name,
            report_path=shot.results.depot_report_path))
    return tuple(result)


def source_location_present(finding: StandardValueFinding) -> bool:
    """Do not imply an XPath/source object exists just because a test ID does."""
    return bool(finding.detail.get('source_element_reference') or
                finding.detail.get('source_xpath_reference'))
