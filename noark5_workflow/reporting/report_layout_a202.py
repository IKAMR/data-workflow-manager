"""Readability-only presentation for the shared a20 selected-job reporter.

Works on existing rendered HTML. No XPath re-execution, source reassignment,
period approval, calculation of master numbers, or rewriting stored evidence.
Keeps all source tables available in offline HTML and in underlying JSON.
"""
from __future__ import annotations

from collections import OrderedDict
from html import escape, unescape
import json
import re
from typing import Any


_STYLE = r'''
/* a20.2: common report layout; applied to each exported HTML page */
html {scroll-padding-top:115px}
.report-table-scroll {max-width:100%; overflow-x:auto; margin:12px 0 20px;
                     border:1px solid #d6dfe9; border-radius:4px}
.report-table-scroll table {margin:0; border:0}
.report-table-scroll:focus {outline:2px solid #2c639b; outline-offset:2px}
.report-table-scroll > table.report-wide-table {width:100%; min-width:var(--report-min-width,1100px)}
.report-job-table th:first-child,.report-job-table td:first-child,.report-job-id {
    min-width:88px !important;width:88px;white-space:nowrap !important;
    word-break:keep-all !important;overflow-wrap:normal !important;
}
.report-job-table td.report-job-id {font-variant-numeric:tabular-nums}
.report-number {white-space:nowrap;text-align:right;font-variant-numeric:tabular-nums}
.report-count-head {min-width:78px; max-width:125px; overflow-wrap:normal; word-break:normal}
.report-wide-table td.report-uuid {min-width:125px;max-width:185px;overflow-wrap:anywhere;word-break:break-word}
.report-wide-table th,.report-wide-table td {vertical-align:top}
.report-wide-table tbody tr:nth-child(even) {background:#f8fafc}
.report-job-navigation {margin:12px 0 24px;padding:12px 15px;background:#f4f7fb;border:1px solid #d8e2ef;border-radius:5px}
.report-job-navigation h2 {margin:0 0 7px;font-size:12pt}
.report-job-navigation p {margin:3px 0 9px}
.report-job-links {display:grid;grid-template-columns:repeat(auto-fit,minmax(235px,1fr));gap:6px 12px}
.report-job-links a {padding:5px 8px;border-bottom:1px solid #dce4ef;text-decoration:none}
.report-job-links a:hover,.report-job-links a:focus {background:#e8f0fa;text-decoration:underline}
.report-job {padding-bottom:12px;scroll-margin-top:115px}
.report-job-heading {position:sticky;top:49px;z-index:40;background:#eaf1f9;
      padding:9px 11px;border-left:4px solid #3d6593;box-shadow:0 2px 4px #00000014;
      line-height:1.35;margin:18px 0 9px}
.report-part-heading {position:sticky;top:102px;z-index:30;background:#f1f4f8;
      border-left:3px solid #7895b4;padding:7px 9px;margin:12px 0 5px}
.report-top-link {font-size:10pt;margin-left:8px;font-weight:normal;white-space:nowrap}
.report-fold {border:1px solid #cbd6e3;border-radius:4px;padding:7px 11px;margin:9px 0;background:#fff}
.report-fold > summary {cursor:pointer;font-weight:600;line-height:1.5;color:#244d7a;padding:3px}
.report-fold[open] {background:#fafcfe}
.report-fold > table,.report-fold > .report-table-scroll {margin:11px 0}
.report-source-group {border-left:4px solid #8babc9;padding:8px 12px}
.report-year-multiples {margin:12px 0 16px}
.report-series {margin:10px 0 14px;max-width:1050px}
.report-series figcaption {font-weight:600;color:#243b55;margin:0 0 3px}
.report-series svg {display:block;width:100%;height:auto;max-height:220px}
.report-note {color:#526071;font-size:10pt}
.report-inline-context {font-weight:600;margin:6px 0;color:#3c4b5c}
@media print {
    nav,.report-job-navigation,.report-top-link {display:none}
    .report-job-heading,.report-part-heading {position:static;box-shadow:none;break-after:avoid}
    .report-table-scroll {overflow:visible;border:0;max-width:none}
    .report-wide-table {min-width:0 !important;width:100% !important}
    .report-fold {break-inside:auto}
}
'''


