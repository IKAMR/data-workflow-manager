from __future__ import annotations
import html
from pathlib import Path
from typing import Any
from noark5_workflow.reporting.report_output import html_document, safe_component, write_html_report, write_json_report

_LEVEL={"error":"FEIL","warning":"ADVARSEL","review":"VURDER","ok":"OK"}
_COVERAGE={"equivalent":"Direkte sammenlignbar","candidate":"Kandidat – må kvalitetssikres","known_non_equivalent":"Ikke direkte sammenlignbar","unmapped":"Ikke kartlagt"}

def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value))

def arkade5_analysis_basename(analysis: dict[str, Any], import_id: str) -> str:
    summary=analysis.get("source_summary") or {}
    date=str(summary.get("date_of_testing") or "udatert").replace("-","")
    return safe_component(f"ARKADE5_ANALYSE_{date}_{import_id}")

def render_arkade5_analysis_html(analysis: dict[str, Any], *, import_id: str) -> str:
    summary=analysis.get("summary") or {}
    source=analysis.get("source") or {}
    source_summary=analysis.get("source_summary") or {}
    cards=[]
    for item in analysis.get("items") or []:
        level=str(item.get("attention_level") or "review")
        coverage=_COVERAGE.get(item.get("coverage_classification"),str(item.get("coverage_classification") or "–"))
        rec=item.get("reconciliation") or {}
        candidates=", ".join(f"{row.get('dwm_test_id')} ({row.get('legacy_job_id')})" for row in item.get("dwm_candidates") or []) or "–"
        findings=[]
        for finding in item.get("findings") or []:
            location=""
            if finding.get("file"):
                location=f" [{finding.get('file')}"
                if finding.get("line_numbers"):
                    location+=f": {finding.get('line_numbers')}"
                location+="]"
            findings.append("<li>"+_esc(finding.get("type") or "Resultat")+": "+_esc(finding.get("message") or "–")+_esc(location)+"</li>")
        findings_html="<h3>Arkade-funn</h3><ul>"+"".join(findings)+"</ul>" if findings else ""
        cards.append(f"""
<section class="card {html.escape(level)}">
<h2>{_esc(_LEVEL.get(level,level.upper()))} – {_esc(item.get('test_id'))} – {_esc(item.get('test_name'))}</h2>
<p>{_esc(item.get('explanation'))}</p>
<table>
<tr><th>Arkade-status</th><td>{_esc(item.get('arkade_status'))}</td></tr>
<tr><th>Feil</th><td>{_esc(item.get('number_of_errors'))}</td></tr>
<tr><th>DWM-dekning</th><td>{_esc(coverage)}</td></tr>
<tr><th>Reconciliation</th><td>{_esc(rec.get('status') or 'ikke tilgjengelig')}</td></tr>
<tr><th>DWM-kandidater</th><td>{_esc(candidates)}</td></tr>
</table>
{findings_html}
</section>
""")
    body=f"""
<h1>Arkade 5 – rapportanalyse</h1>
<div class="meta">
Testdato: {_esc(source_summary.get('date_of_testing') or '–')}<br>
Import-ID: {_esc(import_id)}<br>
Kilde: {_esc(source.get('file') or source.get('original_name') or '–')}<br>
SHA-256: {_esc(source.get('sha256') or '–')}<br>
Arkade-versjon: {_esc(analysis.get('source_version') or '–')}
</div>
<div class="summary">
<strong>Tester:</strong> {_esc(summary.get('tests',0))} |
<strong>FEIL:</strong> {_esc(summary.get('error',0))} |
<strong>ADVARSEL:</strong> {_esc(summary.get('warning',0))} |
<strong>VURDER:</strong> {_esc(summary.get('review',0))} |
<strong>OK:</strong> {_esc(summary.get('ok',0))} |
<strong>Trenger oppfølging:</strong> {_esc(summary.get('needs_attention',0))}
</div>
<p>{_esc(analysis.get('principle') or '')}</p>
{''.join(cards)}
"""
    return html_document(title="Arkade 5 – rapportanalyse",body=body)

def write_arkade5_analysis_reports(analysis: dict[str, Any], *, import_id: str, output_dir: str | Path, html_output: bool=True, json_output: bool=True) -> list[Path]:
    basename=arkade5_analysis_basename(analysis,import_id)
    written=[]
    if html_output:
        written.append(write_html_report(render_arkade5_analysis_html(analysis,import_id=import_id),output_dir=output_dir,basename=basename))
    if json_output:
        payload=dict(analysis)
        payload["source_import_id"]=import_id
        written.append(write_json_report(payload,output_dir=output_dir,basename=basename))
    return written
