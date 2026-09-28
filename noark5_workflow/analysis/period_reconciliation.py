from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_result(run_dir: Path, test_id: str) -> dict[str, Any]:
    path = run_dir / "results" / (test_id.replace(".", "_") + ".json")
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _years(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, int] = {}
    for key, count in value.items():
        year = str(key or "")[:4]
        if len(year) != 4 or not year.isdigit():
            continue
        try:
            amount = int(count)
        except (TypeError, ValueError):
            continue
        out[year] = out.get(year, 0) + amount
    return dict(sorted(out.items()))


def _span(counts: dict[str, int]) -> dict[str, Any]:
    active = [year for year, count in counts.items() if count]
    return {
        "first_year": min(active) if active else None,
        "last_year": max(active) if active else None,
        "active_years": active,
        "count": sum(counts.values()),
    }


def _property_values(result: dict[str, Any], name: str) -> list[str]:
    values = []
    for row in (result.get("values") or {}).get("properties") or []:
        if row.get("name") == name and str(row.get("value") or "").strip():
            values.append(str(row["value"]).strip())
    return values


def _archive_part_map(result: dict[str, Any], metric: str) -> dict[str, dict[str, Any]]:
    out = {}
    for row in (result.get("values") or {}).get("_archive_parts") or []:
        identity = row.get("archive_part") or {}
        key = str(identity.get("system_id") or identity.get("index") or "")
        if not key:
            continue
        out[key] = {
            "archive_part": identity,
            "counts": _years((row.get("values") or {}).get(metric)),
        }
    return out