def _h(value: Any) -> str:
    return escape(str(value), quote=True)


def _plain(value: str) -> str:
    return unescape(re.sub(r'<[^>]*>', '', value)).strip()


def _short_extraction(value: str) -> str:
    """Only for navigation display, not an archive identity or matching key."""
    return str(value).split(' (', 1)[0]


def _job_nav(snapshot: dict, phase: str) -> str:
    labels={'c-sources':'Ekstern evidens','c-comparison':'Kildematriser','d':'Faglige periodevurderinger'}
    links=[]
    for job in snapshot.get('jobs') or []:
        jid=job.get('job_id') or ''
        token=re.sub(r'[^a-z0-9-]', '-', jid.lower())
        label=_short_extraction(job.get('extraction') or '')
        links.append(f'<a href="#{phase}-{token}">{_h(jid)} – {_h(label)}</a>')
    if not links:
        return ''
    return ('<div class="report-job-navigation" id="report-job-nav-'+phase+'">'
            '<h2>'+_h(labels.get(phase,'Velg uttrekk'))+'</h2>'
            '<p>Velg uttrekk for å hoppe til kildene. Kontrolltabellene kan åpnes ved behov.</p>'
            '<div class="report-job-links">'+''.join(links)+'</div></div>')


def _heading_split(label: str) -> str:
    # Break *header labels only* (never data cells), keep long compound labels readable.
    breaks={
        'Dokumentbeskrivelser':'Dokument<br>beskrivelser',
        'Dokumentobjekter':'Dokument<br>objekter',
        'Journalposter':'Journal<br>poster',
        'Registreringer':'Registrer<br>inger',
        'Faglig periode':'Faglig<br>periode',
        'Vurderingsstatus':'Vurderings<br>status',
        'Krysskontroll avvik':'Krysskontroll<br>avvik',
        'PRONOM-filobservasjoner':'PRONOM-fil<br>observasjoner',
        'Dokumentstatus':'Dokument<br>status',
    }
    return breaks.get(label, _h(label))


def _with_class(attrs: str, css: str) -> str:
    match=re.search(r'\bclass=("[^"]*"|\'[^\']*\')', attrs)
    if not match:
        return attrs+' class="'+_h(css)+'"'
    quote=match.group(1)[0]
    existing=match.group(1)[1:-1].split()
    extra=[x for x in css.split() if x not in existing]
    return attrs[:match.start()]+f'class={quote}'+ ' '.join(existing+extra)+quote+attrs[match.end():]


