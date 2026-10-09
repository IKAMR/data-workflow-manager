"""Field-level observations from historical KDRS Query standard/U1/U2 output.

Never infer the recipient DWM job from historic source filenames. Unmapped data
remain usable, searchable observations. No XPath execution or source edits.
"""
from __future__ import annotations

import re
from typing import Any

# Exact semantic labels only: similar numbers are deliberately not conflated.
FIELD_NAMES = {
 'archive_count': 'Arkiver', 'archive_part_count': 'Arkivdeler',
 'folder_count': 'Mapper', 'case_folder_count': 'Saksmapper',
 'meeting_folder_count': 'Møtemapper', 'registration_count': 'Registreringer',
 'journalpost_count': 'Journalposter', 'document_description_count': 'Dokumentbeskrivelser',
 'document_object_count': 'Dokumentobjekter',
 'classification_system_count': 'Klassifikasjonssystemer', 'class_count':'Klasser',
 'correspondence_party_count':'Korrespondanseparter',
 'screening_count':'Skjerminger', 'conversion_count':'Konverteringer',
 'document_description_without_object_count':'Dokumentbeskrivelser uten dokumentobjekt',
}

# Source context => label => explicit DWM metric. Anchors disallow accidental
# matches such as Elektr: 49926 being treated as total documents.
MAIN = {
 ('C01', 'standard'): [(r'^N5\.04 Arkiv:\s*(\d+)', 'archive_count')],
 ('C02', 'standard'): [(r'^N5\.05/06 Arkivdeler:\s*(\d+)', 'archive_part_count')],
 ('C05', 'standard'): [(r'^N5\.07 Klassifikasjonssystemer:\s*(\d+)', 'classification_system_count')],
 ('C06', 'standard'): [(r'^N5\.08 Klasser; Alle:\s*(\d+)', 'class_count')],
 ('C08', 'standard'): [(r'^N5\.10 Mapper pr\. type; Alle:\s*(\d+)', 'folder_count'),
                       (r'^saksmappe:\s*(\d+)', 'case_folder_count')],
 ('C14', 'standard'): [(r'^N5\.16 Registreringer pr\. type; Alle:\s*(\d+)', 'registration_count'),
                        (r'^Journalposter:\s*(\d+)', 'journalpost_count')],
 ('C21', 'standard'): [(r'^N5\.23 Dokumentbeskrivelser pr\. type; Alle:\s*(\d+)', 'document_description_count')],
 ('C22', 'standard'): [(r'^N5\.24 Dokumentbeskrivelser uten dokumentobjekt:\s*(\d+)', 'document_description_without_object_count')],
 ('C24', 'standard'): [(r'^N5\.26 Dokumentobjekt og variantformat:\s*(\d+)', 'document_object_count')],
 ('F05', 'standard'): [(r'^N5\.39 Korrespondanseparter; Alle:\s*(\d+)', 'correspondence_party_count')],
 ('F08', 'standard'): [(r'^N5\.42 Skjerminger; Alle:\s*(\d+)', 'screening_count')],
 ('F12', 'standard'): [(r'^N5\.46 Konverterte dokumenter:\s*(\d+)', 'conversion_count')],
 ('U01', 'u01'): [(r'^N5\.04 Arkiv:\s*(\d+)', 'archive_count'),
                  (r'^N5\.05/06 Arkivdeler:\s*(\d+)', 'archive_part_count'),
                  (r'^N5\.07 Klassifikasjonssystemer:\s*(\d+)', 'classification_system_count'),
                  (r'^N5\.08 Klasser:\s*(\d+)', 'class_count'),
                  (r'^N5\.39 Korrespondanseparter:\s*(\d+)', 'correspondence_party_count'),
                  (r'^N5\.42 Skjerminger:\s*(\d+)', 'screening_count'),
                  (r'^N5\.46 Konverterte dokumenter:\s*(\d+)', 'conversion_count'),
                  (r'^N5\.24 Dokumentbeskrivelser uten dokumentobjekt:\s*(\d+)', 'document_description_without_object_count')],
 ('U02', 'u02'): [(r'^\[\.2\] Mappe typer:.*?\bAlle:\s*(\d+)', 'folder_count'),
                  (r'^\[\.3\] Registreringer; Alle:\s*(\d+)', 'registration_count'),
                  (r'^\[\.4\] Dokumentbeskrivelse; Alle:\s*(\d+)', 'document_description_count'),
                  (r'^Dokumentobjekt; Alle:\s*(\d+)', 'document_object_count'),
                  (r'^\[\.5\] Korrespondansepart:\s*(\d+)', 'correspondence_party_count')],
}

