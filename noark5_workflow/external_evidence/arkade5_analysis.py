from __future__ import annotations

from typing import Any

from .arkade5_coverage import build_arkade5_coverage


def _messages(test: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in test.get("results") or []:
        if not isinstance(item, dict):
            continue
        location = item.get("location") or {}
        rows.append({
            "type": item.get("result_type"),
            "message": str(item.get("message") or ""),
            "file": location.get("file_name"),
            "line_numbers": location.get("line_numbers"),
            "result_set_path": item.get("result_set_path") or [],
        })
    return rows


def _attention_level(test: dict[str, Any], coverage: dict[str, Any], reconciliation: dict[str, Any] | None) -> str:
    status = str(test.get("source_status") or "").casefold()
    if status == "error" or int(test.get("number_of_errors") or 0) > 0:
        return "error"
    if status == "warning":
        return "warning"
    if reconciliation and reconciliation.get("status") == "mismatch":
        return "review"
    if coverage.get("classification") in {"known_non_equivalent", "unmapped"}:
        return "review"
    return "ok"


def _explanation(test: dict[str, Any], coverage: dict[str, Any], reconciliation: dict[str, Any] | None) -> str:
    status = str(test.get("source_status") or "").casefold()
    if status == "error" or int(test.get("number_of_errors") or 0) > 0:
        return "Arkade 5 har registrert feil i dette testpunktet. Se funnene og lokasjonen(e) under."
    if status == "warning":
        return "Arkade 5 har registrert advarsel i dette testpunktet. Punktet bør vurderes før depotkonklusjon."
    if reconciliation and reconciliation.get("status") == "mismatch":
        return "Arkade 5 og DWM har sammenlignbare verdier som ikke stemmer overens. Avviket bør undersøkes."
    classification = coverage.get("classification")
    if classification == "known_non_equivalent":
        return "DWM har relatert kontroll, men semantikken er dokumentert som ikke direkte sammenlignbar."
    if classification == "unmapped":
        return "Arkade-testen er foreløpig ikke kartlagt mot en DWM-test. Resultatet beholdes som selvstendig ekstern evidens."
    if classification == "candidate":
        return "DWM har kontroll(er) på samme Noark 5-testpunkt, men ekvivalensen er ikke kvalitetssikret."
    if classification == "equivalent":
        if reconciliation and reconciliation.get("status") == "match":
            return "Arkade 5-resultatet er direkte sammenlignbart med DWM, og de sammenlignede verdiene stemmer."
        return "Testpunktet er dokumentert som direkte sammenlignbart med DWM."
    return "Arkade 5-resultatet er bevart som ekstern evidens."


def build_arkade5_analysis(
    normalized: dict[str, Any],
    reconciliation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    coverage_model = build_arkade5_coverage(normalized)
    coverage = {
        str(row.get("arkade_test_id") or ""): row
        for row in coverage_model.get("items") or []
    }
    reconciliation_rows = {
        str(row.get("arkade_test_id") or ""): row
        for row in (reconciliation or {}).get("items") or []
    }

    items = []
    counts = {"error": 0, "warning": 0, "review": 0, "ok": 0}
    for test in normalized.get("tests") or []:
        test_id = str(test.get("test_id") or "")
        cov = coverage.get(test_id) or {}
        rec = reconciliation_rows.get(test_id)
        level = _attention_level(test, cov, rec)
        counts[level] += 1
        messages = _messages(test)
        items.append({
            "test_id": test_id,
            "test_name": test.get("test_name"),
            "test_type": test.get("test_type"),
            "test_description": test.get("test_description"),
            "arkade_status": test.get("source_status"),
            "number_of_errors": int(test.get("number_of_errors") or 0),
            "attention_level": level,
            "explanation": _explanation(test, cov, rec),
            "coverage_classification": cov.get("classification"),
            "coverage_reason": cov.get("reason"),
            "dwm_candidates": cov.get("dwm_candidates") or [],
            "reconciliation": rec,
            "findings": messages,
        })

    priority = {"error": 0, "warning": 1, "review": 2, "ok": 3}
    items.sort(key=lambda row: (priority[row["attention_level"]], row["test_id"]))

    source_summary = normalized.get("summary") or {}
    return {
        "format_version": 1,
        "analysis_type": "arkade5_human_review",
        "source_system": "Arkade 5",
        "source_version": normalized.get("source_version"),
        "source": normalized.get("source") or {},
        "source_summary": source_summary,
        "summary": {
            "tests": len(items),
            **counts,
            "needs_attention": counts["error"] + counts["warning"] + counts["review"],
        },
        "items": items,
        "principle": (
            "Analysen forklarer og prioriterer Arkade 5-resultater. "
            "Den er ikke en automatisk depotgodkjenning eller depotavvisning."
        ),
    }