def _format_tables(html: str) -> str:
    """Shared HTML table layout, irrespective of which a19/a20 renderer made it."""
    tab=re.compile(r'<table(?P<attrs>[^>]*)>(?P<body>.*?)</table>',re.S | re.I)
    job_cell=re.compile(r'(<td)(?P<attrs>[^>]*)(>)(?P<job>JOB-[A-Za-z0-9_-]+)(</td>)', re.I)
    def format_table(m):
        attrs,body=m.group('attrs'),m.group('body')
        header=re.search(r'<thead[^>]*>.*?<tr[^>]*>(.*?)</tr>',body,re.S | re.I)
        headings=re.findall(r'<th(?:\s[^>]*)?>(.*?)</th>',header.group(1),re.S | re.I) if header else []
        n=len(headings)
        job=bool(headings and _plain(headings[0]).casefold() in ('jobb','job'))
        numeric_cols={i for i,h in enumerate(headings) if any(s in _plain(h).casefold() for s in (
            'antall','mapper','registreringer','journalposter','dokumentbeskrivelser',
            'dokumentobjekter','feil','avvik','kontroller','observerte'))}
        if job:
            attrs=_with_class(attrs,'report-job-table')
            body=job_cell.sub(lambda j: '<td'+_with_class(j.group('attrs'),'report-job-id')+'>'+j.group('job')+'</td>',body)
        if n >= 8:
            attrs=_with_class(attrs,'report-wide-table')
            for title in sorted(set(_plain(v) for v in headings),key=len,reverse=True):
                if title in ('Jobb','JOB'):continue
                rewritten=_heading_split(title)
                if rewritten == _h(title):
                    continue
                old='<th>'+_h(title)+'</th>'
                body=body.replace(old,'<th class="report-count-head">'+rewritten+'</th>')
        # The native system ID is full and available; allow long UUIDs to wrap.
        body=re.sub(r'<td>([a-f0-9]{8}-[a-f0-9-]{27,})</td>',r'<td class="report-uuid">\1</td>',body,flags=re.I)
        # Only mark simple positive numeric value cells; do not infer unknown=0.
        body=re.sub(r'<td>((?:\d[\d ,.]*|\d{4}–\d{4}))</td>',r'<td class="report-number">\1</td>',body)
        table='<table'+attrs+'>'+body+'</table>'
        if n >= 8:
            width=max(1100, 92*n+340)
            return ('<div class="report-table-scroll" role="region" tabindex="0" '
                    f'aria-label="Tabell med {n} kolonner, rull sideveis" '
                    f'style="--report-min-width:{width}px">'+table+'</div>')
        return table
    return tab.sub(format_table,html)


def _inject_style(text: str) -> str:
    if 'a20.2: common report layout' in text:
        return text
    return text.replace('</head>','<style>'+_STYLE+'</style></head>',1)


def _collapse_main_archive_lists(text: str) -> str:
    """Avoid a 43-line cell in the main report; retain original part names."""
    pattern=re.compile(r'(<table class="job-overview">.*?</table>)',re.S)
    hit=pattern.search(text)
    if not hit:return text
    html=hit.group(1)
    rows=re.finditer(r'<tr>(.*?)</tr>',html,re.S)
    for row in list(rows):
        line=row.group(0)
        cells=list(re.finditer(r'<td(?: [^>]*)?>.*?</td>',line,re.S))
        if len(cells)<4: continue
        cell=cells[2]
        value=cell.group()
        pieces=re.split(r'<br\s*/?>|\n',re.sub(r'^<td(?: [^>]*)?>|</td>$','',value))
        pieces=[part for part in pieces if part.strip()]
        if len(pieces) <= 8:continue
        content='<br>'.join(pieces)
        replacement=(f'<td><details class="report-fold"><summary>{len(pieces)} arkivdeler '
                     '– vis fullstendig liste</summary><div>'+content+'</div></details></td>')
        html=html.replace(line,line[:cell.start()]+replacement+line[cell.end():],1)
    return text[:hit.start()]+html+text[hit.end():]


def _wrap_table_detail(header: str, table: str, *, kind='report-fold', summary=None) -> str:
    rows=len(re.findall(r'<tbody\b[^>]*>.*?</tbody>',table,re.S))
    del rows
    n=len(re.findall(r'<tr\b',table,re.I))-1
    label=summary or f'Vis alle {max(n,0)} kilde-/kontrollrader'
    return header+f'<details class="{_h(kind)}"><summary>{_h(label)}</summary>'+table+'</details>'


def _label_u2_rows(text: str, job_id: str) -> tuple[str,int]:
    """U2 ordinal/title are explicitly **source** scope, not native DWM part ID."""
    pattern=re.compile(r'<h4>N5\.102\s*–\s*Konsentrert opptelling pr\. arkivdel \(u02\)</h4>\s*(<table>.*?</table>)',re.S)
    numbered=[0]
    def swap(m):
        numbered[0]+=1
        table=m.group(1)
        first=re.search(r'<tbody><tr><td>1</td><td>(.*?)</td></tr>',table,re.S)
        scope=_plain(first.group(1)) if first else f'Kildearkivdel {numbered[0]} (navn ukjent)'
        if not scope.casefold().startswith('arkivdel'):
            scope='KDRS kildearkivdel: '+scope
        if len(scope)>185:scope=scope[:180]+'…'
        heading='<h4 class="report-part-heading">'+_h(job_id)+' – U2 '+_h(scope)+'</h4>'
        return _wrap_table_detail(heading,table,summary='Vis full U2-rapport – '+scope)
    result=pattern.sub(swap,text)
    return result,numbered[0]


