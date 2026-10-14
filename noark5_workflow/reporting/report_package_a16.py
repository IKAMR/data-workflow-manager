"""Export a linked, offline HTML report package using existing persisted DWM evidence."""
from __future__ import annotations
from collections import Counter
from datetime import datetime
from html import escape, unescape
from pathlib import Path
import re
import json
import copy
from .job_summary_a16 import (
    ReportOptions, _latest_report, _extraction_label, _review_status,
    _archive_names, _external_values, _period_text, _observed_label, _part_period_annex,
    render_selected_jobs_report,
)
from .period_assessment_a16 import review_candidate, reviewed_years, load_assessment
from .period_report_a18 import collect_period_sources, render_period_source_overview, render_period_source_annex
from .yearly_volume_a16 import archive_part_volumes, combined_volumes, sparse_boundary_years, registration_years
from .external_report_a18 import (collect_job_evidence, report_count_overview,
                                   render_count_overview, external_status_rows, render_external_status)
from .archive_u2_a18 import collect_u2_archive_parts, render_u2_archive_parts
from .archive_part_annex_a18 import render_archive_part_annex
from .evidence_comparison_a18 import build_source_comparison, render_source_comparison_overview, render_source_comparison_whole_counts, render_source_comparison_annex

STYLE = '''body{font:11pt Segoe UI,Arial,sans-serif;color:#223;max-width:1100px;margin:32px auto;padding:0 22px;line-height:1.4}h1{font-size:17pt}h2{font-size:13pt;margin-top:25px}h3{font-size:11pt}table{border-collapse:collapse;width:100%;font-size:10pt;margin:12px 0}th,td{border:1px solid #cbd1dc;padding:6px;text-align:left;vertical-align:top}th{background:#edf1f6}a{color:#17477a}nav{position:sticky;top:0;z-index:100;background:#fff;padding:12px 8px;border-bottom:1px solid #ccd2db;box-shadow:0 2px 4px #00000012}nav a{margin-right:16px}p.note{color:#526071}.job-overview th:first-child,.job-overview td:first-child{width:82px;min-width:82px;white-space:nowrap;word-break:keep-all}.year-chart{margin:12px 0 22px;max-width:950px}.year-chart svg{display:block;width:100%;height:auto}.year-summary{font-size:10pt;color:#435064}.appendix{break-inside:avoid}@media print{nav{display:none}body{margin:0;padding:0}}'''
NAMES = {
    'index.html': 'Hovedrapport',
    'vedlegg-a-uttrekk.html': 'Vedlegg A – Uttrekk',
    'vedlegg-b-arkivdeler.html': 'Vedlegg B – Arkivdeler',
    'vedlegg-c-teknisk-evidens.html': 'Vedlegg C – Teknisk validering og evidens',
    'vedlegg-d-periodevurdering.html': 'Vedlegg D – Periodeavstemming og vurderinger',
}

def _page(title, content, available, filenames=None):
    filenames = filenames or {name:name for name in available}
    nav = ' '.join(f'<a href="{escape(filenames[name], quote=True)}">{escape(NAMES[name])}</a>' for name in available)
    return ('<!doctype html><html lang="no"><head><meta charset="utf-8"><title>' + escape(title) +
        '</title><style>'+STYLE+'</style></head><body><nav>'+nav+'</nav><h1>'+escape(title)+'</h1>'+content+'</body></html>')

def _extract_sections(html):
    # The established report renderer emits top-level sections only, with no nested section tags.
    results = []
    for match in re.finditer(r'<section class="[^"]*">.*?</section>', html, re.S):
        section = match.group()
        title = re.search(r'<h2>(.*?)</h2>', section, re.S)
        if title:
            results.append((re.sub('<[^>]+>', '', title.group(1)), section))
    return results