def build_period_reconciliation(xpath_run_dir: str | Path) -> dict[str, Any]:
    """Build descriptive period evidence from already materialized XPath JSON.

    No source XML is recalculated here. Declared metadata is kept separate from
    observed activity and disagreements become review evidence, not automatic
    conclusions about which source is correct.
    """
    run_dir = Path(xpath_run_dir)
    c09 = _load_result(run_dir, "kdrs.c09")
    c16 = _load_result(run_dir, "kdrs.c16")
    c21 = _load_result(run_dir, "kdrs.c21")
    c24 = _load_result(run_dir, "kdrs.c24")
    h02 = _load_result(run_dir, "kdrs.h02")
    h06 = _load_result(run_dir, "kdrs.h06")
    j01 = _load_result(run_dir, "kdrs.j01")
    meta = _load_result(run_dir, "kdrs.dwm.arkivuttrekk_metadata")

    declared_start = (_property_values(meta, "startDate") or [None])[0]
    declared_end = (_property_values(meta, "endDate") or [None])[0]
    declared = {
        "source": "arkivuttrekk.xml",
        "start_date": declared_start,
        "end_date": declared_end,
        "start_year": declared_start[:4] if declared_start and len(declared_start) >= 4 else None,
        "end_year": declared_end[:4] if declared_end and len(declared_end) >= 4 else None,
        "role": "declared_by_submission_metadata",
    }

    series = {
        "folder_created": {"source": "arkivstruktur.xml / C09", "counts": _years((c09.get("values") or {}).get("created_per_year"))},
        "registration_created": {"source": "arkivstruktur.xml / C16", "counts": _years((c16.get("values") or {}).get("created_per_year"))},
        "journal_date_archive_structure": {"source": "arkivstruktur.xml / C16", "counts": _years((c16.get("values") or {}).get("journalpost_journal_date_per_year"))},
        "document_description_created": {"source": "arkivstruktur.xml / C21", "counts": _years((c21.get("values") or {}).get("document_description_created_per_year"))},
        "document_object_parent_created": {"source": "arkivstruktur.xml / C24", "counts": _years((c24.get("values") or {}).get("document_object_parent_created_per_year"))},
        "running_journal": {"source": "loependeJournal.xml / H02", "counts": _years((h02.get("values") or {}).get("journal_date_per_year"))},
        "public_journal": {"source": "offentligJournal.xml / H06", "counts": _years((h06.get("values") or {}).get("journal_date_per_year"))},
        "change_log": {"source": "endringslogg.xml / J01", "counts": _years((j01.get("values") or {}).get("changes_per_year"))},
    }
    for item in series.values():
        item["span"] = _span(item["counts"])

    journal_keys = ("journal_date_archive_structure", "running_journal", "public_journal")
    journal_counts = [series[key]["counts"] for key in journal_keys]
    journal_match = bool(journal_counts[0]) and journal_counts[0] == journal_counts[1] == journal_counts[2]

    findings = []
    if all(journal_counts):
        findings.append({
            "category": "journal_cross_source_reconciliation",
            "status": "match" if journal_match else "review",
            "requires_review": not journal_match,
            "summary": (
                "Årsfordelingen for journalposter er identisk i arkivstruktur.xml, loependeJournal.xml og offentligJournal.xml."
                if journal_match else
                "Årsfordelingen for journalposter er ikke identisk mellom arkivstruktur.xml, loependeJournal.xml og offentligJournal.xml."
            ),
            "sources": list(journal_keys),
        })

    observed_last = {
        key: item["span"]["last_year"]
        for key, item in series.items()
        if item["span"]["last_year"]
    }
    observed_first = {
        key: item["span"]["first_year"]
        for key, item in series.items()
        if item["span"]["first_year"]
    }
    if len(set(observed_last.values())) > 1:
        findings.append({
            "category": "period_source_divergence",
            "status": "review",
            "requires_review": True,
            "summary": "Observerte sluttår varierer mellom datakildene og bør vurderes i sammenheng.",
            "observed_last_years": observed_last,
        })
    if declared["start_year"] and observed_first and declared["start_year"] not in set(observed_first.values()):
        findings.append({
            "category": "declared_start_vs_observed",
            "status": "review",
            "requires_review": True,
            "summary": "Oppgitt startår i arkivuttrekk.xml avviker fra første observerte år i de materialiserte aktivitetsseriene.",
            "declared_year": declared["start_year"],
            "observed_first_years": observed_first,
        })
    if declared["end_year"] and observed_last and declared["end_year"] not in set(observed_last.values()):
        findings.append({
            "category": "declared_end_vs_observed",
            "status": "review",
            "requires_review": True,
            "summary": "Oppgitt sluttår i arkivuttrekk.xml finnes ikke som siste observerte år i aktivitetsseriene.",
            "declared_year": declared["end_year"],
            "observed_last_years": observed_last,
        })

    part_sources = {
        "folder_created": _archive_part_map(c09, "created_per_year"),
        "registration_created": _archive_part_map(c16, "created_per_year"),
        "journal_date": _archive_part_map(c16, "journalpost_journal_date_per_year"),
        "document_description_created": _archive_part_map(c21, "document_description_created_per_year"),
        "document_object_parent_created": _archive_part_map(c24, "document_object_parent_created_per_year"),
    }
    part_keys = []
    for source in part_sources.values():
        for key in source:
            if key not in part_keys:
                part_keys.append(key)
    archive_parts = []
    for key in part_keys:
        identity = next((src[key]["archive_part"] for src in part_sources.values() if key in src), {})
        metrics = {}
        all_years = set()
        for metric, source in part_sources.items():
            counts = source.get(key, {}).get("counts", {})
            metrics[metric] = {"counts": counts, "span": _span(counts)}
            all_years.update(year for year, count in counts.items() if count)
        archive_parts.append({
            "archive_part": identity,
            "observed_period": {
                "first_year": min(all_years) if all_years else None,
                "last_year": max(all_years) if all_years else None,
            },
            "metrics": metrics,
        })

    return {
        "period_reconciliation_format_version": 1,
        "principle": "Oppgitt metadata, observert aktivitet og krysskontroll holdes adskilt. Avvik er vurderingsgrunnlag, ikke automatisk fasit.",
        "source_xpath_run": str(run_dir),
        "declared_period": declared,
        "observed_series": series,
        "cross_checks": {"journal_year_distribution_match": journal_match},
        "archive_parts": archive_parts,
        "findings": findings,
        "review_finding_count": sum(1 for item in findings if item.get("requires_review")),
    }