def _collapse_controls(text: str) -> str:
    pattern=re.compile(r'<h4>Noark 5-tester</h4>\s*(<table>.*?</table>)',re.S)
    def swap(m):
        table=m.group(1)
        n=max(0,len(re.findall(r'<tr>',table))-1)
        errors=[]
        for row in re.findall(r'<tr>(.*?)</tr>',table,re.S):
            cells=re.findall(r'<td>(.*?)</td>',row,re.S)
            if len(cells)>=4 and _plain(cells[2]).casefold() in ('error','feil'):
                errors.append(_plain(cells[0])+' ('+_plain(cells[3])+' feil)')
        overview='<p><strong>Kontroller med feil:</strong> '+_h(', '.join(errors) if errors else 'Ingen rapportert')+'</p>'
        return overview + _wrap_table_detail('',table,summary=f'Noark 5-tester – {n} kontroller, {len(errors)} med feil (vis tabell)')
    return pattern.sub(swap,text)


def _collapse_long_details(text: str, *, cutoff=26) -> str:
    """Large source matrices stay complete, but no longer dominate the HTML page."""
    pattern=re.compile(r'(<h4>(?!Noark 5-tester)(.*?)</h4>)\s*(<table>.*?</table>)',re.S)
    def swap(m):
        title=_plain(m.group(2))
        table=m.group(3)
        n=max(0,len(re.findall(r'<tr\b',table))-1)
        if n < cutoff:return m.group(0)
        return _wrap_table_detail(m.group(1),table,summary=f'{n} rader – vis detaljert {title}')
    return pattern.sub(swap,text)


def _collapse_kdrs_source_group(source: str, count_u2: int) -> str:
    """The KDRS standard/U1/U2 source pool is a large optional audit section."""
    heading='<h4>KDRS Query – Standard / U1 / U2</h4>'
    if heading not in source:return source
    earlier, remainder=source.split(heading,1)
    sections=len(re.findall(r'<h4\b',remainder,re.I))
    if not sections and '<table' not in remainder:
        # Keep 'no KDRS imports' visible; folding an empty source is misleading.
        return source
    info=(f'KDRS Query: {sections} detaljerte kildeområder'
          + (f', inkludert {count_u2} U2-arkivdeler' if count_u2 else '')
          + '. U2-indekser er ikke DWM system-ID-er.')
    summary=('Vis KDRS Query Standard / U1 / U2 – '
             f'{sections} kildeområder' + (f', {count_u2} U2-arkivdeler' if count_u2 else ''))
    return (earlier+'<p class="report-inline-context">'+_h(info)+'</p>'+
            '<details class="report-fold report-source-group"><summary>'+_h(summary)+
            '</summary>'+heading+remainder+'</details>')


