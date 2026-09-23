
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

    Importene beholdes separat. Sammendraget skiller mellom:
      * unike kontrollområder på tvers av alle importer
      * forekomster summert per import
    """
    work = Path(work_operations)
    imports = list_arkade5_imports(work)
    dwm_ids = _dwm_test_ids_present(depot_model)

    rows: list[dict[str, Any]] = []

    occurrence_totals = {
        "arkade_errors": 0,
        "arkade_warnings": 0,
        "covered_by_arkade": 0,
        "covered_by_both": 0,
        "covered_by_dwm": 0,
        "not_covered_in_run": 0,
    }

    unique_sets = {
        "arkade_errors": set(),
        "arkade_warnings": set(),
        "covered_by_arkade": set(),
        "covered_by_both": set(),
        "covered_by_dwm": set(),
        "not_covered_in_run": set(),
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

        for key in occurrence_totals:
            occurrence_totals[key] += int(summary.get(key) or 0)

        for item in coverage.get("arkade_control_areas") or []:
            control_id = str(item.get("control_id") or "").strip()
            if not control_id:
                continue

            combined_status = str(item.get("combined_status") or "")
            if combined_status in unique_sets:
                unique_sets[combined_status].add(control_id)

            arkade_status = str((item.get("arkade") or {}).get("status") or "")
            if arkade_status == "error":
                unique_sets["arkade_errors"].add(control_id)
            elif arkade_status == "warning":
                unique_sets["arkade_warnings"].add(control_id)

        rows.append({
            "import_id": import_id,
            "source_version": normalized.get("source_version"),
            "source_file": source.get("original_name")
            or (normalized.get("source") or {}).get("file"),
            "source_sha256": source.get("sha256")
            or (normalized.get("source") or {}).get("sha256"),
            "preserved_file": source.get("preserved_file"),
            "normalized_file": manifest.get("normalized_file"),
            "date_of_testing": source_summary.get("date_of_testing"),
            "number_of_tests_run": source_summary.get("number_of_tests_run"),
            "number_of_errors": source_summary.get("number_of_errors"),
            "number_of_warnings": source_summary.get("number_of_warnings"),
            "coverage": coverage,
        })

    unique_summary = {
        key: len(values)
        for key, values in unique_sets.items()
    }
    unique_summary["imports"] = len(rows)

    return {
        "format_version": 2,
        "evidence_type": "arkade5_combined_coverage_for_depot_report",
        "principles": {
            "all_imports_remain_separate": True,
            "arkade_does_not_become_dwm_master": True,
            "arkade_does_not_change_internal_technical_status": True,
            "arkade_errors_are_review_evidence": True,
            "summary_counts_are_unique_control_areas": True,
            "occurrence_counts_are_kept_separately": True,
        },
        "dwm_test_ids_present": dwm_ids,
        "summary": unique_summary,
        "occurrences": {
            "imports": len(rows),
            **occurrence_totals,
        },
        "unique_control_ids": {
            key: sorted(values)
            for key, values in unique_sets.items()
        },
        "imports": rows,
    }


def add_arkade5_review_points(
    depot_model: dict[str, Any],
    external: dict[str, Any],
) -> None:
    """Expose external errors/warnings as review points, not automatic decisions."""
    summary = external.get("summary") or {}
    occurrences = external.get("occurrences") or {}

    errors = int(summary.get("arkade_errors") or 0)
    warnings = int(summary.get("arkade_warnings") or 0)
    covered = int(summary.get("covered_by_arkade") or 0)
    imports = int(summary.get("imports") or 0)

    error_occurrences = int(occurrences.get("arkade_errors") or errors)
    warning_occurrences = int(occurrences.get("arkade_warnings") or warnings)
    covered_occurrences = int(occurrences.get("covered_by_arkade") or covered)

    if imports <= 0:
        return

    deviations = depot_model.setdefault("deviations", [])

    if errors:
        text = f"Arkade 5-ekstern evidens inneholder {errors} unike kontrollområder med feil."
        if error_occurrences != errors:
            text += (
                f" Dette tilsvarer {error_occurrences} feilforekomster "
                f"på tvers av {imports} importer."
            )
        deviations.append({
            "category": "arkade5_external_errors",
            "severity": "review",
            "summary": text,
            "requires_review": True,
            "note": (
                "Arkade-resultatene er ekstern evidens og endrer ikke automatisk "
                "DWM sin interne tekniske status eller depotets faglige konklusjon."
            ),
        })

    if warnings:
        text = (
            f"Arkade 5-ekstern evidens inneholder "
            f"{warnings} unike kontrollområder med advarsel."
        )
        if warning_occurrences != warnings:
            text += (
                f" Dette tilsvarer {warning_occurrences} advarselsforekomster "
                f"på tvers av {imports} importer."
            )
        deviations.append({
            "category": "arkade5_external_warnings",
            "severity": "review",
            "summary": text,
            "requires_review": True,
        })

    if covered:
        text = (
            f"Arkade 5 gir evidens for {covered} unike kontrollområder "
            "uten DWM-resultat i kjøringen."
        )
        if covered_occurrences != covered:
            text += (
                f" De forekommer {covered_occurrences} ganger "
                f"på tvers av {imports} importer."
            )
        deviations.append({
            "category": "arkade5_fills_dwm_gaps",
            "severity": "information",
            "summary": text,
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
    occurrences = external.get("occurrences") or {}

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

    unique_covered = int(summary.get("covered_by_arkade") or 0)
    occurrence_covered = int(occurrences.get("covered_by_arkade") or unique_covered)
    coverage_text = str(unique_covered)
    if occurrence_covered != unique_covered:
        coverage_text += f" ({occurrence_covered} forekomster på tvers av importer)"

    section = f"""
<h2>8. Ekstern validering – Arkade 5</h2>
<div class="note">
Arkade 5-resultater er separat ekstern evidens. De kan dokumentere kontrollområder
som DWM ikke dekker selv, men blir ikke gjort om til DWM-masterresultater og gir
ikke automatisk depotgodkjenning eller avvisning.
</div>
<p><strong>Importerte Arkade-kjøringer:</strong> {escape(str(summary.get('imports', 0)))}</p>
<p><strong>Unike kontrollområder dekket av Arkade uten DWM-resultat:</strong> {escape(coverage_text)}</p>
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
