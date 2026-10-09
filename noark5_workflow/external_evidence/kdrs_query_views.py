"""Read-only presentation and report data for imported KDRS Query result resources.

Uses the existing external result bank, never reruns XPath, and never changes evidence.
Selections are explicit per resource and are not implicit DWM-master replacements.
"""
from __future__ import annotations

import html
from .number_format import format_count, format_result_text
import re
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def presentation_text(value: str) -> str:
    """Interpret legacy @@ line delimiters only in views, never source evidence."""
    return format_result_text(re.sub(r'\s*@@\s*', ' ', str(value)).strip())


def _text(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _rows(resource: dict[str, Any]):
    for line_number, item in enumerate(resource.get("results") or [], 1):
        if isinstance(item, dict):
            yield {"line": line_number, "text": str(item.get("text") or ""),
                   "values": item.get("values") or [], "year_counts": item.get("year_counts") or {}}
        else:
            yield {"line": line_number, "text": str(item), "values": [], "year_counts": {}}


def build_kdrs_query_report_data(bank: dict[str, Any], *, selected_resource_ids=()) -> dict[str, Any]:
    """Carry every imported row/observation to report JSON, preserving provenance."""
    selected = set(selected_resource_ids)
    resources = []
    for group in bank.get("groups") or []:
        if group.get("source_system") != "KDRS Query":
            continue
        for resource in group.get("resources") or []:
            if not isinstance(resource, dict):
                continue
            record = {key: resource.get(key) for key in (
                "resource_id", "source_system", "source_import_id", "source_file",
                "source_sha256", "report_type", "test_id", "test_point", "test_name",
                "archive_part_index", "archive_part_title", "definition_source",
                "relationship_to_internal", "dwm_candidates", "status")}
            record["observations"] = list(_rows(resource))
            record["raw_text"] = resource.get("raw_text")
            record["selected_for_report"] = resource.get("resource_id") in selected
            record["selection_scope"] = "report_evidence_only"
            resources.append(record)
    return {"format_version": 1, "kind": "kdrs_query_report_evidence",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "note": "Selected external evidence does not overwrite internal DWM master results.",
            "resources": resources,
            "summary": {"resources": len(resources), "selected": sum(r["selected_for_report"] for r in resources),
                        "observations": sum(len(r["observations"]) for r in resources)}}


def render_kdrs_query_html(data: dict[str, Any]) -> str:
    cards = []
    types = {"standard": "Standard", "u01": "U1 – hele uttrekket", "u02": "U2 – per arkivdel"}
    for r in data.get("resources") or []:
        typ = str(r.get("report_type") or "")
        head = f'{_text(r.get("test_point") or r.get("test_id"))} · {_text(r.get("test_name") or "")}'
        tag = f' <span class="part">Arkivdel: {_text(r["archive_part_title"])}</span>' if r.get("archive_part_title") else ""
        details = ''.join(f'<tr><td>{x["line"]}</td><td class="mono">{_text(presentation_text(x["text"]))}</td></tr>' for x in r.get("observations") or [])
        if not details:
            details = '<tr><td colspan="2">Ingen resultatlinjer i denne seksjonen</td></tr>'
        source = f'{_text(r.get("source_file"))} · SHA-256: {_text(r.get("source_sha256"))}'
        selected = '<strong class="selected">Valgt som rapport-evidens</strong>' if r.get('selected_for_report') else 'Tilgjengelig evidens'
        cards.append(f'<article data-type="{_text(typ)}" data-part="{_text(r.get("archive_part_title") or "")}"><h2>{head}</h2><p>{_text(types.get(typ, typ))}{tag} · {selected}</p><p class="source">{source}</p><table><thead><tr><th>Linje</th><th>Resultat fra KDRS Query</th></tr></thead><tbody>{details}</tbody></table></article>')
    summary = data.get("summary") or {}
    document = '''<!doctype html><html lang="no"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>KDRS Query – importerte resultater</title><style>
body{font:15px system-ui,sans-serif;background:#f5f7f9;color:#1c2b3c;margin:0}header{background:#163957;color:white;padding:22px max(20px,calc((100% - 1100px)/2))}main{max-width:1100px;margin:20px auto;padding:0 18px}article{background:white;border:1px solid #d9e1e9;border-radius:9px;margin:15px 0;padding:18px;overflow-wrap:anywhere}h1{margin:0 0 8px}h2{font-size:18px;margin:0 0 10px}.source{color:#586c7a;font-size:12px}.part,.selected{color:#0b674b}table{width:100%;border-collapse:collapse}td,th{text-align:left;vertical-align:top;border-bottom:1px solid #e4ebef;padding:8px}td:first-child{width:55px}.mono{font-family:ui-monospace,Consolas,monospace;white-space:pre-wrap}nav{background:white;border:1px solid #ddd;border-radius:8px;padding:12px;display:flex;gap:12px;flex-wrap:wrap}select,input{font:inherit;padding:7px}label{display:flex;align-items:center;gap:5px}</style></head><body><header><h1>Importerte KDRS Query-resultater</h1><div>Standard · U1 · U2 — alle originalobservasjoner tilgjengelige for validering og rapport</div></header><main><p>__SUMMARY__</p><nav><label>Rapporttype <select id="type"><option value="">Alle</option><option value="standard">Standard</option><option value="u01">U1</option><option value="u02">U2</option></select></label><label>Arkivdel <input id="part" placeholder="Søk arkivdel"></label><label>Tekstsøk <input id="search" placeholder="Test og resultat"></label></nav><div id="cards">__CARDS__</div></main><script>
function filt(){const t=document.getElementById('type').value,p=document.getElementById('part').value.toLowerCase(),q=document.getElementById('search').value.toLowerCase();for(const a of document.querySelectorAll('article'))a.hidden=!!((t&&a.dataset.type!==t)||(p&&!a.dataset.part.toLowerCase().includes(p))||(q&&!a.textContent.toLowerCase().includes(q)));}for(const id of ['type','part','search'])document.getElementById(id).addEventListener('input',filt);
</script></body></html>'''
    return document.replace("__SUMMARY__", f'{format_count(int(summary.get("resources",0)))} seksjoner · {format_count(int(summary.get("observations",0)))} resultatlinjer · {format_count(int(summary.get("selected",0)))} valgt som rapport-evidens').replace("__CARDS__", "".join(cards) or "<p>Ingen importerte KDRS Query-ressurser funnet.</p>")


def write_kdrs_query_views(work_operations: str | Path, *, selected_resource_ids=()) -> tuple[Path, Path]:
    from .result_bank import build_external_result_bank
    work = Path(work_operations)
    data = build_kdrs_query_report_data(build_external_result_bank(work), selected_resource_ids=selected_resource_ids)
    from .kdrs_query_selection import load_choices
    data['selected_report_values'] = load_choices(work)
    from .kdrs_query_mapping import build_mapped_pool, write_mapped_pool
    from .kdrs_query_semantics import reconcile_semantic_observations
    mapped = build_mapped_pool(work)
    data['mapped_result_pool'] = mapped
    data['semantic_reconciliation'] = reconcile_semantic_observations(mapped)
    write_mapped_pool(work)
    from .legacy_layout_a410 import write_legacy_audit
    write_legacy_audit(work)
    output = work / 'external_evidence' / 'kdrs_query_views'
    output.mkdir(parents=True, exist_ok=True)
    json_path, html_path = output / 'report-evidence.json', output / 'imported-results.html'
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    html_path.write_text(render_kdrs_query_html(data), encoding='utf-8')
    return html_path, json_path