def _c_job_sections(text: str, snapshot: dict) -> str:
    """Two independently navigable per-job groups: imports and source matrices."""
    jobs={j['job_id']:j.get('extraction') or '' for j in snapshot.get('jobs') or []}
    pat=re.compile(r'<h3>(JOB-[A-Za-z0-9_-]+) – (Arkade 5 / PRONOM / KDRS Query|kildematrise)</h3>')
    found=list(pat.finditer(text))
    if not found:return text
    output=[]; cursor=0
    for i,m in enumerate(found):
        phase='c-sources' if m.group(2).startswith('Arkade') else 'c-comparison'
        # The h2 boundary after the evidence group is outside the per-job section.
        end=found[i+1].start() if i+1<len(found) else text.find('</body>',m.end())
        boundary=re.search(r'<h2>(?:Kildesporbarhet|Felles kontroll- og måltallssammenstilling)[^<]*</h2>',text[m.end():end])
        if boundary:end=m.end()+boundary.start()
        jid=m.group(1)
        slug=re.sub(r'[^a-z0-9-]','-',jid.lower())
        src=text[m.end():end]
        if phase=='c-sources':
            src,count=_label_u2_rows(src,jid)
            src=_collapse_controls(src)
            src=_collapse_long_details(src)
            src=_collapse_kdrs_source_group(src,count)
            if count:
                # The complete imported source content remains available.
                title='<p class="report-note">KDRS Query U2: '+str(count)+' kildearkivdeler. '
                title+='U2-indeks og tittel er ikke automatisk koblet til DWM system-ID.</p>'
                marker='<h4>KDRS Query – Standard / U1 / U2</h4>'
                src=src.replace(marker,marker+title,1)
        else:
            src=_collapse_long_details(src,cutoff=28)
        heading=(f'<h3 class="report-job-heading">{_h(jid)} – {_h(jobs.get(jid) or jid)} '
                 f'· {"Ekstern evidens" if phase=="c-sources" else "Kildematrise"}'
                 f' <a class="report-top-link" href="#report-job-nav-{phase}">Til uttrekksoversikten ↑</a></h3>')
        output.append(text[cursor:m.start()])
        output.append(f'<section class="report-job" id="{phase}-{slug}">'+heading+src+'</section>')
        cursor=end
    output.append(text[cursor:])
    return ''.join(output)


def _c_navigation(text: str, snapshot: dict) -> str:
    links=_job_nav(snapshot,'c-sources')
    if not links:return text
    links += ('<p class="report-note">Under hvert uttrekk er Arkade, PRONOM og KDRS '
              'separate kilder. Kontroller uten avvik og store råtabeller kan åpnes '
              'med «Vis». Kildematriser ligger lenger ned.</p>')
    src_links=_job_nav(snapshot,'c-comparison')
    # Place separate quick navigation at the beginning of the comparison area.
    anchor='<h2>Felles kontroll- og måltallssammenstilling – DWM / Arkade 5 / KDRS Query</h2>'
    if anchor in text:
        text=text.replace(anchor,anchor+src_links,1)
    return re.sub(r'(</h1>)',lambda m:m.group(1)+links,text,count=1)


def _rows_year_table(table: str) -> OrderedDict[str,dict[int,int]]:
    by_metric: OrderedDict[str,dict[int,int]] = OrderedDict()
    for tr in re.findall(r'<tr>(.*?)</tr>',table,re.S):
        cells=re.findall(r'<td(?: [^>]*)?>(.*?)</td>',tr,re.S)
        if len(cells)!=3:continue
        metric=_plain(cells[0]);y=_plain(cells[1]);n=_plain(cells[2]).replace(' ','')
        if not re.fullmatch(r'\d{4}',y) or not re.fullmatch(r'\d+',n):
            continue
        yy=int(y);vv=int(n)
        if not 1000<=yy<=9999:continue
        metric_rows=by_metric.setdefault(metric,{})
        if yy in metric_rows and metric_rows[yy]!=vv:
            # Conflicting source values must not be plotted as a single fact.
            return OrderedDict()
        metric_rows[yy]=vv
    return by_metric


