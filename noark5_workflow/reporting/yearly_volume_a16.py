"""Read-only yearly production totals from existing archive-part summaries."""
from __future__ import annotations

METRICS = ('folder', 'journal', 'document_description', 'document_object')
# registration is intentionally optional: older reports did not save this series.
OPTIONAL_METRIC = 'registration'


def archive_part_volumes(report):
    """Return (system_id, title, normalized year totals) without modifying report."""
    parts = []
    for entry in (report or {}).get('archive_parts') or []:
        info = entry.get('archive_part') or {}
        volumes = entry.get('yearly_volume') or {}
        totals = {}
        for metric in METRICS:
            for year, raw in (volumes.get(metric) or {}).items():
                try:
                    y, quantity = int(year), int(raw)
                except (ValueError, TypeError):
                    continue
                if not 1000 <= y <= 9999 or quantity < 0:
                    continue
                totals.setdefault(y, {key: 0 for key in METRICS})[metric] += quantity
        parts.append((str(info.get('system_id') or ''), str(info.get('title') or 'Uten navn'), totals))
    return parts


def combined_volumes(parts):
    combined = {}
    for _, _, totals in parts:
        for year, counts in totals.items():
            row = combined.setdefault(year, {key: 0 for key in METRICS})
            for key in METRICS:
                row[key] += counts.get(key, 0)
    return combined


def sparse_boundary_years(totals):
    """Identify boundary years with disproportionately few records; suggestion only."""
    years = sorted(y for y, v in totals.items() if any(v.values()))
    if len(years) < 3:
        return []
    typical = max(sum(row.values()) for row in totals.values())
    if not typical:
        return []
    result = []
    for y in (years[0], years[-1]):
        count = sum(totals[y].values())
        if count <= max(2, typical // 100):
            result.append((y, count))
    return result


def registration_years(report, *, archive_part_id=None):
    """Return independent registration counts only if every selected part has them.

    Never substitute journalpost counts for registration counts. An absent
    annual registration series is unknown, NOT a zero count.
    """
    entries = (report or {}).get('archive_parts') or []
    if archive_part_id is not None:
        entries = [p for p in entries if str((p.get('archive_part') or {}).get('system_id') or '') == str(archive_part_id)]
    if not entries:
        return None
    accum = {}
    for entry in entries:
        yearly = (entry.get('yearly_volume') or {}).get(OPTIONAL_METRIC)
        if not isinstance(yearly, dict) or not yearly:
            return None
        for year, count in yearly.items():
            try:
                y, n = int(year), int(count)
            except (ValueError, TypeError):
                return None
            if y < 1000 or y > 9999 or n < 0:
                return None
            accum[y] = accum.get(y, 0) + n
    # A year absent from a supplied registration series is unknown, not zero.
    observed = set()
    for entry in entries:
        for metric in METRICS:
            for year in ((entry.get('yearly_volume') or {}).get(metric) or {}):
                try:
                    observed.add(int(year))
                except (ValueError, TypeError):
                    continue
    if not observed.issubset(accum):
        return None
    return accum