def _table(headings, rows):
    h = '<thead><tr>'+''.join('<th>'+escape(str(x))+'</th>' for x in headings)+'</tr></thead>'
    b = '<tbody>'+''.join('<tr>'+''.join('<td>'+escape(unescape(str(v))).replace('\n','<br>')+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody>'
    return '<table>'+h+b+'</table>'

_METRIC_LABELS = (('folder','Saker'),('journal','JP'),('document_description','Dok.beskr.'),('document_object','Dok.obj.'))
_COLORS = ('#2965a1','#d18835','#438c75','#9572b3','#b24670')

def _chart_metrics(registrations):
    return _METRIC_LABELS + ((('registration','Registr.'),) if registrations is not None else ())

def _yearly_chart(volumes, *, compact=False, registrations=None):
    """Offline SVG plus machine-readable data for ReportLab's vector chart."""
    if not volumes:
        return '<p class="note">Ingen lagret årsfordeling tilgjengelig.</p>'
    years=sorted(volumes)
    metrics=_chart_metrics(registrations)
    if registrations is not None:
        volumes={year:{**volumes[year], 'registration':registrations.get(year,0)} for year in years}
    maximum=max((volumes[y].get(k,0) for y in years for k,_ in metrics),default=0) or 1
    bar_group=34 if compact else 48
    left=54; top=33; bottom=43
    w=max(480,left+len(years)*bar_group+14); height=top+(95 if compact else 160)+bottom
    baseline=height-bottom
    bar_w=(bar_group-8)/len(metrics)
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {height}" role="img" aria-label="Årlig produksjonsvolum; nøyaktige tall i tabell">',
         f'<line x1="{left}" y1="{baseline}" x2="{w-4}" y2="{baseline}" stroke="#708090"/>',
         f'<text x="3" y="{top}" fill="#586579" font-size="10">{maximum:,}</text>']
    sparse = {year for year, _ in sparse_boundary_years(volumes)}
    for index, year in enumerate(years):
        x=left+index*bar_group
        if index and year-years[index-1]>1:
            out.append(f'<text x="{x-4:.1f}" y="{baseline+30}" text-anchor="middle" font-size="10" fill="#9a5420">//</text>')
        for m,(key,_) in enumerate(metrics):
            v=volumes[year].get(key,0)
            bar_height=(baseline-top-10)*v/maximum
            if v: out.append(f'<rect x="{x+m*bar_w:.1f}" y="{baseline-bar_height:.1f}" width="{max(2,bar_w-1):.1f}" height="{max(1,bar_height):.1f}" fill="{_COLORS[m]}"/>')
        out.append(f'<text x="{x+bar_group/2-1:.1f}" y="{baseline+16}" text-anchor="middle" font-size="10" fill="#223">{year}</text>')
        if year in sparse:
            total=sum(int(volumes[year].get(k,0)) for k,_ in metrics)
            out.append(f'<circle cx="{x+bar_group/2-1:.1f}" cy="{top+22}" r="5" fill="#b84726"/><text x="{x+bar_group/2-1:.1f}" y="{top+12}" text-anchor="middle" font-size="10" fill="#923c22">{total}</text>')
    for m,(_,label) in enumerate(metrics):
        out.append(f'<rect x="{left+m*95}" y="8" width="9" height="9" fill="{_COLORS[m]}"/><text x="{left+m*95+13}" y="17" font-size="10" fill="#223">{escape(label)}</text>')
    out.append('</svg>')
    payload=escape(json.dumps({str(y):[volumes[y].get(k,0) for k,_ in metrics] for y in years},separators=(',',':')),quote=True)
    return f'<div class="year-chart" data-yearly="{payload}" data-sparse="{escape(json.dumps(sorted(sparse)),quote=True)}">'+''.join(out)+'</div>'

def _yearly_table(volumes, *, registrations=None):
    metrics=_chart_metrics(registrations)
    headings=('År',*(label for _,label in metrics))
    return _table(headings, [(year,*(registrations.get(year,'–') if key=='registration' else volumes[year].get(key,0)
                                  for key,_ in metrics)) for year in sorted(volumes)])

def _yearly_section(job, data, *, compact=False):
    volume=combined_volumes(archive_part_volumes(data))
    if not volume:
        return '<p class="note">Ingen årsfordeling i lagret depotrapport.</p>'
    registrations=registration_years(data)
    out=_yearly_chart(volume,compact=compact,registrations=registrations)
    if registrations is None and not compact:
        out+='<p class="note">Registreringer per år: ikke lagret i dette DWM-grunnlaget (ukjent, ikke null). Journalposter er en egen kategori.</p>'
    boundary=sparse_boundary_years(volume)
    if boundary:
        out+='<p class="year-summary">Lavt årsvolum i ytterår – til faglig vurdering: '+', '.join(f'{y} ({amount} serietellinger; ikke unike objekter)' for y,amount in boundary)+'</p>'
    if not compact:out+=_yearly_table(volume,registrations=registrations)
    return out

def _overview_entry(job, data, diagnostic):
    """Present an unapproved, document-based period as a proposal, not a fact."""
    label = _extraction_label(job, data)
    status = _review_status(job, data) if data else 'Kan ikke vurderes'
    if data:
        candidate = review_candidate(data)
        declared = candidate.get('declared_years') or []
        proposed = candidate.get('proposed_years') or []
        saved = load_assessment(job)
        if (len(declared) == 2 and declared[1] == 2099
                and len(proposed) == 2 and proposed[1] < 2099
                and not reviewed_years(saved)):
            # Keep the native extraction identifier while not passing a fictitious
            # submitted end-year off as a scientifically verified archive period.
            import re
            label = re.sub(r' \(oppgitt .*?; krever vurdering\)$', '', label)
            label += f' ({proposed[0]}–{proposed[1]}, foreslått)'
            status += f' – 2099 er fiktivt oppgitt sluttår; forslag {proposed[0]}–{proposed[1]}'
    remark = ''
    if data:
        candidate = review_candidate(data)
        declared = candidate.get('declared_years') or []
        observed = candidate.get('observed_years') or []
        saved = load_assessment(job)
        approved = reviewed_years(saved) or []
        if len(declared) == 2 and len(approved) == 2 and list(declared) != list(approved):
            remark = (f'Oppgitt {declared[0]}–{declared[1]}; '
                      f'faglig vurdert {approved[0]}–{approved[1]}')
            if declared[1] == 2099 and approved[1] != 2099:
                year_data = combined_volumes(archive_part_volumes(data))
                folders_2099 = (year_data.get(2099) or {}).get('folder')
                if isinstance(folders_2099, int) and folders_2099 > 0:
                    # Count comes from the persisted yearly folder series, never
                    # from the submitted end year or an assumed default.
                    noun = 'sak/mappe' if folders_2099 == 1 else 'saker/mapper'
                    adjective = 'observert' if folders_2099 == 1 else 'observerte'
                    remark += f'; 2099: {folders_2099} {adjective} {noun} (til vurdering)'
        elif len(observed) == 2 and len(declared) == 2 and list(observed) != list(declared):
            remark = f'Oppgitt {declared[0]}–{declared[1]}; observert {observed[0]}–{observed[1]}'
    progress = getattr(job, 'progress', None)
    progress_text = f'{round(progress*100)} %' if isinstance(progress, (int, float)) else '–'
    state = getattr(job, 'status', None)
    state_text = getattr(state, 'value', str(state or '–'))
    return (str(job.job_id), label, _archive_names(data), status, remark,
            state_text, progress_text,
            'Funnet' if data else 'Mangler / kan ikke leses')


def _main(jobs, rows, level="Medium", *, u2_model=None, period_model=None, source_comparison=None):
    available = [(j,d) for j,d,_,_ in rows if d]
    tech_rows=[]
    kinds=Counter()
    affected={}
    external_bad=[]
    for job,d in available:
        t=d.get('technical_validation') or {}
        s=t.get('summary') or {}
        tech_rows.append((job.job_id,s.get('ok','–'),s.get('error','–'),(t.get('reconciliation') or {}).get('mismatch','–')))
        for dev in d.get('deviations') or []:
            kind=dev.get('category') or 'uten_kategori'
            kinds[kind]+=1
            affected.setdefault(kind,set()).add(job.job_id)
        ext=_external_values(d)
        if len(ext)>2 and isinstance(ext[2],int) and ext[2]>0:
            external_bad.append(job.job_id)
    pending=[(j.job_id,_extraction_label(j,d),_review_status(j,d)) for j,d in available if _review_status(j,d) not in ('Samsvar','Faglig vurdert','Godkjent')]
    body='<p>Generert '+escape(datetime.now().astimezone().isoformat(timespec='seconds'))+' · '+str(len(jobs))+' jobber · '+str(len(available))+' depotrapporter funnet.</p>'
    body+='<p class="note">Basert på lagrede resultater. «Ferdig» betyr ikke depotgodkjent. Manglende importert evidens skal ikke forstås som fravær av dokumenter.</p>'
    body+='<h2>Jobboversikt – alle uttrekk</h2><p>Alle valgte jobber listes i hovedrapporten. Oppgitt periode, observerte ytterår og lagrede faglige vurderinger holdes adskilt. Forslag er aldri godkjenning.</p>'
    body+=_table(('Jobb','Uttrekk','Arkivdel(er)','Periodevurdering','Periodemerknad','Status','Fremdrift','Depotrapport'),
                 [_overview_entry(j,d,diagnostic) for j,d,_p,diagnostic in rows]).replace('<table>', '<table class="job-overview">', 1)
    if level != 'Enkel':
        body+='<h2>Årlig produksjonsvolum per uttrekk</h2><p class="note">Kompakte grafer fra lagret XPath-grunnlag. Saker, registreringer (når tilgjengelige), journalposter, dokumentbeskrivelser og dokumentobjekter; ytterår vurderes faglig. År uten aktivitet mellom ytterår vises ikke som ordinære produksjonsår.</p>'
    if level != "Enkel":
        for j,d in available:
            body+='<h3>'+escape(str(j.job_id)+' – '+_extraction_label(j,d))+'</h3>'+_yearly_section(j,d,compact=True)
    body+='<h2>Samlet omfang – DWM og valgt KDRS Query</h2>'+render_count_overview(report_count_overview(rows))
    if source_comparison is not None:
        body+='<h2>KDRS Query Standard/U1 – observerte hovedtall</h2>'+render_source_comparison_whole_counts(source_comparison)
    body+='<h2>Ekstern evidens – importstatus per uttrekk</h2>'+render_external_status(external_status_rows(rows))
    if u2_model is None: u2_model=collect_u2_archive_parts(rows)
    body+='<h2>KDRS Query U2 – arkivdelvis sammenstilling</h2>'+render_u2_archive_parts(u2_model)
    body+='<h2>Teknisk kontroll</h2><p>'+str(len(tech_rows))+' uttrekk med tilgjengelige tekniske resultater. Se vedlegg C for resultat per uttrekk.</p>'
    if period_model is not None:
        body+='<h2>Periodegrunnlag – DWM og KDRS Query</h2>'+render_period_source_overview(period_model)
    body+='<h2>Åpne periodevurderinger</h2>' + (_table(('Jobb','Uttrekk','Status'),pending) if pending else '<p>Ingen avvikende periodevurderinger registrert i denne rapporten.</p>')
    body+='<h2>Grupperte vurderingspunkter</h2><p>Antall berørte uttrekk – ikke antall individuelle feil. Se vedlegg A og C for detaljer.</p>'
    body+=_table(('Kategori','Berørte uttrekk','Observasjoner'),[(k,len(affected[k]),kinds[k]) for k in sorted(kinds)])
    body+='<h2>Ekstern kontroll</h2><p>Historisk Arkade-evidens i lagrede depotrapporter har feilindikasjoner for '+str(len(external_bad))+' av '+str(len(available))+' uttrekk. Dette er ikke alle importerte Arkade-tester og ikke antall unike feil. Detaljer og nyere importer finnes i vedlegg C.</p>'
    body+='<h2>Rapportvedlegg</h2><p>Se navigasjonen øverst for detaljer per uttrekk, arkivdel, teknisk evidens og periodevurdering.</p>'
    return body

def write_report_package(directory, jobs, options: ReportOptions, *, prefix="", formats=("html",), overwrite=False, on_warning=None):
    """Create index plus selected appendices; never modify jobs or depot reports."""
    jobs=tuple(jobs)
    if not jobs:
        raise ValueError('Ingen jobber valgt')
    directory=Path(directory)
    formats=tuple(dict.fromkeys(str(fmt).lower() for fmt in formats))
    if not formats or any(fmt not in ("html", "pdf", "json") for fmt in formats):
        raise ValueError("Velg minst ett gyldig eksportformat: HTML, PDF eller JSON")
    prefix=safe_prefix(prefix)
    if directory.exists() and not directory.is_dir():
        raise ValueError('Rapportmål er ikke en mappe')
    # Reuse the exact renderer and evidence readers, avoiding a second report interpretation.
    # Appendix B uses the shared compact source model, not the legacy verbose annex.
    full=render_selected_jobs_report(jobs, ReportOptions('Full', (), True, False))
    sections=_extract_sections(full)
    buckets={'a':[],'b':[],'c':[],'d':[]}
    for title, section in sections:
        if title.startswith('Vedlegg – uttrekk:'):
            buckets['a'].append(section)
        elif title.startswith('Vedlegg – arkivdel:') or title.startswith('Vedlegg – arkivdeler:'):
            buckets['b'].append(section)
        elif title in ('Tekniske kontroller','Ekstern evidens','Kildesporbarhet'):
            buckets['c'].append(section)
        elif title in ('Periodeavstemming','Forslag og lagrede periodevurderinger'):
            buckets['d'].append(section)
    # Include graphic yearly volumes in the detailed appendices, while retaining
    # the existing full data tables, metadata and assessment evidence.
    rows=[(j,*_latest_report(j)) for j in jobs]
    evidence_by_job = {str(j.job_id): collect_job_evidence(j, d) for j, d, _path, _diagnostic in rows}
    # A single comparison model supplies the exact U2 facts to *all* report
    # views. Do not let the old overview attempt its own raw-text counting.
    source_comparison=build_source_comparison(rows, evidence_by_job=evidence_by_job)
    u2_model=collect_u2_archive_parts(rows, source_comparison=source_comparison)
    period_model=collect_period_sources(rows)
    extraction_sections=[]
    for j,d,_p,_diag in rows:
        if not d: continue
        extraction_sections.append('<h3>Årlig produksjonsvolum – '+escape(str(j.job_id))+'</h3>'+_yearly_section(j,d))
        # Appendix B is built once from the same structured U2/DWM model.
        # It renders actual yearly volumes there, omitting empty placeholders.
    enabled=set(options.enabled)
    wanted={'index.html':True,
       'vedlegg-a-uttrekk.html':options.extraction_appendix,
       'vedlegg-b-arkivdeler.html':options.archive_part_appendix,
       'vedlegg-c-teknisk-evidens.html':bool(enabled.intersection({'technical','external','sources'})),
       'vedlegg-d-periodevurdering.html':'period' in enabled}
    available=[name for name, flag in wanted.items() if flag]
    rows=[(j,*_latest_report(j)) for j in jobs]
    # The existing appendix sections stay in source order; charts follow their corresponding sections.
    for i, graphic in enumerate(extraction_sections):
        if i < len(buckets['a']): buckets['a'][i] = buckets['a'][i].replace('</section>',graphic+'</section>')

    compact_part_annex = render_archive_part_annex(
        rows, u2_model, volume_chart=_yearly_chart,
        year_registration=registration_years, volumes_by_part=archive_part_volumes,
        extraction_label=_extraction_label, part_period_html=_part_period_annex)
    bodies={'index.html':_main(jobs,rows,options.level,u2_model=u2_model,period_model=period_model,source_comparison=source_comparison) + '<h2>DWM XPath / Arkade 5 / KDRS Query – felles sammenstilling</h2>' + render_source_comparison_overview(source_comparison),
            'vedlegg-a-uttrekk.html':'\n'.join(buckets['a']),
            'vedlegg-b-arkivdeler.html':compact_part_annex,
            'vedlegg-c-teknisk-evidens.html':'\n'.join(buckets['c']) + render_source_comparison_annex(source_comparison, level=options.level),
            'vedlegg-d-periodevurdering.html':'\n'.join(buckets['d'])+render_period_source_annex(period_model)}
    pages = {name:_page('Noark 5 – '+NAMES[name], bodies[name] or '<p>Ingen relevante lagrede resultater.</p>', available,
                        {n:prefix+n for n in available}) for name in available}
    paths = {}  # Build and validate the entire destination set before writing.
    for name in available:
        stem=Path(name).stem
        for fmt in formats:
            paths[(name,fmt)] = directory / (prefix+stem+'.'+fmt)
    conflicts=[str(p) for p in paths.values() if p.exists()]
    if conflicts and not overwrite:
        raise FileExistsError('Filene finnes allerede: '+', '.join(conflicts))
    # Prepare format data without changing the depot reports or job state.
    prepared={}
    pdf_error=None
    if 'pdf' in formats:
        try:
            for name in available:
                prepared[(name,'pdf')]=_pdf_bytes(pages[name])
        except Exception as exc:
            pdf_error=str(exc)
            formats=tuple(fmt for fmt in formats if fmt!='pdf')
            if on_warning is not None:
                on_warning('PDF ble ikke eksportert: '+pdf_error)
            if not formats:
                raise RuntimeError('PDF-eksport feilet: '+pdf_error) from exc
    if 'json' in formats:
        base={'schema':'ikamr.noark5.selected_report.v1',
              'generated_at':datetime.now().astimezone().isoformat(timespec='seconds'),
              'report_title':'Noark 5 – Hovedrapport',
              'report_options':{'level':options.level,'sections':list(options.enabled),
                                'extraction_appendix':options.extraction_appendix,
                                'archive_part_appendix':options.archive_part_appendix},
              'jobs':[],
              'main_count_overview': report_count_overview(rows),
              'external_import_status': external_status_rows(rows),
              'kdrs_u2_archive_parts':u2_model,
              'period_source_evidence':period_model,
              'source_comparison':source_comparison}
        for job,data,path,diagnostic in rows:
            entry={'job_id':str(job.job_id),'extraction':_extraction_label(job,data),
                   'archive_parts':_archive_names(data),'period_status':_review_status(job,data) if data else 'Mangler grunnlag',
                   'source_file':str(path) if path else None,
                   'diagnostic':diagnostic,
                   'depot_report':data,
                   'period_assessment':load_assessment(job) if data else None}
            if 'external' in options.enabled:
                entry['external_evidence'] = evidence_by_job[str(job.job_id)]
            base['jobs'].append(entry)
        for name in available:
            payload=copy.deepcopy(base)
            payload['part']=Path(name).stem
            if name != 'index.html':
                # Same complete structured source, with explicit report part for standalone use.
                payload['section_html_excluded']=True
            prepared[(name,'json')]=json.dumps(payload,ensure_ascii=False,indent=2,default=str).encode('utf-8')
    directory.mkdir(parents=True,exist_ok=True)
    for name in available:
        for fmt in formats:
            dest=paths[(name,fmt)]
            content=pages[name].encode('utf-8') if fmt=='html' else prepared[(name,fmt)]
            temp=dest.with_name(dest.name+'.tmp')
            temp.write_bytes(content)
            temp.replace(dest)
    return paths[('index.html', 'html' if 'html' in formats else formats[0])]


def safe_prefix(value):
    """Filename prefix is user-controlled; cannot create a directory or overwrite arbitrary paths."""
    value=str(value or '').strip()
    if not value:
        return ''
    if value in ('.','..') or '/' in value or '\\' in value or any(c in value for c in '<>:"|?*'):
        raise ValueError('Prefiks må være et filnavn, ikke en sti')
    if any(ord(c)<32 for c in value) or value.endswith(('.', ' ')):
        raise ValueError('Ugyldig filnavnprefiks')
    return value if value.endswith(('-', '_')) else value+'_'


def _pdf_bytes(html_text):
    """Produce a real, printable PDF with wrapped text and repeated table headings."""
    try:
        from bs4 import BeautifulSoup, NavigableString
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle, KeepTogether
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.units import mm
    except ImportError as exc:
        raise RuntimeError('PDF-eksport krever reportlab og beautifulsoup4') from exc
    from reportlab.graphics.shapes import Drawing, Rect, String, Line
    from io import BytesIO
    from html import escape, unescape as esc
    soup=BeautifulSoup(html_text,'html.parser')
    buffer=BytesIO()
    doc=SimpleDocTemplate(buffer,pagesize=landscape(A4),leftMargin=14*mm,rightMargin=14*mm,
                          topMargin=15*mm,bottomMargin=15*mm)
    styles=getSampleStyleSheet()
    title=ParagraphStyle('TitleN',parent=styles['Heading1'],fontName='Helvetica-Bold',fontSize=16,leading=20,spaceAfter=10)
    heading=ParagraphStyle('HeadingN',parent=styles['Heading2'],fontName='Helvetica-Bold',fontSize=12,leading=15,spaceBefore=11,spaceAfter=6)
    subheading=ParagraphStyle('SubheadingN',parent=heading,fontSize=10,leading=13,spaceBefore=8,spaceAfter=4)
    item=ParagraphStyle('ItemN',parent=styles['Normal'],fontName='Helvetica',fontSize=9,leading=12,spaceAfter=5,wordWrap='CJK')
    cell=ParagraphStyle('CellN',parent=styles['Normal'],fontName='Helvetica',fontSize=7,leading=9,wordWrap='CJK')
    story=[]
    for elem in soup.body.descendants:
        if getattr(elem,'name',None) in ('h1','h2','h3','h4'):
            story.append(Paragraph(esc(elem.get_text(' ',strip=True)), title if elem.name=='h1' else (subheading if elem.name=='h4' else heading)))
        elif getattr(elem,'name',None)=='p':
            story.append(Paragraph(esc(elem.get_text(' ',strip=True)),item))
        elif getattr(elem,'name',None)=='div' and 'year-chart' in (elem.get('class') or []):
            try:
                volume=json.loads(elem.get('data-yearly') or '{}')
                if volume:
                    years=sorted(volume,key=int)
                    chart_width=740; chart_height=125
                    max_v=max((int(v) for row in volume.values() for v in row),default=1) or 1
                    group_width=(chart_width-45)/len(years)
                    drawing=Drawing(chart_width,chart_height)
                    drawing.add(Line(38,24,chart_width,24,strokeColor=colors.HexColor('#708090')))
                    sparse={str(y) for y in json.loads(elem.get('data-sparse') or '[]')}
                    for index,year in enumerate(years):
                        if index and int(year)-int(years[index-1])>1:
                            drawing.add(String(38+index*group_width-3,2,'//',fontSize=8,fillColor=colors.HexColor('#923c22')))
                        for k,v in enumerate(volume[year]):
                            width=max(2,(group_width-5)/len(volume[year]))
                            hh=85*int(v)/max_v
                            if v:drawing.add(Rect(38+index*group_width+k*width,24,width-0.5,max(1,hh),fillColor=colors.HexColor(_COLORS[k]),strokeColor=None))
                        drawing.add(String(38+(index+0.4)*group_width,11,year,fontSize=7,textAnchor='middle'))
                        if year in sparse:
                            total=sum(int(v) for v in volume[year])
                            drawing.add(Rect(38+(index+0.4)*group_width-2,102,4,4,fillColor=colors.HexColor('#b84726'),strokeColor=None))
                            drawing.add(String(38+(index+0.4)*group_width,108,str(total),fontSize=8,textAnchor='middle',fillColor=colors.HexColor('#923c22')))
                    drawing.add(String(0,110,str(max_v),fontSize=7))
                    story.append(drawing)
            except (ValueError,TypeError,KeyError,ZeroDivisionError):
                pass
        elif getattr(elem,'name',None)=='table':
            raw=[]
            for tr in elem.find_all('tr'):
                # Keep separately listed archive parts on separate lines in PDF,
                # not only in HTML. Escape text BEFORE restoring safe ReportLab br.
                row=[Paragraph(esc(td.get_text('\n' if td.find('br') else ' ',strip=True)).replace('\n','<br/>'),cell)
                     for td in tr.find_all(['th','td'],recursive=False)]
                if row:raw.append(row)
            if raw:
                width=(landscape(A4)[0]-28*mm)/max(map(len,raw))
                n=max(map(len,raw))
                raw=[r+[Paragraph('',cell)]*(n-len(r)) for r in raw]
                is_overview = elem.get('class') and 'job-overview' in elem.get('class')
                if is_overview and n == 8:
                    total_width=landscape(A4)[0]-28*mm
                    first=67
                    weights=[2.3,2.6,1.3,2.0,0.7,0.72,0.9]
                    widths=[first]+[(total_width-first)*w/sum(weights) for w in weights]
                else:
                    widths=[width]*n
                tab=LongTable(raw,colWidths=widths,repeatRows=1,hAlign='LEFT')
                tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9eff5')),
                            ('GRID',(0,0),(-1,-1),0.25,colors.HexColor('#cbd1dc')),
                            ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),4),
                            ('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),4),
                            ('BOTTOMPADDING',(0,0),(-1,-1),4)]))
                story.append(tab)
    doc.build(story)
    return buffer.getvalue()