def _year_chart(label: str, years: dict[int,int]) -> str:
    """Plain inline SVG, and a19-compatible data-yearly for vector PDF export."""
    data=sorted(years.items())
    if not data:return ''
    span=max(710, len(data)*27+80)
    baseline=141; top=25; maxv=max(v for _y,v in data) or 1
    usable=baseline-top-10
    xstep=(span-104)/len(data)
    bars=[]
    skip=max(1,(len(data)+23)//24)
    prev=None
    for i,(year,count) in enumerate(data):
        x=61+i*xstep + xstep*0.23
        width=min(19,max(5,xstep*0.56))
        hh=max(1.0,usable*count/maxv) if count else 0
        if count:
            bars.append(f'<rect x="{x:.2f}" y="{baseline-hh:.2f}" width="{width:.2f}" '
                        f'height="{hh:.2f}" fill="#3b76a3"><title>{year}: {count:,} observasjoner</title></rect>')
        if i % skip==0 or i==len(data)-1 or (prev is not None and year-prev>1):
            bars.append(f'<text x="{x+width/2:.2f}" y="{baseline+17}" text-anchor="middle" font-size="11" fill="#24394e">{year}</text>')
        if prev is not None and year-prev>1:
            bars.append(f'<text x="{x-7:.2f}" y="{baseline+31}" font-size="12" fill="#a15d20">//</text>')
        prev=year
    source={str(y):[c] for y,c in data}
    encoded=_h(json.dumps(source,separators=(',',':')))
    svg=('<svg xmlns="http://www.w3.org/2000/svg" role="img" '
         f'aria-label="Årsfordeling – {_h(label)}" viewBox="0 0 {span} 184">'
         f'<line x1="53" y1="{baseline}" x2="{span-6}" y2="{baseline}" stroke="#94a6b7"/>'
         f'<text x="3" y="{top+5}" font-size="11" fill="#4a5b6e">Maks: {maxv:,}</text>'
         +''.join(bars)+'</svg>')
    return ('<figure class="report-series"><figcaption>'+_h(label)+f' · {len(data)} år med registrerte tall</figcaption>'
            f'<div class="year-chart" data-yearly="{encoded}" data-sparse="[]">'+svg+'</div></figure>')


def _d_year_tables(text: str) -> str:
    """Replace 117-row year tables with source-local charts + reversible details."""
    pattern=re.compile(r'(<h4>Hele uttrekket[^<]*</h4>)\s*(<table><thead><tr>'
                       r'<th>Datokilde / måltall</th><th>År</th><th>Antall</th>'
                       r'</tr></thead><tbody>.*?</tbody></table>)',re.S)
    n=[0]
    def swap(m):
        rows=_rows_year_table(m.group(2))
        if not rows:
            # If schema/conflict is unexpected, never invent a chart or discard table.
            return m.group(0)
        n[0]+=1
        prominent=[label for label in rows if not ('journal (journaldato)' in label.casefold() or 'endringslogg' in label.casefold())]
        # Standard journalposts != running/public journal; keep it prominent.
        prominent=[label for label in rows if (label.startswith(('Mapper/','Registreringer','Journalposter')))]
        if not prominent:prominent=list(rows)[:3]
        other=[x for x in rows if x not in prominent]
        chart='<div class="report-year-multiples">'+''.join(_year_chart(k,rows[k]) for k in prominent)+'</div>'
        if other:
            chart += ('<details class="report-fold"><summary>Vis '+str(len(other))+
                      ' supplerende årsfordelinger fra samme kilde</summary><div class="report-year-multiples">'+
                      ''.join(_year_chart(k,rows[k]) for k in other)+'</div></details>')
        amount=sum(len(vals) for vals in rows.values())
        chart += _wrap_table_detail('',m.group(2),kind='report-fold report-raw-year',
                                    summary=f'Vis opprinnelig årsopptelling – {amount} kildeverdier')
        chart += '<p class="report-note">Diagrammene viser antall per år fra hver kilde for seg. År uten registrert verdi tolkes ikke som 0. Endringslogg er ikke arkivperiode.</p>'
        return m.group(1)+chart
    return pattern.sub(swap,text)


def _d_part_assessments(text: str) -> str:
    pattern=re.compile(r'(<h3>JOB-[A-Za-z0-9_-]+ – periodevurdering per arkivdel</h3>)\s*'
                       r'(<table>.*?</table>)',re.S)
    def swap(m):
        n=max(0,len(re.findall(r'<tr>',m.group(2)))-1)
        if n<=6:return m.group(0)
        approved=len(re.findall(r'<td>Godkjent</td>',m.group(2)))
        return (m.group(1)+f'<p>{n} arkivdeler; {approved} faglig godkjent på arkivdelnivå.</p>'+
                _wrap_table_detail('',m.group(2),summary=f'Vis alle {n} arkivdelvise periodestatusene'))
    return pattern.sub(swap,text)


def _d_headings(text: str, snapshot: dict) -> str:
    jobs={j['job_id']:j.get('extraction') for j in snapshot.get('jobs') or []}
    pat=re.compile(r'<h3>(JOB-[A-Za-z0-9_-]+) – periodevurdering av hele uttrekket</h3>')
    def replace(m):
        jid=m.group(1); slug=re.sub(r'[^a-z0-9-]','-',jid.lower())
        label=jobs.get(jid) or jid
        return (f'<h3 id="d-{slug}" class="report-job-heading">{_h(jid)} – '
                f'{_h(label)} – periodevurdering av hele uttrekket '
                '<a class="report-top-link" href="#report-job-nav-d">Til uttrekksoversikten ↑</a></h3>')
    text=pat.sub(replace,text)
    return text


def _d_legacy_labels(text: str, snapshot: dict) -> str:
    # Fix a misleading legacy *XPath-only* conclusion for manual/KDRS review.
    for j in snapshot.get('jobs') or []:
        if 'KDRS Query tilgjengelig' not in j.get('professional_period_status',''):
            continue
        jid=_h(j.get('job_id'))
        label=_h(j.get('extraction') or '')
        # Older period tables alternate between Jobb as first column and the
        # extraction LABEL as first column. Both are only DWM XPath status.
        first_cell='(?:'+re.escape(jid)+'|'+re.escape(label)+')'
        pattern=re.compile(r'(<tr><td>'+first_cell+r'</td>.*?</tr>)',re.S)
        def swap(m):
            return m.group(1).replace('<td>Kan ikke vurderes</td>',
                        '<td>Uten DWM XPath-år – faglig vurdering mulig</td>')
        text=pattern.sub(swap,text)
    text=text.replace('<th>Godkjent/valgt</th>', '<th>Lagret periode (godkjent / utkast)</th>')
    return text


def _d_job_sections(text: str) -> str:
    """Constrain the sticky period identity to the selected extraction."""
    pat=re.compile(r'<h3 id="d-([a-z0-9-]+)" class="report-job-heading">')
    positions=list(pat.finditer(text))
    if not positions:return text
    pieces=[]; cursor=0
    for i,m in enumerate(positions):
        end=positions[i+1].start() if i+1<len(positions) else text.find('</body>',m.end())
        if end<0:end=len(text)
        pieces.append(text[cursor:m.start()])
        pieces.append('<section class="report-job">'+text[m.start():end]+'</section>')
        cursor=end
    pieces.append(text[cursor:])
    return ''.join(pieces)


def _c_page(text: str, snapshot: dict) -> str:
    text=_c_job_sections(text,snapshot)
    text=_c_navigation(text,snapshot)
    return text


def _d_page(text: str, snapshot: dict) -> str:
    text=_d_legacy_labels(text,snapshot)
    text=_d_headings(text,snapshot)
    text=_d_part_assessments(text)
    text=_d_year_tables(text)
    text=_d_job_sections(text)
    nav=_job_nav(snapshot,'d')
    # Place after the general period-index table, before the source/year tables.
    anchor='<section class=""><h2>Periodeavstemming</h2>'
    if anchor in text:text=text.replace(anchor,nav+anchor,1)
    else:text=text.replace('</h1>','</h1>'+nav,1)
    return text


def improve_report_html(text: str, filename: str, snapshot: dict, legacy_payload: dict | None = None) -> str:
    """Last, strictly presentational step in the central report service."""
    if filename=='index.html':
        text=_collapse_main_archive_lists(text)
    elif filename=='vedlegg-c-teknisk-evidens.html':
        text=_c_page(text,snapshot)
    elif filename=='vedlegg-d-periodevurdering.html':
        text=_d_page(text,snapshot)
    text=_format_tables(text)
    return _inject_style(text)
