from __future__ import annotations

from typing import Any


_COUNT_FIELDS = (
    "folder_count",
    "registration_count",
    "journalpost_count",
    "document_description_count",
    "document_object_count",
    "screening_count",
    "disposal_decision_count",
    "performed_disposal_count",
    "deletion_count",
)
_YEAR_KEYS = ("folder", "journal", "document_description", "document_object")


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _sum_yearly(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {key: {} for key in _YEAR_KEYS}
    for row in rows:
        yearly = row.get("yearly_volume") or {}
        for key in _YEAR_KEYS:
            values = yearly.get(key) or {}
            if not isinstance(values, dict):
                continue
            for year, count in values.items():
                year_text = str(year or "")[:4]
                if len(year_text) != 4 or not year_text.isdigit():
                    continue
                result[key][year_text] = result[key].get(year_text, 0) + _int(count)
    return {key: dict(sorted(values.items())) for key, values in result.items()}


def build_all_archive_parts_summary(model: dict[str, Any]) -> dict[str, Any]:
    """Materialize one aggregate record without changing the real archive-part list."""
    rows = list(model.get("archive_parts") or [])
    yearly = _sum_yearly(rows)
    active_years = sorted({
        year
        for values in yearly.values()
        for year, count in values.items()
        if _int(count) > 0
    })

    observed_by_series: dict[str, dict[str, str | None]] = {}
    for key, values in yearly.items():
        years = sorted(year for year, count in values.items() if _int(count) > 0)
        observed_by_series[key] = {
            "first_year": years[0] if years else None,
            "last_year": years[-1] if years else None,
        }

    # Cross-source year findings are evidence, not automatic errors.  They expose
    # years where document metadata exists without corresponding folder/journal
    # activity, which is particularly useful when declared outer years are wrong.
    cross_source_findings: list[dict[str, Any]] = []
    all_years = sorted({year for values in yearly.values() for year in values})
    for year in all_years:
        folder = _int(yearly.get("folder", {}).get(year))
        journal = _int(yearly.get("journal", {}).get(year))
        description = _int(yearly.get("document_description", {}).get(year))
        obj = _int(yearly.get("document_object", {}).get(year))
        if (description or obj) and not folder and not journal:
            cross_source_findings.append({
                "year": year,
                "category": "document_activity_without_folder_or_journal",
                "requires_review": True,
                "counts": {
                    "folder": folder,
                    "journal": journal,
                    "document_description": description,
                    "document_object": obj,
                },
                "summary": (
                    f"{year}: dokumentaktivitet uten mapper/saker eller journalposter "
                    f"(dok.beskr. {description}, dok.obj. {obj})."
                ),
            })

    counts = {field: sum(_int(row.get(field)) for row in rows) for field in _COUNT_FIELDS}
    declared = ((model.get("period_reconciliation") or {}).get("declared_period") or {})

    return {
        "all_archive_parts_summary_format_version": 2,
        "archive_part_count": len(rows),
        **counts,
        "yearly_volume": yearly,
        "declared_period": {
            "start_date": declared.get("start_date"),
            "end_date": declared.get("end_date"),
            "start_year": declared.get("start_year"),
            "end_year": declared.get("end_year"),
            "source": declared.get("source") or "arkivuttrekk.xml",
        },
        "observed_period": {
            "first_year": active_years[0] if active_years else None,
            "last_year": active_years[-1] if active_years else None,
            "first_date": None,
            "last_date": None,
        },
        "observed_period_by_series": observed_by_series,
        "cross_source_year_findings": cross_source_findings,
        "review_finding_count": len(cross_source_findings),
        "note": (
            "Observerte ytterår er materialisert fra årsfordelingene for alle arkivdeler. "
            "Eksakte observerte første/siste datoer materialiseres først når kildetestene leverer dette eksplisitt."
        ),
    }
