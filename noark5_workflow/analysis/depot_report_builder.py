from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _find_view(presentation: dict[str, Any], view_id: str) -> dict[str, Any] | None:
    for view in presentation.get("views", []):
        if view.get("id") == view_id:
            return view
    return None


def _iter_fields(view: dict[str, Any] | None):
    if not view:
        return
    for section in view.get("sections", []):
        for field in section.get("fields", []):
            yield section, field


def _field_map(view: dict[str, Any] | None) -> dict[str, Any]:
    return {
        field.get("id"): field
        for _, field in _iter_fields(view)
        if field.get("id")
    }


def _ok_value(field: dict[str, Any] | None, default=None):
    if not field or field.get("status") != "ok":
        return default
    return field.get("value", default)


def _field_source(field: dict[str, Any] | None) -> dict[str, Any] | None:
    if not field:
        return None
    test_id = field.get("source_test_id") or field.get("source_test")
    path = field.get("source_path")
    if not test_id and not path:
        return None
    return {"test_id": test_id, "path": path}


def _classify_standard_value_checks(checks: dict[str, Any]) -> dict[str, int]:
    counts = {
        "all_observed_values_standard": 0,
        "additional_observed_values": 0,
        "no_observed_values": 0,
        "other": 0,
    }

    def walk(value):
        if isinstance(value, dict):
            status = value.get("status")
            if status in counts:
                counts[status] += 1
            elif status:
                counts["other"] += 1
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)

    walk(checks)
    return counts


def _reconciliation_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"match": 0, "mismatch": 0, "not_comparable": 0, "other": 0}

    def walk(value):
        if isinstance(value, dict):
            status = value.get("status")
            if status in counts:
                counts[status] += 1
            elif status in {"ok", "error"}:
                pass
            elif status:
                counts["other"] += 1
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)

    for row in rows:
        walk(row.get("reconciliation_summary"))
    return counts


