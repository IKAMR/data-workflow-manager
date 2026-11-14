"""Source-bounded, evidence-labelled content annex for the QA draft.

Only files explicitly selected in the current external analysis and validated
by its SHA-256 are read. No semantic conclusions or additive counts are inferred.
"""
from __future__ import annotations

from collections import OrderedDict
from html import escape
import hashlib
import json
from pathlib import Path
import re
from typing import Any

MAX_BYTES = 30_000_000
MAX_PARTS = 500
MAX_FORMATS = 500
MAX_CELL = 600
_PART = re.compile(r'^Arkivdel \(systemID, tittel\):\s*([0-9a-fA-F-]{36}),\s*(.+)$')
_COUNT = re.compile(r'^(?:Antall(?:\s+mapper)?|Totalt):\s*(\d+)\s*$')


def h(value: Any) -> str:
    return escape(str(value if value is not None and value != '' else 'Ikke dokumentert')[:MAX_CELL], quote=True)


def _load_source(root: Path, source: dict, link_state: dict) -> dict | None:
    evidence = source.get('evidence') or {}
    rel = evidence.get('work_relative_path')
    if not isinstance(rel, str) or link_state.get(rel) != 'analyzed':
        return None
    base = root.resolve()
    target = root / rel
    if target.is_symlink():
        return None
    target = target.resolve()
    if not target.is_relative_to(base) or not target.is_file() or target.stat().st_size > MAX_BYTES:
        return None
    if hashlib.sha256(target.read_bytes()).hexdigest() != evidence.get('sha256'):
        return None
    try:
        result = json.loads(target.read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return result if isinstance(result, dict) else None


def _part_from_path(path: list) -> tuple[str, str] | None:
    if not isinstance(path, list):
        return None
    for item in path:
        if isinstance(item, str):
            match = _PART.match(item)
            if match:
                return match.group(1).lower(), match.group(2)
    return None


def _archive_parts(report: dict) -> list[dict]:
    """List only archive parts actually identified by the Arkade source."""
    parts: OrderedDict[str, dict] = OrderedDict()
    for test in report.get('tests', []):
        if not isinstance(test, dict):
            continue
        tid = test.get('test_id')
        if tid not in ('N5.06', 'N5.10', 'N5.15', 'N5.22'):
            continue
        for result in test.get('results', []):
            if not isinstance(result, dict):
                continue
            match = _part_from_path(result.get('result_set_path'))
            message = result.get('message')
            if tid == 'N5.06' and isinstance(message, str):
                # Arkade includes arkivdel identification in the message rather than result_set_path.
                description = re.match(r'^Status for Arkivdel \(systemID, tittel\):\s*([0-9a-fA-F-]{36}),\s*(.+?):\s*(.+)$', message)
                if description:
                    match = (description.group(1).lower(), description.group(2))
                    state = description.group(3)
                else:
                    state = None
            else:
                state = None
            if not match:
                continue
            identifier, title = match
            if identifier not in parts and len(parts) < MAX_PARTS:
                parts[identifier] = {'id': identifier, 'title': title, 'status': None,
                                     'folders': None, 'issues': []}
            if identifier not in parts:
                continue
            part = parts[identifier]
            if tid == 'N5.06' and state:
                part['status'] = state
            if tid == 'N5.10' and len(result.get('result_set_path') or []) == 1 and isinstance(message, str):
                count = _COUNT.fullmatch(message)
                if count:
                    part['folders'] = int(count.group(1))
            if tid in ('N5.15', 'N5.22') and result.get('result_type') in ('Error', 'Warning'):
                part['issues'].append({'test_id': tid, 'message': message})
    return list(parts.values())


def _source_documents(root: Path, external: dict) -> tuple[list[tuple[dict, dict]], list[tuple[dict, dict]]]:
    arkade, pronom = [], []
    for source in (external.get('analysis') or {}).get('sources', []):
        analysis = source.get('analysis') or {}
        fmt = analysis.get('source_format')
        if fmt not in ('arkade_normalized_v2', 'arkade_pronom_statistics_v1'):
            continue
        source_doc = _load_source(root, source, external.get('sources') or {})
        if source_doc is None:
            continue
        if fmt == 'arkade_normalized_v2' and source_doc.get('evidence_type') == 'external_validation_report' and source_doc.get('format_version') == 2:
            arkade.append((source, source_doc))
        elif fmt == 'arkade_pronom_statistics_v1' and source_doc.get('evidence_type') == 'arkade5_pronom_format_statistics':
            pronom.append((source, source_doc))
    return arkade, pronom


def render_content_annex(root: Path, external: dict, canonical: dict) -> tuple[str, dict]:
    """Render provenance-led content sections. Never sum overlapping test results."""
    arkade, pronom = _source_documents(root, external)
    extraction = canonical.get('extraction') if isinstance(canonical.get('extraction'), dict) else {}
    observations = canonical.get('observations', [])
    html = '<h2>4. Uttrekkets identitet og proveniens</h2>'
    html += '<p><b>Datakilde:</b> Kanonisk DWM-indeks (arbeidsjobb, ikke verifisert kildeidentitet).</p>'
    metadata = [('DWM jobb-ID', extraction.get('stable_id')), ('Leveranse-ID / LABEL', extraction.get('delivery_id')),
                ('Noark-versjon', extraction.get('noark_version')), ('System (bekreftet DWM)', extraction.get('system')),
                ('Arkivskaper (bekreftet DWM)', extraction.get('archive_creators')), ('Arkiveier', extraction.get('archive_owner'))]
    html += '<table><thead><tr><th>Opplysning</th><th>Registrert verdi</th></tr></thead><tbody>'
    html += ''.join('<tr><td>'+h(name)+'</td><td>'+h(value)+'</td></tr>' for name,value in metadata)
    html += '</tbody></table>'
    if arkade:
        report = arkade[0][1]
        s = report.get('summary') or {}
        html += '<p><b>Oppgitt av Arkade 5 (ikke bekreftet av arkivskaper):</b> Arkivskaper: ' + h(s.get('archive_creators')) + '; system: ' + h(s.get('system_name')) + '; systemtype: ' + h(s.get('system_type')) + '; periode: ' + h(s.get('archival_period')) + '; testdato: ' + h(s.get('date_of_testing')) + '.</p>'
        html += '<p>Arkades samlede periode er <b>ikke</b> dokumentasjon på perioder for hver arkivdel. Disse må avklares særskilt.</p>'
    html += '<h2>5. Arkivdeler og rapportert innhold</h2>'
    html += '<p>Arkivdeler vises separat med Arkades opprinnelige identifikatorer. Tall fra ulike testverktøy summeres ikke med hverandre.</p>'
    parts = _archive_parts(arkade[0][1]) if arkade else []
    if parts:
        html += '<table><thead><tr><th>Arkivdel</th><th>System-ID</th><th>Status (Arkade)</th><th>Mapper (N5.10)</th><th>Rapporterte funn</th></tr></thead><tbody>'
        for part in parts:
            issues = '; '.join(str(v['test_id'])+': '+str(v['message']) for v in part['issues'])
            html += '<tr><td>'+h(part['title'])+'</td><td><code>'+h(part['id'])+'</code></td><td>'+h(part['status'])+'</td><td>'+h(part['folders'])+'</td><td>'+h(issues if issues else 'Ingen avvik i utvalgte kildekontroller')+'</td></tr>'
        html += '</tbody></table>'
    else:
        html += '<p>Ingen arkivdeler med verifiserbar kildetilknytning ble funnet i valgt analyse. Dette er ikke et bevis på at arkivdeler mangler.</p>'
    known = [o for o in observations if isinstance(o, dict) and o.get('test_id') == 'kdrs.c02']
    if known:
        values = known[0].get('numeric_values') or {}
        if isinstance(values, dict):
            html += '<p><b>DWM XPath kdrs.c02 – rapporterte totalverdier (ikke faglig verifisert):</b> '
            html += '; '.join(h(k)+': '+h(v) for k,v in values.items() if isinstance(v, int) and type(v) is int) + '.</p>'
    html += '<h2>6. Filformater og bevaringsrelevante spørsmål</h2>'
    if pronom:
        rows = (pronom[0][1].get('csv') or {}).get('rows') or []
        if len(rows) <= MAX_FORMATS:
            html += '<p><b>Kilde:</b> Arkade 5 PRONOM-formatstatistikk. «RAF-220301» gjengis som kildestatus, ikke som depotets formatgodkjenning.</p>'
            html += '<table><thead><tr><th>PRONOM-ID</th><th>Format</th><th>Versjon</th><th>RAF-220301 (kilde)</th><th>Antall</th></tr></thead><tbody>'
            count_total = 0
            for row in rows:
                if not isinstance(row, dict):
                    continue
                try:
                    count = int(row.get('Antall', ''))
                    if count < 0:
                        raise ValueError()
                except (ValueError, TypeError):
                    count = None
                if count is not None:
                    count_total += count
                html += '<tr>' + ''.join('<td>'+h(row.get(key))+'</td>' for key in ('Format-ID','Filtype','Formatversjon','RAF-220301','Antall')) + '</tr>'
            html += '</tbody></table><p><b>Sum i valgt formatstatistikk:</b> '+h(count_total)+' filer. Må avstemmes mot dokument-/filinventar; er ikke en integritetskontroll.</p>'
        else:
            html += '<p>Formatstatistikken overskrider visningsgrensen; se original evidens.</p>'
    else:
        html += '<p>Ingen gyldig, kildekontrollert PRONOM-formatstatistikk er koblet til denne rapporten.</p>'
    html += '<p><b>Avklar:</b> hvilke arkivdeler skal bevares, periodisering, aktive mapper/journalposter, filformat som krever særskilt vurdering, og avvik mellom arkivskapers leveranseliste og observerte tall.</p>'
    return html, {'archive_parts_listed': len(parts), 'pronom_statistics_present': bool(pronom),
                  'identity_confirmed': False, 'source_derived_content_only': True}
