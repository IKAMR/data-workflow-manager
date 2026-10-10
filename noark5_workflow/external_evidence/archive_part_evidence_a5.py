"""Archive-part evidence browser data from the immutable native/companion pair."""
from __future__ import annotations

METRIC_LABELS = {
    'folder_count': 'Mapper', 'case_folder_count': 'Saker',
    'registration_count': 'Registreringer', 'journalpost_count': 'Journalposter',
    'document_description_count': 'Dokumentbeskrivelser',
    'document_object_count': 'Dokumentobjekter',
}


def available_archive_parts(annex: dict) -> list[tuple[int, str]]:
    """Only destination archive parts known from the native report are selectable."""
    parts = {}
    for record in annex.get('records') or []:
        i = record.get('archive_part_index')
        identity = record.get('dwm_archive_part')
        if type(i) is int and i > 0 and isinstance(identity, dict):
            parts[i] = str(identity.get('title') or identity.get('system_id') or f'Arkivdel {i}')
    return sorted(parts.items())


def part_evidence_lines(annex: dict, index: int) -> list[str]:
    if type(index) is not int or index < 1:
        raise ValueError('Ugyldig arkivdelindeks')
    def count(value):
        return f'{value:,}'.replace(',', ' ') if type(value) is int else 'Ukjent'
    rows = [r for r in (annex.get('records') or []) if r.get('archive_part_index') == index]
    lines = []
    for row in sorted(rows, key=lambda r: r.get('metric_id') or ''):
        metric = row.get('metric_id') or '?'
        name = METRIC_LABELS.get(metric, metric)
        candidates = row.get('external_candidates') or []
        external_values = row.get('external_unique_values')
        if external_values is None:
            external_values = sorted({c['value'] for c in candidates if type(c.get('value')) is int})
        available = ', '.join(count(value) for value in external_values) if external_values else 'Ingen'
        selected = row.get('status') == 'external_evidence_selected'
        lines.append(f'{name}: DWM {count(row.get("dwm_value"))} | KDRS tilgjengelig {available} | Valgt {count(row.get("effective_value")) if selected else "Ingen"}')
        compare = row.get('dwm_comparison') or 'unknown'
        compare_label = {'unknown': 'Kan ikke sammenlignes (DWM-verdi mangler eller KDRS mangler)',
                         'agreement': 'Samsvar', 'conflict': 'Avvik',
                         'mixed': 'Blandede eksterne verdier'}.get(compare, compare)
        external = {'agreement': 'Enig', 'conflict': 'Uenige', 'missing': 'Ingen'}.get(
            row.get('external_comparison'), row.get('external_comparison') or 'Ukjent')
        lines.append(f'  Sammenligning: {compare_label} | Eksterne kilder: {external}')
        evidence = row.get('evidence')
        if isinstance(evidence, dict):
            lines.append(f'  Valgt kilde: {evidence.get("source") or "?"} | Fil: {evidence.get("source_file") or "?"}')
            lines.append(f'  SHA-256: {evidence.get("source_sha256") or "?"} | Linje: {evidence.get("source_line_number") or "?"}')
            lines.append(f'  Begrunnelse: {evidence.get("reason") or "?"} | Merknad: {evidence.get("note") or "-"}')
        elif candidates:
            types = sorted({str(c.get('report_type') or 'KDRS Query') for c in candidates})
            lines.append(f'  Tilgjengelige kilder: {", ".join(types)}. Ingen er valgt som rapportgrunnlag.')
        if row.get('scope_review'):
            lines.append(f'  KONTROLLER OMFANG: {row["scope_review"]}')
        lines.append('')
    return lines or ['Ingen eksakt mappede observasjoner eller DWM-måltall for denne arkivdelen.']


def archive_part_summary(projection: dict, index: int) -> list[str]:
    """Evidence facts for an archive part, never altering its native counts."""
    item = (projection.get('archive_parts') or {}).get(str(index)) or {}
    metrics = item.get('metrics') or {}
    labels = {'folder_count':'Mapper', 'registration_count':'Registreringer',
              'journalpost_count':'Journalposter', 'document_description_count':'Dokumentbeskrivelser',
              'document_object_count':'Dokumentobjekter'}
    lines = []
    for metric, label in labels.items():
        row = metrics.get(metric) or {}
        if not row:
            continue
        if row.get('status') != 'external_evidence_selected' and row.get('dwm_comparison') != 'conflict':
            continue
        original = row.get('dwm_value')
        effective = row.get('effective_value')
        show = lambda v: f'{v:,}'.replace(',', ' ') if type(v) is int else 'Ukjent'
        source = row.get('effective_source') or 'Ukjent'
        lines.append(f'{label}: DWM {show(original)} | Rapportgrunnlag {show(effective)} ({source})')
        evidence = row.get('evidence') or {}
        if row.get('status') == 'external_evidence_selected':
            parts = [str(evidence.get(k)) for k in ('source_file','test_id','line') if evidence.get(k) is not None]
            if parts: lines.append('  Evidens: ' + ' | '.join(parts))
    return lines


def evidence_table_rows(annex: dict, index: int | None) -> list[dict]:
    """Human-facing facts from the same reconciled records; no implicit approval."""
    if type(index) is not int or index < 1:
        return []
    labels = {**METRIC_LABELS, 'correspondence_party_count': 'Korrespondanseparter',
              'case_folder_count': 'Saksmapper'}
    def display(value):
        return f'{value:,}'.replace(',', ' ') if type(value) is int else 'Ukjent'
    result = []
    for row in sorted((r for r in annex.get('records', []) if r.get('archive_part_index') == index),
                      key=lambda r: (labels.get(r.get('metric_id'), r.get('metric_id') or ''))):
        candidates = row.get('external_candidates') or []
        values = row.get('external_unique_values')
        if values is None:
            values = sorted({c['value'] for c in candidates if type(c.get('value')) is int})
        selected = row.get('status') == 'external_evidence_selected'
        dwm = row.get('dwm_value')
        available = ', '.join(display(v) for v in values) if values else 'Ingen'
        if dwm is None:
            verdict = 'DWM mangler verdi'
        elif not values:
            verdict = 'Ingen ekstern verdi'
        elif len(values) > 1:
            verdict = 'Kildekonflikt'
        elif dwm == values[0]:
            verdict = 'Samsvar'
        else:
            verdict = 'Avvik'
        evidence = row.get('evidence') if selected else None
        detail = ''
        if isinstance(evidence, dict):
            detail = ('Godkjent KDRS-kilde: ' + str(evidence.get('source_file') or '?')
                      + ' | Linje: ' + str(evidence.get('source_line_number') or '?')
                      + ' | Begrunnelse: ' + str(evidence.get('reason') or '?')
                      + ' | Merknad: ' + str(evidence.get('note') or '-'))
        result.append({'cells': (labels.get(row.get('metric_id'), row.get('metric_id') or '?'),
                                 display(dwm), available,
                                 display(row.get('effective_value')) if selected else 'Ikke valgt', verdict),
                       'detail': detail})
    return result