def build_depot_report_model(
    presentation: dict[str, Any],
    *,
    source_presentation_file: str = "",
) -> dict[str, Any]:
    whole = _find_view(presentation, "whole_extraction_overview")
    archive_parts = _find_view(presentation, "archive_part_overview")
    validation = _find_view(presentation, "validation_evidence")
    depot = _find_view(presentation, "depot_control_summary")

    whole_fields = _field_map(whole)
    depot_fields = _field_map(depot)

    summary_ids = (
        "archive_count",
        "archive_creator_count",
        "archive_part_count",
        "classification_system_count",
        "class_count",
        "folder_count",
        "registration_count",
        "journalpost_count",
        "document_description_count",
        "document_object_count",
    )
    summary = {}
    summary_sources = {}
    for field_id in summary_ids:
        field = whole_fields.get(field_id)
        summary[field_id] = _ok_value(field)
        src = _field_source(field)
        if src:
            summary_sources[field_id] = src

    validation_rows = []
    technical_summary = {"ok": 0, "legacy_disabled": 0, "error": 0, "other": 0}
    standard_value_rows = []

    if validation:
        for row in validation.get("tests", []):
            status = row.get("status")
            if status == "ok":
                technical_summary["ok"] += 1
            elif status == "disabled_by_legacy_source":
                technical_summary["legacy_disabled"] += 1
            elif status == "error":
                technical_summary["error"] += 1
            else:
                technical_summary["other"] += 1

            validation_row = {
                "test_id": row.get("test_id"),
                "legacy_job_id": row.get("legacy_job_id"),
                "test_point": row.get("test_point"),
                "status": status,
                "reconciliation_summary": row.get("reconciliation_summary"),
            }
            validation_rows.append(validation_row)

            std = row.get("standard_value_checks") or {}
            if std:
                standard_value_rows.append({
                    "test_id": row.get("test_id"),
                    "legacy_job_id": row.get("legacy_job_id"),
                    "test_point": row.get("test_point"),
                    "checks": std,
                    "status_counts": _classify_standard_value_checks(std),
                })

    reconciliation = _reconciliation_counts(validation_rows)

    standard_value_summary = {
        "tests_with_checks": len(standard_value_rows),
        "status_counts": {
            "all_observed_values_standard": 0,
            "additional_observed_values": 0,
            "no_observed_values": 0,
            "other": 0,
        },
    }
    for row in standard_value_rows:
        for key, value in row["status_counts"].items():
            standard_value_summary["status_counts"][key] += value

    archive_part_rows = []
    if archive_parts:
        for row in archive_parts.get("archive_parts", []):
            fields = {}
            sources = {}
            for section in row.get("sections", []):
                for field in section.get("fields", []):
                    fid = field.get("id")
                    if not fid:
                        continue
                    fields[fid] = field
                    src = _field_source(field)
                    if src:
                        sources[fid] = src

            identity = row.get("archive_part", {})
            archive_part_rows.append({
                "archive_part": identity,
                "folder_count": _ok_value(fields.get("folder_count")),
                "registration_count": _ok_value(fields.get("registration_count")),
                "journalpost_count": _ok_value(fields.get("journalpost_count")),
                "document_description_count": _ok_value(fields.get("document_description_count")),
                "document_object_count": _ok_value(fields.get("document_object_count")),
                "screening_count": _ok_value(fields.get("screening_count")),
                "disposal_decision_count": _ok_value(fields.get("disposal_decision_count")),
                "performed_disposal_count": _ok_value(fields.get("performed_disposal_count")),
                "deletion_count": _ok_value(fields.get("deletion_count")),
                "sources": sources,
            })

    deviations = []

    if technical_summary["error"] > 0:
        deviations.append({
            "category": "technical_error",
            "severity": "serious",
            "summary": f"{technical_summary['error']} tekniske testfeil er registrert.",
            "requires_review": True,
        })

    if reconciliation["mismatch"] > 0:
        deviations.append({
            "category": "reconciliation_mismatch",
            "severity": "serious",
            "summary": f"{reconciliation['mismatch']} reconciliation-avvik er registrert.",
            "requires_review": True,
        })

    additional = standard_value_summary["status_counts"]["additional_observed_values"]
    if additional > 0:
        deviations.append({
            "category": "additional_observed_values",
            "severity": "review",
            "summary": (
                f"{additional} standardverdikontroller inneholder observerte verdier "
                "utover registrerte standardverdier."
            ),
            "requires_review": True,
            "note": (
                "Dette er ikke automatisk en feil i uttrekket. Verdiene skal dokumenteres "
                "og vurderes i kontekst."
            ),
        })

    technical_status = (
        "error"
        if technical_summary["error"] > 0 or reconciliation["mismatch"] > 0
        else "ok"
    )

    assessment = {
        "status": "requires_clarification",
        "automatic_decision": False,
        "reason": (
            "Depotets faglige aksept eller krav om nytt uttrekk registreres etter "
            "gjennomgang av tekniske resultater, innhold og dokumenterte avvik."
        ),
        "archive_creator_responsibility": (
            "Arkivskaper er ansvarlig for innholdet i uttrekket."
        ),
        "new_extraction_guidance": (
            "Nytt uttrekk vurderes ved alvorlige struktur- eller innholdsmangler. "
            "Andre avvik dokumenteres og forelegges arkivskaper for lesing og aksept."
        ),
    }

    evidence = {
        "source_presentation_profile": presentation.get("profile_id"),
        "source_presentation_file": source_presentation_file,
        "source_view_ids": [
            view.get("id")
            for view in presentation.get("views", [])
            if view.get("id")
        ],
        "summary_sources": summary_sources,
    }

    return {
        "depot_report_model_format_version": 2,
        "report_type": "noark5_depot_validation",
        "summary": summary,
        "technical_validation": {
            "status": technical_status,
            "summary": technical_summary,
            "reconciliation": reconciliation,
            "tests": validation_rows,
        },
        "archive_parts": archive_part_rows,
        "standard_values": {
            "summary": standard_value_summary,
            "tests": standard_value_rows,
        },
        "deviations": deviations,
        "depot_control": {
            "available": bool(depot),
            "fields": depot_fields,
        },
        "assessment": assessment,
        "evidence": evidence,
    }


