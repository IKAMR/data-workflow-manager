"""Create a traceable, *unapproved* quality-assurance report for archive creator review.

Reads only the selected Work and the explicit draft control profile. Creates a
separate HTML draft; never registers acceptance, changes source evidence, or
claims test coverage beyond the documented draft matrix.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path
import hashlib
import os
import tempfile
from typing import Any
import json
from version import APP_NAME, VERSION
from noark5_workflow.analysis.canonical_qa_content_v0115_a13 import render_content_annex

from noark5_workflow.analysis.canonical_matrix_v0115_a11 import (
    evaluate_control_matrix, load_external_status,
)
from noark5_workflow.analysis.canonical_results import _validate_work

OUTPUT = 'noark5_reports/QUALITY_ASSURANCE_DRAFT.html'
MAX_ISSUES = 250
MAX_TEXT = 2500


class QualityAssuranceError(ValueError):
    pass


def _h(value: Any) -> str:
    return escape(str(value if value is not None else 'Ikke oppgitt')[:MAX_TEXT], quote=True)


def _sha(path: Path) -> str:
    result = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def _issues(external: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    """Extract ONLY source-reported Error/Warning records; no inferred findings."""
    findings: list[dict[str, Any]] = []
    total = 0
    for source in (external.get('analysis') or {}).get('sources', []):
        evidence = source.get('evidence', {})
        rel = evidence.get('work_relative_path')
        if external.get('sources', {}).get(rel) != 'analyzed':
            continue
        data = source.get('analysis', {})
        if data.get('source_format') != 'arkade_normalized_v2':
            continue
        for record in data.get('records', []):
            if not isinstance(record, dict):
                continue
            counts = record.get('reported_result_counts') or {}
            reported_status = str(record.get('reported_status') or '')
            issue_rows = record.get('reported_issues') or []
            if reported_status.casefold() not in ('error', 'warning') and not (counts.get('Error') or counts.get('Warning')):
                continue
            if issue_rows:
                for issue in issue_rows:
                    if not isinstance(issue, dict) or issue.get('result_type') not in ('Error', 'Warning'):
                        continue
                    total += 1
                    if len(findings) < MAX_ISSUES:
                        findings.append({
                            'test_id': record.get('external_test_id'),
                            'test_name': record.get('test_name'),
                            'status': issue.get('result_type'),
                            'message': issue.get('message') or 'Ingen feilmelding oppgitt',
                            'context': ' / '.join(str(x) for x in (issue.get('result_set_path') or [])),
                            'source': rel,
                        })
            else:
                total += 1
                if len(findings) < MAX_ISSUES:
                    findings.append({
                        'test_id': record.get('external_test_id'),
                        'test_name': record.get('test_name'),
                        'status': reported_status,
                        'message': 'Arkade rapporterer testutfall, uten detaljert feilmelding i analysen',
                        'context': 'Ikke oppgitt', 'source': rel,
                    })
    return findings, total


def _render(matrix: dict, external: dict, profile: Path, root: Path, generated_at: str, canonical: dict) -> tuple[str, dict]:
    findings, finding_count = _issues(external)
    control_rows = ''.join(
        '<tr><td>' + _h(item['title']) + '</td><td>' + _h(item['requirement']) +
        '</td><td>' + _h(item['assessment']) + '</td><td>' +
        _h(item['internal_observations']) + '</td><td>' +
        _h(item['external_test_records']) + '</td></tr>'
        for item in matrix['controls'])
    finding_rows = ''.join(
        '<tr><td>' + _h(item['test_id']) + '</td><td>' + _h(item['status']) +
        '</td><td>' + _h(item['message']) + '</td><td>' + _h(item['context']) +
        '</td><td>' + _h(item['source']) + '</td></tr>' for item in findings)
    if not finding_rows:
        finding_rows = '<tr><td colspan="5">Ingen detaljerte feil-/advarselsposter i koblet analyse. Dette betyr ikke at uttrekket er feilfritt.</td></tr>'
    summary = matrix['summary']
    refs = [
        ('Kontrollprofil', str(profile), _sha(profile)),
        ('Kanonisk DWM-indeks', 'noark5_evidence/canonical-results.json', _sha(root / 'noark5_evidence/canonical-results.json')),
    ]
    external_file = root / 'noark5_evidence/canonical-external-analysis.json'
    if external.get('state') == 'linked' and external_file.is_file():
        refs.append(('Ekstern analyse', 'noark5_evidence/canonical-external-analysis.json', _sha(external_file)))
    for source in (external.get('analysis') or {}).get('sources', []):
        rel = source.get('evidence', {}).get('work_relative_path')
        if external.get('sources', {}).get(rel) == 'analyzed':
            refs.append(('Kontrollkilde', rel, source['evidence'].get('sha256')))
    ref_rows = ''.join('<tr><td>' + _h(kind) + '</td><td>' + _h(rel) + '</td><td><code>' + _h(digest) + '</code></td></tr>' for kind, rel, digest in refs)
    questions = [
        'Bekreft arkivskaper, system, avleveringsomfang, avgrensning og proveniens.',
        'Bekreft at arkivperioder og de enkelte arkivdelene er riktig beskrevet.',
        'Gjennomgå Arkade-funn og dokumenter forklaring, eventuell retting og konsekvens.',
        'Bekreft at leverte dokumentfiler, antall og formatfordeling stemmer med leveransen.',
        'Avklar betingede kontroller og manglende verifikasjon i kontrollprofilen.',
    ]
    question_items = ''.join('<li>' + _h(q) + '</li>' for q in questions)
    html = '''<!doctype html><html lang="no"><head><meta charset="utf-8"><title>KS-rapport – UTKAST</title>
<style>body{font:15px system-ui,Arial,sans-serif;max-width:1100px;margin:32px auto;padding:0 18px;line-height:1.45;color:#20252b}h1,h2{color:#173e49}h1{margin-bottom:3px}.draft{border:2px solid #98692b;padding:12px;background:#fff5dc;font-weight:bold}table{border-collapse:collapse;width:100%;margin:14px 0 26px}th,td{border:1px solid #bbc5cd;padding:8px;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#e9f1f2}code{font-size:11px}li{margin-bottom:8px}.line{border-bottom:1px solid #666;min-height:32px;margin-bottom:20px}small{color:#48535b}@media print{body{margin:0;max-width:none}.draft{background:none}tr{break-inside:avoid}}</style></head><body>'''
    html += '<header style="border-bottom:3px solid #173e49;padding:12px 0 14px;margin-bottom:18px"><strong>' + _h(APP_NAME) + ' (DWM) v' + _h(VERSION) + '</strong><p><b>LABEL / leveranse-ID:</b> ' + _h((canonical.get('extraction') or {}).get('delivery_id')) + ' <small>[uttrekksbasert; ikke dokumentert dersom tom]</small></p><small>Rapportstruktur og kontrollspørsmål: malbasert. Identifikatorer, tall og funn: uttrekks-/evidensbasert og kildeangitt.</small></header>'
    html += '<h1>Kvalitetssikringsrapport – grunnlag for arkivskapers gjennomgang</h1>'
    html += '<div class="draft">UTKAST – ikke godkjent kontrollprofil. Ingen arkivskaperaksept eller depotgodkjenning er registrert.</div>'
    html += '<p><b>Jobb-ID:</b> ' + _h(matrix['work_job_uid']) + '<br><b>Opprettet (UTC):</b> ' + _h(generated_at) + '<br><b>Kontrollprofil:</b> ' + _h(matrix['profile_id']) + '</p>'
    html += '<h2>1. Formål og avgrensning</h2><p>Rapporten er et faktagrunnlag for arkivskapers kontroll av innhold, omfang, periode og proveniens. Den bygger på registrerte DWM-kjøringer og eksplisitt analysert ekstern evidens. Testutfall er ikke faglig verifisert, og kontrollprofilen er et arbeidsutkast. Opplysninger som ikke er dokumentert, skal avklares.</p>'
    reported = []
    for source in (external.get('analysis') or {}).get('sources', []):
        rel = source.get('evidence', {}).get('work_relative_path')
        if external.get('sources', {}).get(rel) != 'analyzed':
            continue
        data = source.get('analysis', {})
        if data.get('source_format') == 'arkade_normalized_v2':
            reported.append(data.get('reported_summary') or {})
    if reported:
        entry = reported[0]
        html += ('<p><b>Arkade-rapportens opplysninger (ikke bekreftet av arkivskaper):</b> '
                 'System: ' + _h(entry.get('system_name')) + '; rapportert periode: '
                 + _h(entry.get('archival_period')) + '; type: '
                 + _h(entry.get('archive_type')) + '.</p>')
    html += '<h2>2. Kontrolloversikt</h2><p>Påkrevde kontrollområder med registrert evidens: <b>' + _h(summary['required_with_registered_evidence']) + '/' + _h(summary['required_categories']) + '</b>. Arkade rapporterte tester med status error: <b>' + _h(summary['reported_arkade_errors']) + '</b>. Dette er ikke et mål på godkjent kontrolldekning.</p>'
    html += '<table><thead><tr><th>Område</th><th>Krav</th><th>Foreløpig status</th><th>DWM-observasjoner</th><th>Eksterne tester</th></tr></thead><tbody>' + control_rows + '</tbody></table>'
    html += '<h2>3. Rapporterte feil og advarsler fra Arkade 5</h2><p>Detaljerte feilmeldinger er gjengitt fra kildeanalysen, uten ny faglig konklusjon. ' + _h(finding_count) + ' detaljerte feil-/advarselsposter registrert; maksimalt ' + str(MAX_ISSUES) + ' vises.</p>'
    html += '<table><thead><tr><th>Test-ID</th><th>Kildestatus</th><th>Melding</th><th>Arkivdel / kontekst</th><th>Evidenskilde</th></tr></thead><tbody>' + finding_rows + '</tbody></table>'
    annex_html, annex_summary = render_content_annex(root, external, canonical)
    html += annex_html
    html += '<h2>7. Spørsmål til arkivskaper</h2><ol>' + question_items + '</ol>'
    html += '<p><b>Arkivskapers kommentarer/avklaringer:</b></p><div class="line"></div><div class="line"></div><div class="line"></div>'
    html += '<h2>8. Bekreftelse og videre behandling</h2><p>Følgende felt er ikke forhåndsutfylt. Utfylling i en utskrift er ikke en registrering av aksept i DWM.</p>'
    html += '<p>Kontaktperson / rolle: ________________________________________</p><p>Dato: ____________________ Referanse til svar/journalpost: ____________________</p>'
    html += '<p><b>Depotets videre vurdering:</b> Ikke utført i dette utkastet. Godkjennings-/ferdigstillingsrapport er et eget senere prosesstrinn.</p>'
    html += '<h2>9. Kilder og sporbarhet</h2><table><thead><tr><th>Type</th><th>Fil</th><th>SHA-256</th></tr></thead><tbody>' + ref_rows + '</tbody></table>'
    html += '<small>Opplysninger kan endre seg ved ny analyse. Kontroll av nye kildefiler og ny versjon av rapporten er nødvendig før formell behandling.</small></body></html>'
    return html, {**annex_summary, 'reported_arkade_errors': summary['reported_arkade_errors'],
                  'detailed_issue_records': finding_count,
                  'required_evidence': summary['required_with_registered_evidence'],
                  'required_categories': summary['required_categories'],
                  'external_analysis_state': external['state'], 'approval': None}


def build_qa_draft(work: str | Path, profile_path: str | Path, *, write: bool = True,
                   generated_at: str | None = None) -> dict[str, Any]:
    root, identity = _validate_work(Path(work))
    profile = Path(profile_path).resolve()
    if not profile.is_file() or profile.is_symlink() or profile.stat().st_size > 1_000_000:
        raise QualityAssuranceError('Mangler eller ugyldig kontrollprofil')
    matrix = evaluate_control_matrix(root, profile)
    if matrix['work_job_uid'] != identity['job_uid'] or matrix['profile_approved']:
        raise QualityAssuranceError('Uventet jobbidentitet eller kontrollprofilstatus')
    external = load_external_status(root)
    timestamp = generated_at or datetime.now(timezone.utc).isoformat(timespec='seconds')
    canonical_path = root / 'noark5_evidence/canonical-results.json'
    if canonical_path.is_symlink() or canonical_path.stat().st_size > 30_000_000:
        raise QualityAssuranceError('Ugyldig kanonisk kilde')
    canonical = json.loads(canonical_path.read_text(encoding='utf-8-sig'))
    if canonical.get('model_id') != 'noark5.canonical-results.v1' or (canonical.get('extraction') or {}).get('stable_id') != identity['job_uid']:
        raise QualityAssuranceError('Kanonisk indeks er ugyldig eller gjelder annen jobb')
    html, summary = _render(matrix, external, profile, root, timestamp, canonical)
    target = root / OUTPUT
    if write:
        directory = target.parent
        if directory.is_symlink() or target.is_symlink():
            raise QualityAssuranceError('Symbolsk lenke som maal er ikke tillatt')
        directory.mkdir(exist_ok=True)
        if directory.resolve() != (root / 'noark5_reports').resolve():
            raise QualityAssuranceError('Ugyldig utmappe')
        fd, temp = tempfile.mkstemp(prefix='.ks-draft-', suffix='.tmp', dir=directory)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                stream.write(html)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, target)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    return {'model_id': 'noark5.quality-assurance-draft.v1', 'output': OUTPUT,
            'html': html if not write else None, 'summary': summary,
            'status': 'draft_not_approved', 'archive_creator_acceptance': None,
            'depot_approval': None, 'generated_at': timestamp}
