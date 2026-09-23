from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from .arkade5 import list_arkade5_imports, load_arkade5_import
from .combined_coverage import build_combined_coverage


def _dwm_test_ids_present(depot_model: dict[str, Any]) -> list[str]:
    tests = ((depot_model.get("technical_validation") or {}).get("tests") or [])
    return sorted({
        str(row.get("test_id") or "").strip()
        for row in tests
        if str(row.get("test_id") or "").strip()
    })


def build_arkade5_depot_evidence(
    *,
    work_operations: str | Path,
    depot_model: dict[str, Any],
) -> dict[str, Any]:
    """Build report-safe Arkade evidence for all imported Arkade runs.

    Every imported Arkade report remains a separate evidence group. The function
    never picks a hidden "latest winner", never promotes Arkade to DWM master
    results, and never changes DWM's internal technical status.
    """
    work = Path(work_operations)
    imports = list_arkade5_imports(work)
    dwm_ids = _dwm_test_ids_present(depot_model)

    rows: list[dict[str, Any]] = []
    totals = {
        "imports": 0,
        "arkade_errors": 0,
        "arkade_warnings": 0,
        "covered_by_arkade": 0,
        "covered_by_both": 0,
        "covered_by_dwm": 0,
        "not_covered_in_run": 0,
    }

    for manifest in imports:
        import_id = str(manifest.get("import_id") or "")
        if not import_id:
            continue
        loaded = load_arkade5_import(work, import_id)
        normalized = loaded.get("normalized") or {}
        coverage = build_combined_coverage(
            arkade_normalized=normalized,
            dwm_test_ids_present=dwm_ids,
        )
        summary = coverage.get("summary") or {}
        source_summary = normalized.get("summary") or {}
        source = manifest.get("source") or {}

        totals["imports"] += 1
        for key in (
            "arkade_errors",
            "arkade_warnings",
            "covered_by_arkade",
            "covered_by_both",
            "covered_by_dwm",
            "not_covered_in_run",
        ):
            totals[key] += int(summary.get(key) or 0)

        rows.append({
            "import_id": import_id,
            "source_version": normalized.get("source_version"),
            "source_file": source.get("original_name") or (normalized.get("source") or {}).get("file"),
            "source_sha256": source.get("sha256") or (normalized.get("source") or {}).get("sha256"),
            "preserved_file": source.get("preserved_file"),
            "normalized_file": manifest.get("normalized_file"),
            "date_of_testing": source_summary.get("date_of_testing"),
            "number_of_tests_run": source_summary.get("number_of_tests_run"),
            "number_of_errors": source_summary.get("number_of_errors"),
            "number_of_warnings": source_summary.get("number_of_warnings"),
            "coverage": coverage,
        })

    return {
        "format_version": 1,
        "evidence_type": "arkade5_combined_coverage_for_depot_report",
        "principles": {
            "all_imports_remain_separate": True,
            "arkade_does_not_become_dwm_master": True,
            "arkade_does_not_change_internal_technical_status": True,
            "arkade_errors_are_review_evidence": True,
        },
        "dwm_test_ids_present": dwm_ids,
        "summary": totals,
        "imports": rows,
    }


def add_arkade5_review_points(
    depot_model: dict[str, Any],
    external: dict[str, Any],
) -> None:
    """Expose external errors/warnings as review points, not automatic decisions."""
    summary = external.get("summary") or {}
    errors = int(summary.get("arkade_errors") or 0)
    warnings = int(summary.get("arkade_warnings") or 0)
    covered = int(summary.get("covered_by_arkade") or 0)
    imports = int(summary.get("imports") or 0)

    if imports <= 0:
        return

    deviations = depot_model.setdefault("deviations", [])
    if errors:
        deviations.append({
            "category": "arkade5_external_errors",
            "severity": "review",
            "summary": f"Arkade 5-ekstern evidens inneholder {errors} kontrollområder med feil.",
            "requires_review": True,
            "note": (
                "Arkade-resultatene er ekstern evidens og endrer ikke automatisk "
                "DWM sin interne tekniske status eller depotets faglige konklusjon."
            ),
        })
    if warnings:
        deviations.append({
            "category": "arkade5_external_warnings",
            "severity": "review",
            "summary": f"Arkade 5-ekstern evidens inneholder {warnings} kontrollområder med advarsel.",
            "requires_review": True,
        })
    if covered:
        deviations.append({
            "category": "arkade5_fills_dwm_gaps",
            "severity": "information",
            "summary": f"Arkade 5 gir evidens for {covered} kontrollområder uten DWM-resultat i kjøringen.",
            "requires_review": False,
        })


def attach_arkade5_to_depot_model(
    depot_model: dict[str, Any],
    *,
    work_operations: str | Path,
) -> dict[str, Any]:
    external = build_arkade5_depot_evidence(
        work_operations=work_operations,
        depot_model=depot_model,
    )
    depot_model["external_validation"] = {"arkade5": external}
    depot_model.setdefault("evidence", {})["arkade5_import_count"] = (
        external.get("summary") or {}
    ).get("imports", 0)
    add_arkade5_review_points(depot_model, external)
    return depot_model


def inject_arkade5_html(path: str | Path, depot_model: dict[str, Any]) -> None:
    """Insert one readable external-evidence section into an existing report HTML."""
    path = Path(path)
    external = ((depot_model.get("external_validation") or {}).get("arkade5") or {})
    imports = external.get("imports") or []
    summary = external.get("summary") or {}

    if not imports or not path.is_file():
        return

    rows = []
    for item in imports:
        cov = (item.get("coverage") or {}).get("summary") or {}
        rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('date_of_testing') or '–'))}</td>"
            f"<td>{escape(str(item.get('source_version') or '–'))}</td>"
            f"<td>{escape(str(item.get('import_id') or '–'))}</td>"
            f"<td>{escape(str(cov.get('covered_by_arkade', 0)))}</td>"
            f"<td>{escape(str(cov.get('covered_by_both', 0)))}</td>"
            f"<td>{escape(str(cov.get('arkade_errors', 0)))}</td>"
            f"<td>{escape(str(cov.get('arkade_warnings', 0)))}</td>"
            "</tr>"
        )

    section = f"""
<h2>8. Ekstern validering – Arkade 5</h2>
<div class="note">
Arkade 5-resultater er separat ekstern evidens. De kan dokumentere kontrollområder
som DWM ikke dekker selv, men blir ikke gjort om til DWM-masterresultater og gir
ikke automatisk depotgodkjenning eller avvisning.
</div>
<p><strong>Importerte Arkade-kjøringer:</strong> {escape(str(summary.get('imports', 0)))}</p>
<p><strong>Kontrollområder dekket av Arkade uten DWM-resultat:</strong> {escape(str(summary.get('covered_by_arkade', 0)))}</p>
<table>
<tr><th>Testdato</th><th>Arkade-versjon</th><th>Import-ID</th><th>Kun Arkade</th><th>Begge</th><th>Feil</th><th>Advarsler</th></tr>
{''.join(rows)}
</table>
<p class="small">Komplett normalisert og rå Arkade-evidens er bevart under work_operations/external_evidence/arkade5/.</p>
"""

    html = path.read_text(encoding="utf-8")
    marker = "</body>"
    if marker in html:
        html = html.replace(marker, section + "\n" + marker, 1)
    else:
        html += "\n" + section
    path.write_text(html, encoding="utf-8")
