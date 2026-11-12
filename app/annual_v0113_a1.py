"""Annual totals with explicit coverage, derived only from saved Work evidence.

A partial sum is a known subtotal, never a complete archive-wide total.
"""
from __future__ import annotations

from app.result_evidence_v018_a13 import (
    AnnualTable, METRICS, MAX_YEARS, _metric_values, _parts,
    _unique_work_snapshots, annual_scopes,
)


def annual_table_with_coverage(snapshots, scope_key="all") -> AnnualTable:
    snapshots = _unique_work_snapshots(snapshots)
    scopes = {scope.key: scope for scope in annual_scopes(snapshots)}
    if scope_key not in scopes:
        raise ValueError("Ukjent årsomfang: " + str(scope_key))
    scope = scopes[scope_key]
    selected = []
    warnings = []
    if not scope.job_uid and len(snapshots) > 1:
        warnings.append(
            "Flere uttrekk summeres uten automatisk deduplisering på tvers av uttrekk."
        )
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

    observed = set()
    series_by_part = []
    for shot, part in selected:
        series = {}
        for metric, label in METRICS:
            values = _metric_values(part, metric)
            if values is None:
                name = str((part.get("archive_part") or {}).get("title") or "Ukjent arkivdel")
                warnings.append(f"{shot.job.name} / {name}: {label} per år mangler eller er ugyldig.")
            else:
                observed.update(values)
            series[metric] = values
        series_by_part.append(series)
    if len(observed) > MAX_YEARS:
        warnings.append("Årsgrunnlaget omfatter for mange år og er avkortet.")
    years = sorted(observed)[:MAX_YEARS]
    rows = []
    partial_cells = 0
    for year in years:
        row = {"year": year, "coverage": {}}
        for metric, _label in METRICS:
            known = [part[metric][year] for part in series_by_part
                     if part[metric] is not None and year in part[metric]]
            available = len(known)
            count = len(series_by_part)
            row[metric] = sum(known) if known else None
            row["coverage"][metric] = (available, count)
            if available and available < count:
                partial_cells += 1
        rows.append(row)
    if partial_cells:
        warnings.insert(0,
            f"{partial_cells} årsverdier er delsummer med ufullstendig dekning. "
            "Disse er ikke fullstendige totaler; manglende verdier er ukjente, ikke null."
        )
    return AnnualTable(scope, tuple(rows), len(selected), tuple(dict.fromkeys(warnings)), tuple(years))
