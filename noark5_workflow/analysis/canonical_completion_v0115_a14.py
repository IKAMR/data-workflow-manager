"""Conservative finishing/decision record draft; does not approve or journalize.

All evidence remains in Work. This HTML is a non-authoritative decision worksheet,
not a depot decision. No recorded acceptance is inferred from file presence.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path
import hashlib
import os
import tempfile
from typing import Any

from version import APP_NAME, VERSION
from noark5_workflow.analysis.canonical_results import _validate_work
from noark5_workflow.analysis.canonical_matrix_v0115_a11 import evaluate_control_matrix, load_external_status
from noark5_workflow.analysis.canonical_qa_report_v0115_a12 import _issues, OUTPUT as QA_OUT

OUTPUT = 'noark5_reports/COMPLETION_DECISION_DRAFT.html'

class CompletionDraftError(ValueError):
    pass

def _h(value: Any) -> str:
    return escape(str(value if value is not None else 'Ikke dokumentert')[:4000], quote=True)

def _sha(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()

def build_completion_draft(work: str | Path, profile_path: str | Path, *,
                           write: bool = True, generated_at: str | None = None) -> dict[str, Any]:
    root, identity = _validate_work(Path(work))
    profile = Path(profile_path).resolve()
    if profile.is_symlink() or not profile.is_file() or profile.stat().st_size > 1_000_000:
        raise CompletionDraftError('Ugyldig kontrollprofil')
    matrix = evaluate_control_matrix(root, profile)
    if matrix.get('work_job_uid') != identity['job_uid'] or matrix.get('profile_approved'):
        raise CompletionDraftError('Uventet jobbidentitet eller kontrollprofil er ikke et utkast')
    external = load_external_status(root)
    issues, count = _issues(external)
    summary = matrix['summary']
    qa = root / QA_OUT
    if qa.is_symlink():
        raise CompletionDraftError('KS-rapport kan ikke være symbolsk lenke')
    qa_exists = qa.is_file()
    qa_digest = _sha(qa) if qa_exists else None
    # A referenced KS draft is evidence of a generated document, never an acceptance.
    blockers = [
        'Kontrollprofilen er et utkast, ikke faglig godkjent.',
        'Dokumentert arkivskaperaksept er ikke registrert i denne modellen.',
        'Depotets beslutning, ansvarlig og dato er ikke registrert.',
        'Journalføringsreferanse er ikke registrert.',
        'Påkrevde og betingede kontrollutfall er ikke faglig verifisert.',
    ]
    if not qa_exists:
        blockers.append('KS-rapportutkast mangler i Work.')
    if external.get('state') != 'linked':
        blockers.append('Ekstern analyse er ikke koblet med verifiserte kildeavtrykk.')
    if count:
        blockers.append(f'{count} feil-/advarselsposter fra Arkade krever dokumentert behandling.')
    controls=''.join('<tr><td>'+_h(c.get('title'))+'</td><td>'+_h(c.get('requirement'))+
                     '</td><td>'+_h(c.get('assessment'))+'</td></tr>'
                     for c in matrix.get('controls',[]))
    issue_rows=''.join('<tr><td>'+_h(x.get('test_id'))+'</td><td>'+_h(x.get('status'))+
                       '</td><td>'+_h(x.get('message'))+'</td><td>'+_h(x.get('context'))+'</td></tr>'
                       for x in issues)
    if not issue_rows:
        issue_rows='<tr><td colspan="4">Ingen detaljerte avvik i valgt evidens. Dette er ikke en friskmelding.</td></tr>'
    blockers_html=''.join('<li>'+_h(b)+'</li>' for b in blockers)
    when=generated_at or datetime.now(timezone.utc).isoformat(timespec='seconds')
    document="""<!doctype html><html lang="no"><head><meta charset="utf-8"><title>Ferdigstilling – beslutningsgrunnlag (utkast)</title>
