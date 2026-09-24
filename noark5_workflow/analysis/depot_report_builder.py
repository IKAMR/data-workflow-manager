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
    """Write the human assessment surface without recalculating source results.

    v0.1.6-a1 changes presentation only: archive parts are the primary working
    surface, while technical validation, deviations and provenance stay visibly
    separate. The JSON report model remains unchanged for compatibility.
    """
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

    def metric(label: str, value) -> str:
        return (
            "<div class='metric'>"
            f"<div class='metric-value'>{count(value)}</div>"
            f"<div class='metric-label'>{esc(label)}</div>"
            "</div>"
        )

    summary = model["summary"]
    technical = model["technical_validation"]
    tech = technical["summary"]
    rec = technical["reconciliation"]
    std = model["standard_values"]["summary"]
    deviations = list(model.get("deviations") or [])
    archive_parts = list(model.get("archive_parts") or [])

    if technical.get("status") == "error":
        overall_class = "danger"
        overall_label = "Krever behandling"
    elif deviations:
        overall_class = "warning"
        overall_label = "Krever vurdering"
    else:
        overall_class = "ok"
        overall_label = "Teknisk OK"

    headline_metrics = "".join([
        metric("Arkivdeler", summary.get("archive_part_count")),
        metric("Mapper", summary.get("folder_count")),
        metric("Registreringer", summary.get("registration_count")),
        metric("Journalposter", summary.get("journalpost_count")),
        metric("Dokumentbeskrivelser", summary.get("document_description_count")),
        metric("Dokumentobjekter", summary.get("document_object_count")),
    ])

    archive_cards = []
    for index, row in enumerate(archive_parts, start=1):
        identity = row.get("archive_part") or {}
        system_id = identity.get("system_id") or ""
        title = identity.get("title") or identity.get("name") or "Uten navn"
        card_metrics = "".join([
            metric("Mapper", row.get("folder_count")),
            metric("Registreringer", row.get("registration_count")),
            metric("Journalposter", row.get("journalpost_count")),
            metric("Dok.beskr.", row.get("document_description_count")),
            metric("Dok.obj.", row.get("document_object_count")),
            metric("Skjerming", row.get("screening_count")),
            metric("Kassasjonsvedtak", row.get("disposal_decision_count")),
            metric("Utført kassasjon", row.get("performed_disposal_count")),
            metric("Sletting", row.get("deletion_count")),
        ])
        source_count = len(row.get("sources") or {})
        archive_cards.append(
            "<article class='archive-card'>"
            "<div class='archive-card-head'>"
            "<div>"
            f"<div class='eyebrow'>Arkivdel {index}</div>"
            f"<h3>{esc(title)}</h3>"
            f"<div class='system-id'>systemID: {esc(system_id) or '–'}</div>"
            "</div>"
            f"<div class='source-count'>{source_count} sporbare felt</div>"
            "</div>"
            f"<div class='metric-grid compact'>{card_metrics}</div>"
            "</article>"
        )
    archive_part_html = "".join(archive_cards) or (
        "<div class='empty'>Ingen arkivdelsresultater er materialisert i rapporten.</div>"
    )

    deviation_html = []
    for item in deviations:
        serious = str(item.get("severity", "")).casefold() == "serious"
        css = "danger" if serious else "warning"
        deviation_html.append(
            f"<div class='finding {css}'>"
            f"<div class='finding-label'>{esc(item.get('category'))}</div>"
            f"<div>{esc(item.get('summary'))}</div>"
            + (f"<div class='finding-note'>{esc(item.get('note'))}</div>" if item.get("note") else "")
            + "</div>"
        )
    deviations_block = "".join(deviation_html) or (
        "<div class='finding ok'><div class='finding-label'>Ingen automatiske vurderingspunkter</div>"
        "Ingen automatiske avvik er identifisert i det materialiserte datagrunnlaget.</div>"
    )

    html_doc = f"""<!doctype html>
<html lang="no">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vurdering av Noark 5-uttrekk</title>
<style>
:root {{
  --bg: #f4f6f8; --panel: #ffffff; --ink: #18212b; --muted: #66717d;
  --line: #dce2e8; --soft: #eef2f5; --ok: #24734a; --ok-bg: #e9f6ef;
  --warn: #8a5a00; --warn-bg: #fff4d8; --danger: #9b2c2c; --danger-bg: #fdecec;
  --accent: #244a64; --shadow: 0 8px 24px rgba(28, 43, 54, .08);
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: "Segoe UI", Arial, sans-serif; color: var(--ink); background: var(--bg); line-height: 1.45; }}
main {{ max-width: 1480px; margin: 0 auto; padding: 28px; }}
.hero {{ background: var(--panel); border: 1px solid var(--line); border-radius: 18px; padding: 28px; box-shadow: var(--shadow); }}
.hero-top {{ display: flex; gap: 20px; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; }}
.eyebrow {{ text-transform: uppercase; letter-spacing: .08em; font-size: .74rem; font-weight: 700; color: var(--muted); }}
h1 {{ margin: 4px 0 8px; font-size: clamp(1.8rem, 3vw, 2.8rem); line-height: 1.12; }}
h2 {{ margin: 0 0 14px; font-size: 1.35rem; }}
h3 {{ margin: 2px 0 4px; font-size: 1.15rem; }}
.lead {{ margin: 0; max-width: 850px; color: var(--muted); }}
.status {{ border-radius: 999px; padding: 9px 14px; font-weight: 700; white-space: nowrap; }}
.status.ok, .finding.ok {{ color: var(--ok); background: var(--ok-bg); }}
.status.warning, .finding.warning {{ color: var(--warn); background: var(--warn-bg); }}
.status.danger, .finding.danger {{ color: var(--danger); background: var(--danger-bg); }}
.metric-grid {{ display: grid; grid-template-columns: repeat(6, minmax(120px, 1fr)); gap: 10px; margin-top: 24px; }}
.metric-grid.compact {{ grid-template-columns: repeat(9, minmax(100px, 1fr)); margin-top: 18px; }}
.metric {{ background: var(--soft); border: 1px solid var(--line); border-radius: 12px; padding: 14px; min-width: 0; }}
.metric-value {{ font-size: 1.45rem; font-weight: 750; font-variant-numeric: tabular-nums; }}
.metric-label {{ margin-top: 2px; color: var(--muted); font-size: .82rem; }}
.section {{ margin-top: 22px; background: var(--panel); border: 1px solid var(--line); border-radius: 18px; padding: 24px; box-shadow: var(--shadow); }}
.section-intro {{ color: var(--muted); margin: -6px 0 18px; }}
.archive-list {{ display: grid; gap: 14px; }}
.archive-card {{ border: 1px solid var(--line); border-radius: 14px; padding: 18px; background: #fff; }}
.archive-card-head {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; }}
.system-id, .source-count, .small {{ color: var(--muted); font-size: .84rem; }}
.source-count {{ background: var(--soft); border-radius: 999px; padding: 6px 10px; white-space: nowrap; }}
.two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
.panel {{ border: 1px solid var(--line); border-radius: 14px; padding: 18px; background: #fff; }}
.stat-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }}
.stat {{ background: var(--soft); border-radius: 10px; padding: 10px 12px; }}
.stat strong {{ display: block; font-size: 1.2rem; }}
.finding {{ border-left: 4px solid currentColor; border-radius: 10px; padding: 14px 16px; margin-top: 10px; }}
.finding-label {{ font-weight: 750; margin-bottom: 3px; }}
.finding-note {{ margin-top: 5px; font-size: .9rem; opacity: .85; }}
.assessment {{ border-left: 5px solid var(--accent); background: #edf3f7; border-radius: 10px; padding: 16px 18px; }}
.trace {{ display: grid; grid-template-columns: 170px 1fr; gap: 8px 14px; font-size: .9rem; }}
.trace div:nth-child(odd) {{ color: var(--muted); }}
.empty {{ padding: 22px; background: var(--soft); border-radius: 12px; color: var(--muted); }}
@media (max-width: 1150px) {{ .metric-grid, .metric-grid.compact {{ grid-template-columns: repeat(3, 1fr); }} }}
@media (max-width: 760px) {{ main {{ padding: 14px; }} .two-col {{ grid-template-columns: 1fr; }} .metric-grid, .metric-grid.compact, .stat-row {{ grid-template-columns: repeat(2, 1fr); }} .trace {{ grid-template-columns: 1fr; }} }}
@media print {{ body {{ background: #fff; }} main {{ max-width: none; padding: 0; }} .hero, .section {{ box-shadow: none; break-inside: avoid; }} .archive-card {{ break-inside: avoid; }} }}
</style>
</head>
<body>
<main>
<section class="hero">
  <div class="hero-top">
    <div>
      <div class="eyebrow">Data Workflow Manager · Noark 5</div>
      <h1>Vurdering av arkivuttrekk</h1>
      <p class="lead">Arkivdelene er hovedinngangen til vurderingen. Rapporten bruker eksisterende materialiserte resultater og gjør ingen ny analyse eller automatisk faglig godkjenning.</p>
    </div>
    <div class="status {overall_class}">{overall_label}</div>
  </div>
  <div class="metric-grid">{headline_metrics}</div>
</section>

<section class="section">
  <h2>Arkivdeler</h2>
  <p class="section-intro">Omfang og nøkkeltall per arkivdel. Dette er den primære arbeidsflaten for videre depotvurdering.</p>
  <div class="archive-list">{archive_part_html}</div>
</section>

<section class="section">
  <h2>Kontroll og vurderingsgrunnlag</h2>
  <div class="two-col">
    <div class="panel">
      <div class="eyebrow">Teknisk validering</div>
      <h3>Status: {esc(technical.get('status'))}</h3>
      <div class="stat-row">
        <div class="stat"><strong>{tech['ok']}</strong>OK</div>
        <div class="stat"><strong>{tech['error']}</strong>Feil</div>
        <div class="stat"><strong>{tech['legacy_disabled']}</strong>Legacy av</div>
        <div class="stat"><strong>{tech['other']}</strong>Annet</div>
      </div>
      <h3>Avstemming</h3>
      <div class="stat-row">
        <div class="stat"><strong>{rec['match']}</strong>Match</div>
        <div class="stat"><strong>{rec['mismatch']}</strong>Mismatch</div>
        <div class="stat"><strong>{rec['not_comparable']}</strong>Ikke sammenlignbar</div>
        <div class="stat"><strong>{rec['other']}</strong>Annet</div>
      </div>
    </div>
    <div class="panel">
      <div class="eyebrow">Standardverdier</div>
      <h3>{std['tests_with_checks']} tester med verdikontroller</h3>
      <div class="stat-row">
        <div class="stat"><strong>{std['status_counts']['all_observed_values_standard']}</strong>Standard</div>
        <div class="stat"><strong>{std['status_counts']['additional_observed_values']}</strong>Ekstra</div>
        <div class="stat"><strong>{std['status_counts']['no_observed_values']}</strong>Ingen verdier</div>
        <div class="stat"><strong>{std['status_counts']['other']}</strong>Annet</div>
      </div>
    </div>
  </div>
</section>

<section class="section">
  <h2>Avvik og vurderingspunkter</h2>
  {deviations_block}
</section>

<section class="section">
  <h2>Depotets vurdering</h2>
  <div class="assessment">
    <strong>Status: {esc(model['assessment']['status'])}</strong>
    <p>{esc(model['assessment']['reason'])}</p>
    <p>{esc(model['assessment']['archive_creator_responsibility'])}</p>
    <p>{esc(model['assessment']['new_extraction_guidance'])}</p>
  </div>
</section>

<section class="section">
  <h2>Evidens og sporbarhet</h2>
  <div class="trace">
    <div>Kildeprofil</div><div>{esc(model['evidence']['source_presentation_profile']) or '–'}</div>
    <div>Kildefil</div><div>{esc(model['evidence']['source_presentation_file']) or '–'}</div>
    <div>Materialiserte views</div><div>{esc(', '.join(model['evidence']['source_view_ids'])) or '–'}</div>
  </div>
  <p class="small">Maskinlesbar JSON-rapport beholder source-test/source-path for nøkkeltall og arkivdelfelt. Ekstern evidens holdes separat fra DWM-masterresultater.</p>
</section>
</main>
</body>
</html>
"""
    path.write_text(html_doc, encoding="utf-8")