# Multi-column lines in U1; individual matching restricted to precise prefixes.
U1_COMPOSITE = {
 'N5.10/12/14 Mapper:': {'Mapper':'folder_count', 'Sak':'case_folder_count', 'Møte':'meeting_folder_count'},
 'N5.16 Registreringer:': {'Registreringer':'registration_count', 'Journalpost':'journalpost_count'},
 'N5.23 Dokumentbeskrivelse:': {'Dokumentbeskrivelse':'document_description_count'},
 'N5.26.01 Dokumentobjekt:': {'Dokumentobjekt':'document_object_count'},
}
U2_SUBFIELDS = {
 '[.3] Registreringer;': {'Journalpost':'journalpost_count'},
 '[.2] Mappe typer:': {},
 'Dokumentobjekt;': {},
}
YEAR_BLOCKS = {
 'N5.11 Mapper pr. år:':'folders_by_creation_year',
 'N5.18 Registreringer pr. år (opprettet dato):':'registrations_by_creation_year',
 'N5.18 Journalposter pr. år (journaldato):':'journalposts_by_journal_year',
 'N5.53 Journalposter per år i løpende journal:':'running_journal_by_year',
 'N5.57 Journalposter per år i offentlig journal:':'public_journal_by_year',
 'N5.22.02 Journalposter pr. år (journaldato):':'journalposts_by_journal_year',
 'N5.61 Endringer i endringslogg:':'change_log_events_by_year',
}
# Other well-defined categories are preserved even when there is no DWM equivalent.
CONTEXT_SECTION = re.compile(r'^\s*(?:N5\.\d+[./\d]*\s+[^:]{1,90}:|\[\.\d\]\s+[^:]{1,90}:|\w[^:]{1,90}:)')
PART = re.compile(r'^Arkivdel\s+(\d+)\s*:\s*(.+)$', re.I)
YEAR = re.compile(r'^\s*((?:18|19|20|21)\d\d):\s*(\d+)\s*$')
PAIR = re.compile(r'([^;,\n]{1,95}?)\s*[:=]\s*(-?\d+)\b')