<style>body{font:15px system-ui,Arial,sans-serif;max-width:1100px;margin:30px auto;padding:0 18px;line-height:1.5;color:#20252b}h1,h2{color:#173e49}header{border-bottom:3px solid #173e49;padding-bottom:12px}.draft{border:2px solid #98692b;padding:10px;font-weight:700}table{border-collapse:collapse;width:100%;margin:12px 0 24px}th,td{border:1px solid #bbc5cd;padding:8px;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#e9f1f2}code{overflow-wrap:anywhere}.line{border-bottom:1px solid #666;min-height:24px}@media print{body{margin:0;max-width:none}tr{break-inside:avoid}}</style></head><body>"""
    document += '<header><strong>'+_h(APP_NAME)+' (DWM) v'+_h(VERSION)+'</strong><p>Dokumenttype: beslutnings- og ferdigstillingsgrunnlag [malbasert]</p><p>Jobb-ID: '+_h(identity['job_uid'])+' [Work-basert]</p></header>'
    document += '<h1>Godkjennings- og ferdigstillingsrapport – UTKAST</h1>'
    document += '<p class="draft">IKKE GODKJENT. Ingen arkivskaperaksept, depotbeslutning eller journalføring er registrert.</p>'
    document += '<p><b>Opprettet (UTC):</b> '+_h(when)+'<br><b>Kontrollprofil:</b> '+_h(matrix.get('profile_id'))+'</p>'
    document += '<h2>1. Beslutningsstatus</h2><p><b>Tilstand:</b> Ikke klarert for ferdigstilling. Dette er et dokumentasjonsutkast, ikke en automatisk beslutning.</p><ul>'+blockers_html+'</ul>'
    document += '<h2>2. Status for kontrollgrunnlaget</h2><p>Påkrevde kontrollområder med registrert evidens: '+_h(summary.get('required_with_registered_evidence'))+'/'+_h(summary.get('required_categories'))+'. Registrert evidens er ikke lik godkjent kontroll.</p>'
    document += '<table><thead><tr><th>Kontrollområde</th><th>Krav</th><th>Registrert tilstand</th></tr></thead><tbody>'+controls+'</tbody></table>'
    document += '<h2>3. Uavklarte Arkade-funn</h2><p>Rapporterte feil-/advarselsposter: '+_h(count)+'. Bare kildefunn; ingen faglig konklusjon eller avvikslukking er registrert.</p>'
    document += '<table><thead><tr><th>Test-ID</th><th>Kildestatus</th><th>Melding</th><th>Kontekst</th></tr></thead><tbody>'+issue_rows+'</tbody></table>'
    document += '<h2>4. Vurderinger og beslutninger som må dokumenteres</h2><table><thead><tr><th>Beslutningspunkt</th><th>Status</th><th>Referanse / ansvar / dato</th></tr></thead><tbody>'
    for label in ('Arkivskapers bekreftelse av innhold, periode og proveniens','Avviksbehandling og eventuell ny kontroll','Vurdering av betingede kontrollkrav','Depotets faglige beslutning','Journalføring og saksreferanse','Klargjøring for bevaringspakke'):
        document += '<tr><td>'+_h(label)+'</td><td>IKKE REGISTRERT</td><td>________________________</td></tr>'
    document += '</tbody></table>'
    document += '<h2>5. KS-rapport og evidens</h2>'
    if qa_exists:
        document += '<p>KS-rapportutkast i Work: <code>'+_h(QA_OUT)+'</code><br>SHA-256: <code>'+_h(qa_digest)+'</code>. Innhold og eventuell senere aksept må vurderes selvstendig.</p>'
    else:
        document += '<p>KS-rapportutkast mangler. Generer KS-rapport før videre behandling.</p>'
    document += '<p><b>Ekstern analyse:</b> '+_h(external.get('state'))+'. Fornyede kilder krever kontroll av referanser og kildeavtrykk.</p>'
    document += '<h2>6. Saksbehandling og journalføring</h2><p>Journalpost-ID: <span class="line">____________________</span> Saksnummer: ____________________</p><p>Beslutter / rolle: ____________________ Dato: ____________________</p><p>Ingen felt fylles automatisk som vedtak. Utfylling i papir eller HTML registrerer ikke beslutningen i DWM.</p>'
    document += '<p><small>Rapporten er basert på malbaserte beslutningspunkter og Work-/evidensbaserte kontrollfunn. Source og original evidens endres ikke.</small></p></body></html>'
    target=root / OUTPUT
    if write:
        directory=target.parent
        if directory.is_symlink() or target.is_symlink():
            raise CompletionDraftError('Symbolsk lenke i utmappe')
        directory.mkdir(exist_ok=True)
        if directory.resolve() != (root/'noark5_reports').resolve():
            raise CompletionDraftError('Ugyldig målmappe')
        fd, temp = tempfile.mkstemp(prefix='.completion-draft-', suffix='.tmp',dir=directory)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as stream:
                stream.write(document)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp,target)
        finally:
            if os.path.exists(temp):os.unlink(temp)
    return {'model_id':'noark5.completion-decision-draft.v1', 'output':OUTPUT,
            'html':None if write else document,'generated_at':when,
            'summary':{'issues':count,'open_conditions':len(blockers),'has_qa_draft':qa_exists,
                       'required_evidence':summary.get('required_with_registered_evidence'),
                       'required_categories':summary.get('required_categories'),
                       'approval_registered':False,'journal_reference_registered':False},
            'status':'draft_not_approved'}
