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
            "location_string": location.get("string"),
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
    if coverage.get("classification") in {"partial", "complementary", "arkade_only", "unmapped"}:
        return "review"
    return "ok"


def _explanation(test: dict[str, Any], coverage: dict[str, Any], reconciliation: dict[str, Any] | None) -> str:
    status = str(test.get("source_status") or "").casefold()
    if status == "error" or int(test.get("number_of_errors") or 0) > 0:
        return "Arkade 5 har registrert feil i dette testpunktet. Se funnene og lokasjonen(e) under."
    if status == "warning":
        return "Arkade 5 har registrert advarsel i dette testpunktet. Punktet bør vurderes før depotkonklusjon."
    if reconciliation and reconciliation.get("status") == "mismatch":
        return "Arkade 5 og DWM har eksplisitt sammenlignbare verdier som ikke stemmer overens. Avviket bør undersøkes."
    classification = coverage.get("classification")
    if classification == "partial":
        return "Arkade 5 og DWM dekker samme område delvis, men kontrollsemantikken er ikke identisk. Begge resultater skal beholdes."
    if classification == "complementary":
        return "Arkade 5 og DWM har komplementære kontroller. Ingen av resultatene erstatter det andre."
    if classification == "arkade_only":
        return "Denne kontrollen dekkes av Arkade 5 og fyller et dokumentert hull i DWMs egne tester."
    if classification == "unmapped":
        return "Arkade-testen finnes ikke i gjeldende verifiserte mapping og beholdes som selvstendig ekstern evidens."
    if classification == "equivalent":
        if reconciliation and reconciliation.get("status") == "match":
            return "Arkade 5-resultatet er eksplisitt sammenlignbart med DWM, og de sammenlignede verdiene stemmer."
        return "Testpunktet er dokumentert som semantisk ekvivalent med den koblede DWM-kontrollen."
    return "Arkade 5-resultatet er bevart som ekstern evidens."


def build_arkade5_analysis(normalized: dict[str, Any], reconciliation: dict[str, Any] | None = None) -> dict[str, Any]:
    coverage_model = build_arkade5_coverage(normalized)
    coverage = {str(row.get("arkade_test_id") or ""): row for row in coverage_model.get("items") or []}
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
            "findings": _messages(test),
        })

    priority = {"error": 0, "warning": 1, "review": 2, "ok": 3}
    items.sort(key=lambda row: (priority[row["attention_level"]], row["test_id"]))
    source_summary = normalized.get("summary") or {}
    return {
        "format_version": 2,
        "analysis_type": "arkade5_human_review",
        "source_system": "Arkade 5",
        "source_version": normalized.get("source_version"),
        "source": normalized.get("source") or {},
        "source_summary": source_summary,
        "coverage_mapping_id": coverage_model.get("mapping_id"),
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