def _key(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', text.casefold()).strip('_')[:90]


def _source_lines(raw: str, report_type: str) -> list[str]:
    lines=raw.splitlines()
    if report_type in {'u01','u02'}:
        for i,line in enumerate(lines):
            if re.match(r'^U[12]\.\s*N5\.10[12]\b', line.strip()):
                return lines[i:]
    return lines


def extract_field_observations(raw_text: str, *, report_type: str,
                               legacy_job_id: str = '',
                               archive_part_index: int | None = None,
                               archive_part_title: str | None = None) -> list[dict[str, Any]]:
    """Return ALL nonempty result lines, each with exact semantic facts or raw value.

    'metric_id' non-null only for definition-backed, exact mappings.
    'source_context' keeps composite key names distinct across test sections.
    """
    result=[]
    context=''
    year_context=None
    part_index=archive_part_index
    part_title=archive_part_title
    legacy=(legacy_job_id or ('U01' if report_type=='u01' else 'U02' if report_type=='u02' else '')).upper()
    lines=_source_lines(raw_text,report_type)
    for line_num, raw in enumerate(lines,1):
        line=raw.strip()
        if not line: continue
        match=PART.match(line)
        if match and report_type=='u02':
            part_index=int(match.group(1));part_title=match.group(2).strip()
            context='';year_context=None
        new_context=next((v for k,v in YEAR_BLOCKS.items() if line.startswith(k)),None)
        if new_context:
            year_context=new_context
        elif line.startswith('Arkivdel ') or (line.startswith('N5.') and not new_context):
            year_context=None
        if CONTEXT_SECTION.match(line) and not YEAR.match(line):
            if not line.startswith('Arkivdel '):
                context=line.split(':',1)[0].strip()
        facts=[]
        seen=set()
        for pat,metric in MAIN.get((legacy,report_type),[]):
            m=re.search(pat,line,re.I)
            if m:
                facts.append({'metric_id':metric,'value':int(m.group(1)), 'label':FIELD_NAMES[metric],
                              'mapping_status':'exact','value_kind':'count'})
                seen.add((metric,int(m.group(1))))
        if report_type=='u01':
            for prefix, keys in U1_COMPOSITE.items():
                if not line.startswith(prefix):continue
                for label, metric in keys.items():
                    pattern=(r'^N5\.16 Registreringer:\s*(\d+)' if label=='Registreringer' else
                             r'^N5\.23 Dokumentbeskrivelse:\s*(\d+)' if label=='Dokumentbeskrivelse' else
                             r'^N5\.26\.01 Dokumentobjekt:\s*(\d+)' if label=='Dokumentobjekt' else
                             rf'\b{re.escape(label)}:\s*(\d+)')
                    m=re.search(pattern,line)
                    if m and (metric,int(m.group(1))) not in seen:
                        facts.append({'metric_id':metric,'value':int(m.group(1)),'label':FIELD_NAMES[metric],
                                      'mapping_status':'exact','value_kind':'count'})
                        seen.add((metric,int(m.group(1))))
        if report_type=='u02':
            if line.startswith('[.3] Registreringer;'):
                m=re.search(r'\bJournalpost:\s*(\d+)',line)
                if m: facts.append({'metric_id':'journalpost_count','value':int(m.group(1)),
                                    'label':'Journalposter','mapping_status':'exact','value_kind':'count'})
            if re.match(r'^saksmappe:\s*(\d+)',line,re.I):
                m=re.match(r'^saksmappe:\s*(\d+)',line,re.I)
                facts.append({'metric_id':'case_folder_count','value':int(m.group(1)),
                              'label':'Saksmapper','mapping_status':'exact','value_kind':'count'})
        year=YEAR.match(line)
        if year:
            facts.append({'metric_id':year_context,'value':int(year.group(2)),'year':int(year.group(1)),
                          'label':year_context or context or 'Årsverdi','mapping_status':'exact' if year_context else 'context_only',
                          'value_kind':'year_count'})
        else:
            for k,m in enumerate(PAIR.finditer(line),1):
                value=int(m.group(2)); label=m.group(1).strip()
                if not label or len(label)>85:continue
                # All numeric pairs are captured; the exact main-field mapping is
                # separate, not inferred from the English/Norwegian label alone.
                facts.append({'metric_id':None,'value':value,'label':label,'mapping_status':'context_only',
                              'value_kind':'labelled_count','context_key':f'{_key(context)}.{_key(label)}',
                              'pair_index':k})
        result.append({'line_number':line_num,'raw_text':raw,'source_context':context,
                       'archive_part_index':part_index,'archive_part_title':part_title,
                       'facts':facts})
    return result


def attach_semantic_facts(mapped: dict[str,Any]) -> dict[str,Any]:
    """Enrich a4.8 pool without removing historic raw observations or candidates."""
    n=0; exact=0
    for resource in mapped.get('resources') or []:
        semantic=extract_field_observations(str(resource.get('raw_text') or ''),
           report_type=str(resource.get('report_type') or ''),
           legacy_job_id=str(resource.get('legacy_test_id') or ''),
           archive_part_index=resource.get('archive_part_index'),
           archive_part_title=resource.get('archive_part_title'))
        for line in semantic:
            for fact in line['facts']:
                fact['source_line_number']=line['line_number']
                fact['source_context']=line['source_context']
                fact['archive_part_index']=line['archive_part_index']
                fact['archive_part_title']=line['archive_part_title']
                fact['source_resource_id']=resource.get('resource_id')
                fact['source_file']=resource.get('source_file')
                fact['source_sha256']=resource.get('source_sha256')
                n+=1
                exact+=(fact['mapping_status']=='exact')
        resource['semantic_lines']=semantic
    mapped['summary']['semantic_observations']=n
    mapped['summary']['exact_semantic_observations']=exact
    mapped['semantic_mapping_version']=2
    return mapped


def reconcile_semantic_observations(mapped: dict[str, Any]) -> dict[str, Any]:
    """Compare source metrics without silently selecting a winner.

    Multiple imports of different extractions must not be aggregated together.
    Results grouped per source_import_id; the operator owns job/source identity.
    """
    by_import={}
    for res in mapped.get('resources') or []:
        imp=str(res.get('import_id') or '')
        scope=by_import.setdefault(imp,{'whole':{},'parts':{},'source_files':set()})
        if res.get('source_file'):scope['source_files'].add(res['source_file'])
        for row in res.get('semantic_lines') or []:
            for fact in row.get('facts') or []:
                if fact.get('mapping_status')!='exact' or fact.get('value_kind')!='count':continue
                metric=fact['metric_id']
                part=fact.get('archive_part_index')
                target=(scope['parts'].setdefault(str(part),{}) if part is not None else scope['whole'])
                entry=target.setdefault(metric,[])
                entry.append({'value':fact['value'],'report_type':res.get('report_type'),
                              'source_file':res.get('source_file'),
                              'resource_id':res.get('resource_id'),
                              'line':fact.get('source_line_number')})
    output={}
    for imp,item in by_import.items():
        diffs=[]
        for metric,obs in item['whole'].items():
            values={o['value'] for o in obs}
            if len(values)>1:
                diffs.append({'metric_id':metric,'kind':'source_disagreement','observations':obs})
        for metric, obs in item['whole'].items():
            part_values=[]
            for part, metrics in item['parts'].items():
                vals={r['value'] for r in metrics.get(metric) or []}
                if len(vals)==1:part_values.append(next(iter(vals)))
            if part_values and len(part_values)==len(item['parts']):
                totals={o['value'] for o in obs}
                if len(totals)==1 and sum(part_values)!=next(iter(totals)):
                    diffs.append({'metric_id':metric,'kind':'parts_sum_mismatch',
                                  'whole':next(iter(totals)),'parts_sum':sum(part_values)})
        output[imp]={'source_files':sorted(item['source_files']), 'whole':item['whole'],
                     'archive_parts':item['parts'], 'conflicts':diffs}
    return {'import_groups':output,'note':'Source comparison; no changes to DWM authoritative results'}
