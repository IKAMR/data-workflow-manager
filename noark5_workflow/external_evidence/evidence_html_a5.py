"""Human-readable projection of reconciled evidence, separate from native DWM reports."""
from __future__ import annotations
from html import escape
from pathlib import Path
import json


def _count(value):
    return f"{value:,}".replace(",", " ") if type(value) is int else "Ukjent"


def _table(metrics):
    chunks = ['<table><thead><tr><th>Målefelt</th><th>DWM</th><th>Gjeldende rapportgrunnlag</th><th>Kilde</th><th>Status</th><th>Evidens</th></tr></thead><tbody>']
    for metric, row in sorted(metrics.items()):
        evidence = row.get('evidence') or {}
        detail = ' | '.join(str(evidence.get(key) or '') for key in ('source_file', 'test_id', 'line') if evidence.get(key) is not None)
        cells = [metric, _count(row.get('dwm_value')), _count(row.get('effective_value')),
                 row.get('effective_source') or 'Ukjent', row.get('status') or '', detail]
        chunks.append('<tr>' + ''.join('<td>' + escape(str(c)) + '</td>' for c in cells) + '</tr>')
    chunks.append('</tbody></table>')
    return ''.join(chunks)


def render_evidence_html(projection: dict) -> str:
    if projection.get('kind') != 'noark5_effective_evidence_projection':
        raise ValueError('Ugyldig evidensgrunnlag')
    parts = projection.get('archive_parts') or {}
    output = ['<!doctype html><html lang="no"><head><meta charset="utf-8"><title>Depot – evidensrapport</title>',
      '<style>body{font:15px system-ui,sans-serif;max-width:1300px;margin:28px auto;padding:0 20px;color:#24303d}h1,h2{color:#183452}table{border-collapse:collapse;width:100%;margin:12px 0 30px}th,td{border:1px solid #cdd4dc;padding:7px 9px;text-align:left;vertical-align:top}th{background:#e8eef4}tr:nth-child(even){background:#f7f9fc}p{line-height:1.5}.note{padding:12px;border-left:4px solid #59799a;background:#f2f6fa}</style></head><body>',
      '<h1>Depot – dokumentert evidensgrunnlag</h1>',
      '<p class="note">Denne rapporten er et separat visningsgrunnlag. Den opprinnelige depotrapporten og DWM-testresultatene er ikke endret. Eksterne verdier brukes bare ved eksplisitt, gyldig kildevalg.</p>',
      '<p>Originalrapport: <strong>' + escape(str(projection.get('native_report_file') or 'Ukjent')) + '</strong><br>SHA-256: ' + escape(str(projection.get('native_report_sha256') or '')) + '</p>',
      '<h2>Hele uttrekket</h2>', _table(projection.get('whole') or {})]
    def sort_key(item):
        try: return (0,int(item[0]))
        except ValueError: return (1,str(item[0]))
    for index, item in sorted(parts.items(),key=sort_key):
        identity = item.get('archive_part') or {}
        title = identity.get('title') or 'Uten tittel'
        sid = identity.get('system_id') or ''
        output.append('<h2>Arkivdel ' + escape(str(index)) + ': ' + escape(str(title)) + '</h2>')
        if sid: output.append('<p>System-ID: ' + escape(str(sid)) + '</p>')
        output.append(_table(item.get('metrics') or {}))
    output.append('</body></html>')
    return '\n'.join(output)


def write_evidence_html(projection_path: str | Path) -> Path:
    source = Path(projection_path)
    projection = json.loads(source.read_text(encoding='utf-8'))
    output = source.with_name('depot-evidence-report.html')
    temporary = output.with_suffix('.tmp')
    temporary.write_text(render_evidence_html(projection),encoding='utf-8')
    temporary.replace(output)
    return output