def write_depot_report_html(model: dict[str, Any], path: str | Path) -> None:
    path = Path(path)

    def esc(value):
        if value is None:
            return ""
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def count(value):
        return "–" if value is None else esc(value)

    summary = model["summary"]
    tech = model["technical_validation"]["summary"]
    rec = model["technical_validation"]["reconciliation"]
    std = model["standard_values"]["summary"]

    summary_rows = [
        ("Arkiv", summary.get("archive_count")),
        ("Arkivskapere", summary.get("archive_creator_count")),
        ("Arkivdeler", summary.get("archive_part_count")),
        ("Klassifikasjonssystem", summary.get("classification_system_count")),
        ("Klasser", summary.get("class_count")),
        ("Mapper", summary.get("folder_count")),
        ("Registreringer", summary.get("registration_count")),
        ("Journalposter", summary.get("journalpost_count")),
        ("Dokumentbeskrivelser", summary.get("document_description_count")),
        ("Dokumentobjekter", summary.get("document_object_count")),
    ]
    summary_html = "".join(
        f"<tr><th>{esc(label)}</th><td>{count(value)}</td></tr>"
        for label, value in summary_rows
    )

    archive_part_html = ""
    for row in model["archive_parts"]:
        identity = row.get("archive_part", {})
        archive_part_html += (
            "<tr>"
            f"<td>{esc(identity.get('system_id'))}</td>"
            f"<td>{esc(identity.get('title') or identity.get('name'))}</td>"
            f"<td>{count(row.get('folder_count'))}</td>"
            f"<td>{count(row.get('registration_count'))}</td>"
            f"<td>{count(row.get('journalpost_count'))}</td>"
            f"<td>{count(row.get('document_description_count'))}</td>"
            f"<td>{count(row.get('document_object_count'))}</td>"
            f"<td>{count(row.get('screening_count'))}</td>"
            f"<td>{count(row.get('disposal_decision_count'))}</td>"
            f"<td>{count(row.get('performed_disposal_count'))}</td>"
            f"<td>{count(row.get('deletion_count'))}</td>"
            "</tr>"
        )

    deviation_html = ""
    if model["deviations"]:
        for item in model["deviations"]:
            deviation_html += (
                "<div class='deviation'>"
                f"<strong>{esc(item.get('category'))}</strong>: "
                f"{esc(item.get('summary'))}"
            )
            if item.get("note"):
                deviation_html += f"<br><span>{esc(item['note'])}</span>"
            deviation_html += "</div>"
    else:
        deviation_html = "<p>Ingen automatiske vurderingspunkter ble identifisert.</p>"

    html_doc = f"""<!doctype html>
<html lang="no">
<head>
<meta charset="utf-8">
<title>Depotvalideringsrapport – Noark 5</title>
<style>
body {{ font-family: Arial, sans-serif; max-width: 1280px; margin: 2rem auto; line-height: 1.45; }}
h1, h2 {{ margin-top: 1.5em; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .95rem; }}
th, td {{ border: 1px solid #bbb; padding: .45rem; text-align: left; vertical-align: top; }}
th {{ background: #eee; }}
.note {{ border-left: 4px solid #777; padding: .75rem 1rem; background: #f7f7f7; }}
.deviation {{ border-left: 4px solid #999; padding: .65rem 1rem; margin: .75rem 0; background: #fafafa; }}
.status-ok {{ font-weight: bold; }}
.small {{ font-size: .9rem; color: #444; }}
</style>
</head>
<body>
<h1>Depotvalideringsrapport – Noark 5</h1>

<div class="note">
Rapporten er generert fra materialiserte depot-views. Den kjører ikke ny XML/XPath-analyse
og gjør ingen automatisk faglig godkjenning av uttrekket.
</div>

<h2>1. Sammendrag</h2>
<table>{summary_html}</table>

<h2>2. Teknisk validering</h2>
<p><strong>Teknisk status:</strong> {esc(model["technical_validation"]["status"])}</p>
<table>
<tr><th>OK</th><th>Legacy-deaktivert</th><th>Feil</th><th>Annet</th></tr>
<tr><td>{tech["ok"]}</td><td>{tech["legacy_disabled"]}</td><td>{tech["error"]}</td><td>{tech["other"]}</td></tr>
</table>

<h3>Reconciliation</h3>
<table>
<tr><th>Match</th><th>Mismatch</th><th>Ikke sammenlignbar</th><th>Annet</th></tr>
<tr><td>{rec["match"]}</td><td>{rec["mismatch"]}</td><td>{rec["not_comparable"]}</td><td>{rec["other"]}</td></tr>
</table>

<h2>3. Arkivdeler</h2>
<table>
<tr>
<th>systemID</th><th>Tittel/navn</th><th>Mapper</th><th>Registreringer</th>
<th>Journalposter</th><th>Dok.beskr.</th><th>Dok.obj.</th>
<th>Skjerming</th><th>Kassasjonsvedtak</th><th>Utført kassasjon</th><th>Sletting</th>
</tr>
{archive_part_html}
</table>

<h2>4. Standardverdier og observerte verdier</h2>
<table>
<tr>
<th>Tester med kontroller</th>
<th>Alle observerte verdier standard</th>
<th>Ekstra observerte verdier</th>
<th>Ingen observerte verdier</th>
<th>Annet</th>
</tr>
<tr>
<td>{std["tests_with_checks"]}</td>
<td>{std["status_counts"]["all_observed_values_standard"]}</td>
<td>{std["status_counts"]["additional_observed_values"]}</td>
<td>{std["status_counts"]["no_observed_values"]}</td>
<td>{std["status_counts"]["other"]}</td>
</tr>
</table>

<h2>5. Avvik og vurderingspunkter</h2>
{deviation_html}

<h2>6. Depotets vurdering</h2>
<p><strong>Status:</strong> {esc(model["assessment"]["status"])}</p>
<p>{esc(model["assessment"]["reason"])}</p>
<p>{esc(model["assessment"]["archive_creator_responsibility"])}</p>
<p>{esc(model["assessment"]["new_extraction_guidance"])}</p>

<h2>7. Evidens og sporbarhet</h2>
<p><strong>Kildeprofil:</strong> {esc(model["evidence"]["source_presentation_profile"])}</p>
<p><strong>Kildefil:</strong> {esc(model["evidence"]["source_presentation_file"])}</p>
<p><strong>Views:</strong> {esc(", ".join(model["evidence"]["source_view_ids"]))}</p>
<p class="small">Maskinlesbar rapportmodell inneholder source-test/source-path for nøkkeltall og arkivdelfelt.</p>
</body>
</html>
"""
    path.write_text(html_doc, encoding="utf-8")
