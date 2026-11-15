"""Read genuine KDRS Query 0.9 result text into a11's *provisional* comparison.

Supports full, clean and separately written (job_enabled=3) text outputs
produced by IKAMR/KDRS_Query Form1.writeResultsToFile / WriteSingleToFile.
The original text files are read-only. The source-file and XML hashes recorded
now DO NOT attest which bytes were used by the historical Saxon run.

Only a small, source-checked allowlist of direct count XPath metrics is parsed;
complex Standard/U1/U2 outputs remain opaque and explicitly unverified.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
from hashlib import sha256
import json
import ntpath
from pathlib import Path
import re
from typing import Any

from app.noark5_kdrs_parity_v021_a11 import compare, digest, read_json, write_report
from app.noark5_kdrs_u1u2_v021_a11 import map_u1, map_u2

REPORT_NAMES = (
    'noark5-a11-kdrs-import.json',
    'noark5-a11-kdrs-map.json',
    'noark5-a11-kdrs-inventory.csv',
    'noark5-a11-kdrs-import-summary.md',
)
MAX_REPORT_BYTES = 64_000_000
MAX_JOBS = 300
MAX_REPORTS = 8
MAX_QUERY_SOURCE_BYTES = 1_000_000
HEADER = re.compile(r'^Query file:\s*(.*)$', re.I)
SEPARATOR = re.compile(r'^={20,}\s*$')
JOB = re.compile(r'^[A-Za-z][A-Za-z0-9_.]*$')
SHA = re.compile(r'^[0-9a-f]{64}$')
PROFILES = {'STANDARD', 'U1', 'U2'}
STANDARD_VARIANTS = (
    'xml-queries_noark5_2026-05-26_no-journal.txt',
    'xml-queries_noark5_2026-05-26_no-offjournal.txt',
)
SOURCE_FILES = {
    'STANDARD': 'xml-queries_noark5_2026-05-26.txt',
    'U1': 'xml-queries_noark5_2026-05-26_U1.txt',
    'U2': 'xml-queries_noark5_2026-05-26_U2.txt',
}

# Each entry is deliberately narrow: KDRS label, DWM metric ID, and the XPath
# expression that must be present in BOTH reference definitions. String-similar
# metrics with different semantics (including namespace-dependent @xsi:type)
# are not automatically paired. These are still provisional runtime comparisons.
SIMPLE_COUNTS = {
    'C01': ('N5.04 Arkiv:', 'archive_count', 'count(//arkiv)'),
    'C02': ('N5.05/06 Arkivdeler:', 'archive_part_count', 'count(//arkivdel)'),
    'C05': ('N5.07 Klassifikasjonssystemer:', 'classification_system_count', 'count(//klassifikasjonssystem)'),
    'C07': ('N5.09 Klasser uten underklasser, mapper eller registreringer:', 'empty_class_count', 'count(//klasse[not(klasse or mappe or registrering)])'),
    'C08': ('N5.10 Mapper pr. type; Alle:', 'folder_count', 'count(//mappe)'),
    'C10': ('N5.12 Klasser med både mappe og underklasse (>0 er avvik):', 'class_with_subclass_and_folder', 'count(//klasse[klasse]/mappe)'),
    'C12': ('N5.14 Mapper uten undermapper eller registreringer:', 'folder_without_content', 'count(//mappe[not(mappe or registrering)])'),
    'C13': ('N5.15 Saksmapper pr. status; Alle:', 'folder_count', 'count(//mappe)'),
    'C14': ('N5.16 Registreringer pr. type; Alle:', 'registration_count', 'count(//registrering)'),
    'C19': ('N5.21 Registreringer uten dokumentbeskrivelse:', 'registration_without_document_description', 'count(//registrering[not(dokumentbeskrivelse)]/registreringsID)'),
    'C21': ('N5.23 Dokumentbeskrivelser pr. type; Alle:', 'document_description_count', 'count(//dokumentbeskrivelse)'),
    'C22': ('N5.24 Dokumentbeskrivelser uten dokumentobjekt:', 'without_object_count', 'count(//dokumentbeskrivelse[not(dokumentobjekt)])'),
    'C23': ('N5.25 Dokumentbeskrivelser pr. status; Alle:', 'document_description_count', 'count(//dokumentbeskrivelse)'),
    'C24': ('N5.26 Dokumentobjekt og variantformat:', 'document_object_count', 'count(//dokumentobjekt)'),
    'F01': ('M5.35 Sakspart (Noark 5 v3.1/4.0):', 'sakspart_count_v31_v40', 'count(//sakspart)'),
    'F02': ('N5.36 Merknader pr. type tilknyttet; Alle:', 'note_count', 'count(//merknad)'),
    'F03': ('N5.37 Kryssreferanser pr. type tilknyttet:', 'cross_reference_children', 'count(//kryssreferanse/*)'),
    'F04': ('N5.38 Presedenser pr. type tilknyttet:', 'precedent_count', 'count(//presedens)'),
    'F05': ('N5.39 Korrespondanseparter; Alle:', 'correspondence_party_count', 'count(//korrespondansepart)'),
    'F07': ('N5.41 Dokumentflyter; Alle:', 'document_flow_count', 'count(//registrering/dokumentflyt)'),
    'F08': ('N5.42 Skjerminger; Alle:', 'screening_count', 'count(//skjerming)'),
    'F10': ('N5.44 Kassasjonsvedtak; Alle:', 'disposal_decision_count', 'count(//kassasjon)'),
    'F11': ('N5.45 Utførte kassasjoner; Alle:', 'performed_disposal_count', 'count(//utfoertKassasjon)'),
    'F12': ('N5.46 Konverterte dokumenter:', 'conversion_count', 'count(//konvertering)'),
    'F13': ('Utførte slettinger utenom kassasjon:', 'deletion_count', 'count(//sletting)'),
    'H01': ('N5.52 Journalregistreringer i loependeJournal:', 'journal_registration_count', 'count(//journalregistrering)'),
    'H04': ('N5.55 Skjermede journalposter i løpendeJournal:', 'screened_journal_registration_count', 'count(//journalregistrering[journalpost[tilgangsrestriksjon]])'),
    'H05': ('N5.56 Journalregistreringer i offentligJournal:', 'journal_registration_count', 'count(//journalregistrering)'),
    'J01': ('N5.61 Endringer i endringslogg:', 'change_count', 'count(//endring)'),
}


@dataclass(frozen=True)
class TextJob:
    job_id: str
    raw_result: str
    verbose: bool
    embedded_query: str | None


def _source_name(s: str) -> str:
    return ntpath.basename(s.strip().replace('/', '\\'))


def _read_utf8(path: Path, limit: int) -> str:
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError(f'KDRS-kildefil mangler/overstiger grensen: {path}')
    return path.read_text(encoding='utf-8-sig')


def _read_report(path: Path) -> tuple[str, list[TextJob]]:
    """Parse the exact delimiter/record layout written by KDRS Query 0.9.

    Does not interpret strings inside Saxon results as new jobs. Rejects broken
    separators, ambiguous duplicates and missing the original report header.
    """
    text = _read_utf8(path, MAX_REPORT_BYTES)
    lines = text.splitlines()
    if not lines:
        raise ValueError(f'Tom KDRS-rapport: {path}')
    match = HEADER.match(lines[0].lstrip('\ufeff'))
    if not match or not match.group(1).strip():
        raise ValueError('KDRS-rapport må starte med Query file: <query-file>')
    header_name = _source_name(match.group(1))
    if not any(SEPARATOR.fullmatch(line.strip()) for line in lines[1:]):
        raise ValueError('KDRS-rapport mangler original seksjonsskilletegn')
    sections = []
    current = []
    seen_start = False
    for line in lines[1:]:
        if SEPARATOR.fullmatch(line.strip()):
            if seen_start and any(x.strip() for x in current):
                sections.append(current)
            current = []
            seen_start = True
        elif seen_start:
            current.append(line)
        elif line.strip():
            raise ValueError('Ukjent innhold før første KDRS-seksjon')
    if any(x.strip() for x in current):
        raise ValueError('Uavsluttet KDRS-jobbseksjon')
    jobs = []
    known = set()
    for section in sections:
        while section and not section[0].strip():
            section = section[1:]
        while section and not section[-1].strip():
            section = section[:-1]
        if not section or not JOB.fullmatch(section[0].strip()):
            raise ValueError('Ugyldig KDRS-jobb-ID i tekstfil')
        job_id = section[0].strip()
        if job_id in known:
            raise ValueError(f'Duplisert KDRS-jobb i rapport: {job_id}')
        known.add(job_id)
        if len(known) > MAX_JOBS:
            raise ValueError('For mange KDRS-jobber i tekstfil')
        # Full output has status (0..3), query metadata, then Query result:.
        # Clean output consists of job ID, an empty line and the raw result.
        content = section[1:]
        verbose = bool(content and content[0].strip() in {'0','1','2','3'})
        if verbose:
            markers = [i for i, value in enumerate(content) if value.strip() == 'Query result:']
            if len(markers) != 1:
                raise ValueError(f'KDRS fullformat uten entydig Query result: {job_id}')
            pos = markers[0]
            if pos < 4:
                raise ValueError(f'KDRS fullformat med manglende metadata: {job_id}')
            query = '\n'.join(content[7:pos]).strip() if pos > 7 else None
            raw = '\n'.join(content[pos+1:]).strip('\n')
        else:
            query = None
            raw = '\n'.join(content).strip('\n')
        jobs.append(TextJob(job_id, raw.strip(), verbose, query))
    if not jobs:
        raise ValueError('KDRS-rapporten inneholder ingen jobbseksjoner')
    return header_name, jobs


def _source_jobs(text: str) -> dict[str, dict[str, str]]:
    out = {}
    for part in text.split('[XML_QUERY]')[1:]:
        id_match = re.search(r'^job_id\s*=\s*([^\s]+)', part, re.M)
        expr_match = re.search(r'#START#(.*?)#STOP#', part, re.S)
        xml_match = re.search(r'^source\s*=\s*(\S+)', part, re.M)
        if id_match and expr_match and xml_match:
            job = id_match.group(1).strip()
            if job in out:
                raise ValueError(f'Duplisert KDRS-definisjon: {job}')
            out[job] = {'expression': expr_match.group(1).strip(), 'source_xml': xml_match.group(1).strip()}
    return out


def _norm_xpath(expr: str) -> str:
    """Narrow whitespace/quote normalization for the supported count subset."""
    return re.sub(r'\s+', '', expr).replace('"', "'")


def _source_contains_expression(source_body: str, expression: str) -> bool:
    return _norm_xpath(expression) in _norm_xpath(source_body)


def _metric_expression(test: dict, metric_id: str) -> str | None:
    matches = [m.get('expression') for m in test.get('execution', {}).get('metrics', [])
               if isinstance(m, dict) and m.get('id') == metric_id and m.get('type') == 'xpath']
    return matches[0] if len(matches) == 1 and isinstance(matches[0], str) else None


def _parse_count(raw: str, label: str) -> tuple[int | None, str]:
    if raw.startswith('ERROR 1, unable to compile:') or raw.startswith('ERROR '):
        return None, 'kdrs_query_failed'
    # A full result can be a Saxon sequence: a count may be followed by rows.
    # Restrict to explicit labels and a standalone unsigned integer value.
    label_pattern = re.escape(label).replace(r'\ ', r'[ \t]+')
    pattern = re.compile(r'(?<!\w)' + label_pattern + r'[ \t]*(\d+)(?![\w.])')
    numbers = pattern.findall(raw)
    if len(numbers) != 1:
        return None, 'label_missing_or_ambiguous'
    # Reject huge untrusted digit strings before int() (Python can raise for
    # >4300 digits, and even smaller values exceed a 64-bit count here).
    if len(numbers[0]) > 19:
        return None, 'count_out_of_range'
    value = int(numbers[0])
    if value > 2**63 - 1:
        return None, 'count_out_of_range'
    return value, ''


def _csv_safe(value: Any) -> str:
    text = str(value or '')
    if text and text[0] in '=+-@':
        return "'" + text
    return text


def _rel_report(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace('\\', '/')
    except ValueError:
        return str(path.resolve())


def build_import(*, dwm_root: Path, xml_root: Path,
                 reports: dict[str, Path], noark_version: str,
                 dwm_index_path: Path | None = None) -> tuple[dict, dict, list[dict]]:
    """Source-check count witnesses and create a11-compatible export + map.

    The report's Query file: header proves only a *claimed* source basename.
    XML is hashed after the fact; this cannot attest historical KDRS input.
    """
    if not reports or len(reports) > MAX_REPORTS or any(p not in PROFILES for p in reports):
        raise ValueError('Bruk opptil ett KDRS-resultat per STANDARD, U1 og U2')
    if noark_version not in ('3.1','4.0','5.0'):
        raise ValueError('Ukjent Noark-versjon')
    root = dwm_root.resolve()
    catalog = read_json(root/'config/noark5/tests/xpath_catalog_2026_05_26.json')
    catalog_tests = catalog.get('tests')
    if not isinstance(catalog_tests, list):
        raise ValueError('DWM-katalog mangler tester')
    by_legacy = {}
    for t in catalog_tests:
        if not isinstance(t, dict):
            raise ValueError('Ugyldig katalograd')
        legacy = t.get('legacy') or {}
        jid = legacy.get('job_id')
        if not isinstance(jid, str) or jid in by_legacy:
            raise ValueError('Ugyldig/duplisert legacy-ID i DWM-katalog')
        by_legacy[jid] = t

    source_by_profile = {}
    source_hashes = {}
    standard_variant_sources = {}
    for profile, basename in SOURCE_FILES.items():
        ref = root/'docs/reference/kdrs-query'/basename
        source_text = _read_utf8(ref, MAX_QUERY_SOURCE_BYTES)
        source_by_profile[profile] = _source_jobs(source_text)
        source_hashes[basename] = digest(ref)
    for basename in STANDARD_VARIANTS:
        ref = root/'docs/reference/kdrs-query'/basename
        if ref.is_file():
            variant_text = _read_utf8(ref, MAX_QUERY_SOURCE_BYTES)
            standard_variant_sources[basename] = _source_jobs(variant_text)
            source_hashes[basename] = digest(ref)
    index = []
    jobs = {}
    used_sources = set()
    issues = []
    candidates = []
    for profile, report in sorted(reports.items()):
        query_basename, parsed = _read_report(report)
        valid_headers = {SOURCE_FILES[profile]}
        if profile == 'STANDARD':
            valid_headers.update(standard_variant_sources)
        else:
            valid_headers.add(SOURCE_FILES['STANDARD'])
            valid_headers.update(standard_variant_sources)
        header_ok = query_basename in valid_headers
        report_sha = digest(report)
        for j in parsed:
            if j.job_id in jobs:
                raise ValueError(f'Samme KDRS-jobb forekommer i flere rapporter: {j.job_id}')
            test = by_legacy.get(j.job_id)
            if profile == 'STANDARD' and query_basename in standard_variant_sources:
                source = standard_variant_sources[query_basename].get(j.job_id)
            else:
                source = source_by_profile[profile].get(j.job_id)
            if source is None or test is None:
                raise ValueError(f'KDRS-jobb finnes ikke i DWM/original {profile}: {j.job_id}')
            source_xml = source['source_xml']
            if source_xml != test.get('source_xml'):
                raise ValueError(f'Ulik kilde-XML i DWM/KDRS for {j.job_id}')
            # In a verbose file, the embedded query is a stronger source witness,
            # but still not proof of the file's historical contents or execution.
            verified_embedded = (j.embedded_query is not None and
                                 _norm_xpath(j.embedded_query) == _norm_xpath(source['expression']))
            if j.embedded_query is not None and not verified_embedded:
                issues.append({'kind':'embedded_query_differs_from_reference', 'job_id':j.job_id,
                               'profile':profile})
            if not header_ok:
                issues.append({'kind':'historical_query_source_basename_unknown',
                               'job_id':j.job_id, 'profile':profile,
                               'query_file_basename':query_basename})
            used_sources.add(source_xml)
            raw_sha = sha256(j.raw_result.encode('utf-8')).hexdigest()
            entry = {'metrics':{}, 'raw_result_sha256':raw_sha,
                     'raw_result_characters':len(j.raw_result),
                     'raw_result_lines':j.raw_result.count('\n')+1,
                     'source_report':str(report), 'source_report_sha256':report_sha,
                     'source_profile':profile, 'source_xml':source_xml,
                     'query_file_basename':query_basename,
                     'query_file_basename_recognized':header_ok,
                     'embedded_query_matches_reference':verified_embedded if j.verbose else None,
                     'runtime_execution_attested':False}
            jobs[j.job_id] = entry
            status = 'OPAQUE_NOT_MAPPED'
            reason = 'complex_result_or_no_approved_metric_mapping'
            config = SIMPLE_COUNTS.get(j.job_id)
            if config is not None and profile == 'STANDARD':
                label, metric, expression = config
                dwm_expr = _metric_expression(test,metric)
                source_ok = _source_contains_expression(source['expression'],expression)
                dwm_ok = dwm_expr is not None and _norm_xpath(dwm_expr)==_norm_xpath(expression)
                source_claim_ok = header_ok and (not j.verbose or verified_embedded)
                if not source_ok or not dwm_ok:
                    status, reason = 'NOT_MAPPED', 'kdrs_or_dwm_xpath_witness_mismatch'
                    issues.append({'kind':reason,'job_id':j.job_id,'profile':profile})
                elif not source_claim_ok:
                    status, reason = 'NOT_MAPPED', 'kdrs_source_not_identified'
                else:
                    count, why = _parse_count(j.raw_result,label)
                    if count is None:
                        status, reason = 'NOT_MAPPED', why
                        issues.append({'kind':why,'job_id':j.job_id,'profile':profile})
                    else:
                        candidates.append({'job_id':j.job_id,'test_id':test['test_id'],
                                           'profile':'STANDARD',
                                           'kdrs_path':f'metrics.{metric}','dwm_path':metric})
                        jobs[j.job_id]['metrics'][metric] = count
                        status, reason = 'COUNT_CANDIDATE_PROVISIONAL', ''
            elif profile in {'U1', 'U2'}:
                # U1/U2 mappings are opt-in only when the source profile and
                # any embedded full-format XPath have been checked. For U2,
                # a real DWM U02 result is mandatory to corroborate ordered
                # archive-part identities; titles alone do not suffice.
                source_claim_ok = header_ok and (not j.verbose or verified_embedded)
                if not source_claim_ok:
                    status, reason = 'NOT_MAPPED', 'kdrs_source_not_identified'
                elif profile == 'U1':
                    values, additional, qa = map_u1(j.raw_result, source['expression'], test, _parse_count)
                    jobs[j.job_id]['metrics'].update(values)
                    candidates.extend(additional)
                    issues.extend({'profile':profile, 'job_id':j.job_id, **item} for item in qa)
                    if additional:
                        status, reason = 'U1_METRICS_PROVISIONAL', ''
                    else:
                        status, reason = 'OPAQUE_NOT_MAPPED', 'u1_no_source_witnessed_counts'
                else:
                    values, additional, qa = map_u2(j.raw_result, source['expression'], test,
                                                    dwm_index_path, _parse_count)
                    jobs[j.job_id]['metrics'].update(values)
                    if len(candidates) + len(additional) > 20000:
                        status, reason = 'NOT_MAPPED', 'u2_comparison_limit_exceeded'
                        jobs[j.job_id]['metrics'] = {}
                        issues.append({'kind':reason, 'profile':profile, 'job_id':j.job_id})
                    else:
                        candidates.extend(additional)
                        issues.extend({'profile':profile, 'job_id':j.job_id, **item} for item in qa)
                        if additional:
                            status, reason = 'U2_ARCHIVE_PART_METRICS_PROVISIONAL', ''
                        else:
                            status, reason = 'OPAQUE_NOT_MAPPED', (qa[0]['kind'] if qa else
                                                                'u2_requires_dwm_result_index')
            index.append({'profile':profile,'job_id':j.job_id,'test_id':test['test_id'],
                          'source_xml':source_xml,'source_report':str(report),
                          'text_format':'full' if j.verbose else 'clean',
                          'query_file_basename':query_basename,
                          'result_raw_sha256':raw_sha,'mapping_status':status,'reason':reason,
                          'mapped_metric_rows':sum(c['job_id']==j.job_id for c in candidates)})

    # Hash only known XML inputs in the provided extraction root. Missing
    # optional XML files are not invented as empty files or successful runs.
    hashes = {}
    missing_sources = []
    for name in sorted(used_sources):
        if Path(name).name != name or Path(name).suffix.lower() != '.xml':
            raise ValueError('KDRS oppgir utrygt XML-filnavn')
        p = (xml_root.resolve()/name).resolve()
        if not p.is_relative_to(xml_root.resolve()):
            raise ValueError('KDRS-kilde peker utenfor uttrekket')
        if p.is_file():
            hashes[name] = digest(p)
        else:
            missing_sources.append(name)
            issues.append({'kind':'xml_file_missing_at_import','source_xml':name})

    legacy = {'format_version':1,'engine':'Saxon','noark_version':noark_version,
              'xml_sha256':hashes,'jobs':jobs,
              'run_identity':'POSTHOC_UNATTESTED',
              'runtime_saxon_engine_attested':False,
              'runtime_input_bytes_attested':False,
              'provenance_note':('KDRS Query kildekode bruker Saxon.Api. Tekstrapport og '
                 'ny SHA-256 av XML verifiserer ikke historisk motor eller input.') ,
              'kdrs_reference_source_sha256':source_hashes,
              'kdrs_reports_sha256':{profile:digest(path) for profile,path in reports.items()},
              'missing_xml_at_import':missing_sources,
              'import_issues':issues}
    mapping = {'format_version':1,'scope':'partial',
               'mapping_role':'curated_exact_count_xpath_candidates_not_full_parity',
               'comparisons':candidates}
    return legacy, mapping, index


def write_import(legacy: dict, mapping: dict, inventory: list[dict], output_dir: Path) -> list[Path]:
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError('Utdata må være mappe')
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = [output_dir / name for name in REPORT_NAMES]
    if any(p.exists() for p in paths):
        raise FileExistsError('a11-import finnes; velg en ny mappe')
    paths[0].write_text(json.dumps(legacy,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    paths[1].write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with paths[2].open('w',encoding='utf-8',newline='') as f:
        fields=['profile','job_id','test_id','source_xml','text_format','mapping_status',
                'mapped_metric_rows','reason','query_file_basename','source_report',
                'result_raw_sha256']
        writer = csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        for row in inventory:
            writer.writerow({k:_csv_safe(row.get(k,'')) for k in fields})
    statuses = Counter(r['mapping_status'] for r in inventory)
    lines = [
        '# Noark 5 a11.3 – KDRS-tekstimport', '',
        f"Importerte historiske KDRS-jobbresultater: **{len(inventory)}**.",
        f"Standard-jobber med enkle tellekandidater: **{statuses['COUNT_CANDIDATE_PROVISIONAL']}**.",
        f"U1-jobber med parsede telleverdier: **{statuses['U1_METRICS_PROVISIONAL']}**.",
        f"U2-jobber med arkivdelsverifiserte telleverdier: **{statuses['U2_ARCHIVE_PART_METRICS_PROVISIONAL']}**.",
        f"Opaque/ikke kartlagt eller avvist: **{sum(r['mapped_metric_rows']==0 for r in inventory)}**.",
        f"Deklarerte sammenligningsrader: **{len(mapping['comparisons'])}**.",
        '',
        '**Ingen historisk Saxon-kjøring eller XML-byteidentitet er attestert.**',
        'U2-identitet er sjekket mot DWM-indeks ved import, men ikke mot historisk Saxon XML.',
        'Selv om enkle tall stemmer, er Saxon/lxml-paritet og normativ dekning ikke verifisert.',
        f"KDRS-kildeversjon: registrert {len(legacy['kdrs_reference_source_sha256'])} referansefiler med SHA-256.",
        f"Manglende XML ved import: {', '.join(legacy['missing_xml_at_import']) or 'ingen'}.",
        f"Registrerte kilde-/parser-QA-punkter: {len(legacy['import_issues'])}.",
    ]
    paths[3].write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='a11: import av ekte KDRS Query-tekstutdata')
    parser.add_argument('--dwm-root',required=True,type=Path)
    parser.add_argument('--xml-root',required=True,type=Path)
    parser.add_argument('--report',action='append',required=True,
                        metavar='STANDARD|U1|U2=STI',
                        help='KDRS Query tekstutdata, kan gjentas for Standard, U1, U2')
    parser.add_argument('--noark-version',required=True,choices=('3.1','4.0','5.0'))
    parser.add_argument('--dwm-index',type=Path)
    parser.add_argument('--output-dir',required=True,type=Path)
    args = parser.parse_args(argv)
    reports = {}
    for spec in args.report:
        name, sep, path = spec.partition('=')
        if not sep or name not in PROFILES or not path:
            parser.error('--report må skrives STANDARD=sti, U1=sti eller U2=sti')
        if name in reports:
            parser.error('Duplikat --report-profil')
        reports[name] = Path(path)
    if args.output_dir.resolve().is_relative_to(args.dwm_root.resolve()) or \
       args.output_dir.resolve().is_relative_to(args.xml_root.resolve()):
        parser.error('--output-dir må ligge utenfor DWM-repo og Source')
    if any(args.output_dir.resolve().is_relative_to(path.resolve().parent)
           for path in reports.values()):
        parser.error('--output-dir kan ikke ligge i mappen med originale KDRS-resultater')
    legacy, mapping, inventory = build_import(
        dwm_root=args.dwm_root, xml_root=args.xml_root,
        reports=reports, noark_version=args.noark_version,
        dwm_index_path=args.dwm_index)
    written = write_import(legacy,mapping,inventory,args.output_dir)
    for path in written:
        print(path)
    if args.dwm_index:
        report = compare(args.dwm_index, written[0], written[1], args.xml_root)
        write_report(report,args.output_dir)
        for name in ('noark5-a11-parity.json','noark5-a11-parity.csv','noark5-a11-summary.md'):
            print(args.output_dir/name)
        print('Foreløpig sammenligning:', report['summary'])
    print('KDRS jobbresultater:',len(inventory), 'enkle kandidater:',
          len([x for x in inventory if x['mapping_status']=='COUNT_CANDIDATE_PROVISIONAL']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
