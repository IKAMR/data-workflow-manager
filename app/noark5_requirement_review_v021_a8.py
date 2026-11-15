"""A8: reviewable Noark 5 requirement candidates, source first and read only.

This is NOT an automatically approved normative requirements register.  A7
recorded numbered lexical snippets (some are dates/TOC references); A8 indexes
structured v3.1 XLSX rows and source-located v4/v5 PDF table candidates and
keeps all unreviewed citations separate from the six existing DWM requirements.
No XML, normative XSD, KDRS source, or original specification is modified.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable
from zipfile import ZipFile

from app.noark5_source_document_reader_v021_a7 import (
    M_ID, _xlsx_sections, read_source_document, diagnose_docx,
)

A7_REPORT_TYPE = 'noark5_a7_source_xsd_requirement_candidate_matrix_not_conformance'
REPORT_TYPE = 'noark5_a8_reviewable_requirement_evidence_not_conformance'
VERSIONS = ('3.1', '4.0', '5.0')
MAX_A7_REPORT_BYTES = 20_000_000
MAX_DOCUMENT_BYTES = 15_000_000
MAX_CANDIDATES = 12_000
MAX_CLAUSE_LENGTH = 4_000
MAX_OUTPUT_BYTES = 24_000_000
ID = re.compile(r'^\s*(\d{1,2}\.\d{1,2}\.\d{1,3})\s*$')
PDF_ROW = re.compile(r'^\s*(\d{1,2}\.\d{1,2}\.\d{1,3})\s+([^\s].+)$')
TOC_DOTS = re.compile(r'\.{5,}\s*\d*\s*$')
REQ_FILES = {
    '3.1': 'Noark5_v3.1_tabelloversikt_krav.xlsx',
    '4.0': 'Noark5v4 Standard for elektronisk arkiv (01.12.2016).pdf',
    '5.0': 'Noark 5 v 5.pdf',
}
OUTPUT_NAMES = (
    'noark5-a8-requirements.json', 'noark5-a8-requirements.csv',
    'noark5-a8-kdrs.csv', 'noark5-a8-docx-diagnostics.json',
    'noark5-a8-summary.md',
)


def _json(path: Path, *, limit: int = MAX_A7_REPORT_BYTES) -> dict[str, Any]:
    if path.stat().st_size > limit:
        raise ValueError('Inputrapporten overstiger størrelsesgrensen')
    obj = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(obj, dict):
        raise ValueError('Forventet JSON-objekt')
    return obj


def _source_doc_index(a7: dict) -> dict[tuple[str, str], dict]:
    return {(v, d['file']): d
            for v in VERSIONS for d in a7['versions'][v].get('documents', [])}


def _source_document(source_root: Path | None, a7: dict, version: str,
                     filename: str) -> tuple[Path | None, str, dict]:
    docs = [d for d in a7['versions'][version]['documents']
            if Path(str(d['file'])).name == filename]
    if len(docs) != 1:
        return None, 'document_not_uniquely_listed_in_a7', {}
    doc = docs[0]
    if source_root is None:
        return None, 'source_checkout_not_supplied', doc
    relative = Path(str(doc['file']))
    if relative.is_absolute() or '..' in relative.parts:
        return None, 'unsafe_source_path', doc
    root = (source_root / 'docs/kilder/noark').resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        return None, 'unsafe_source_path', doc
    if not path.is_file():
        return None, 'source_document_missing', doc
    if path.stat().st_size > MAX_DOCUMENT_BYTES:
        return None, 'source_document_too_large', doc
    digest = sha256(path.read_bytes()).hexdigest()
    expected = doc.get('manifest_sha256')
    if not expected or digest != expected:
        return None, 'source_sha256_mismatch', doc
    return path, 'identical_bytes', doc


def _record(version: str, number: str, *, origin: str, text: str,
            source: str, location: str, source_sha256: str | None,
            requirement_class: str = '', condition: str = '',
            original_length: int | None = None) -> dict:
    raw_text = text.strip()
    display = raw_text[:MAX_CLAUSE_LENGTH]
    mids = sorted(set(M_ID.findall(raw_text)))
    retired = bool(re.match(r'^utgår\b', raw_text, re.I))
    return {
        'candidate_id': f'{version}:{number}:{sha256((source+"|"+location+"|"+origin).encode("utf-8")).hexdigest()[:12]}',
        'noark_version': version, 'number': number, 'origin': origin,
        'source': source, 'location': location, 'source_sha256': source_sha256,
        'text': display, 'text_truncated': len(display) < len(raw_text),
        'original_text_length': original_length if original_length is not None else len(raw_text),
        'requirement_class': requirement_class, 'condition': condition[:MAX_CLAUSE_LENGTH],
        'metadata_ids_mentioned': mids, 'retired_text': retired,
        'source_wording_independently_reviewed': False,
        'normative_requirement_approved': False,
        'dwm_implementation_verified': False,
        'saxon_lxml_semantic_parity_verified': False,
        'qa_severity': 'NOTE' if retired else 'WARNING',
        'qa_reason': ('historical_retired_candidate_requires_review' if retired
                      else 'source_text_candidate_requires_manual_normative_review'),
    }


def _parse_xlsx_requirements(path: Path, version: str, doc: dict) -> list[dict]:
    """v3.1 numbered XLSX rows: respect actual row, class O/B/V and condition.

    Do not infer requirement type from surrounding text.  Never join a row to
    an adjacent row (continuations require QA, not silent repair).
    """
    with ZipFile(path) as archive:
        members = archive.infolist()
        if (sum(info.file_size for info in members) > 80_000_000 or
                len(members) > 20_000):
            raise ValueError('XLSX utpakket OOXML-innhold overskrider grensen')
    rows: list[dict] = []
    for location, raw in _xlsx_sections(path):
        cells = [x.strip() for x in raw.split(' | ')]
        if len(cells) < 2 or not ID.fullmatch(cells[0]):
            continue
        number = cells[0]
        text = cells[1]
        # The supplied table has requirement category O/B/V, sometimes followed
        # by mandatory/conditional notes.  Unknown categories stay empty.
        grade_positions = [i for i, cell in enumerate(cells[2:], start=2)
                           if cell.upper() in {'O', 'B', 'V'}]
        grade = cells[grade_positions[0]].upper() if grade_positions else ''
        condition = ' | '.join(cells[grade_positions[0] + 1:]) if grade_positions else ' | '.join(cells[2:])
        rows.append(_record(version, number, origin='xlsx_numbered_row',
                            text=text, source=doc['file'], location=location,
                            source_sha256=doc.get('manifest_sha256'),
                            requirement_class=grade, condition=condition))
    return rows


def _pdf_table_context(text: str) -> bool:
    window = text.casefold().replace('\n', ' ')
    return (('krav' in window and 'type' in window)
            or 'kravkrav' in window or 'krav nr.' in window)


def _parse_pdf_requirements(path: Path, version: str, doc: dict,
                            progress: Callable[[str], None] | None = None) -> tuple[list[dict], dict]:
    """Conservative line-level PDF candidates; NOT reconstructed clause wording.

    PDF columns can interleave on extraction.  Keep first line and page/line
    provenance, do not concatenate neighboring rows or claim category O/B/V.
    """
    sections, backend = read_source_document(path)
    result: list[dict] = []
    seen = set()
    page_count = len(sections)
    for p, (page, body) in enumerate(sections, 1):
        if progress and (p == 1 or p % 30 == 0 or p == page_count):
            progress(f'Noark {version}: leser kravtabell {p}/{page_count} ({backend})')
        context = _pdf_table_context(body)
        for line_index, line in enumerate(body.splitlines(), 1):
            match = PDF_ROW.match(line)
            if not match:
                continue
            number, text = match.group(1), match.group(2).strip()
            if len(text) < 16 or TOC_DOTS.search(text):
                continue
            # Avoid dates masquerading as numbered requirements. Such digits
            # remain visible in the A7 lexical candidate evidence instead.
            if re.match(r'^\d{2}\.\d{2}\.\d{2,4}$', number):
                continue
            key = (number, page, line_index)
            if key in seen:
                continue
            seen.add(key)
            record = _record(version, number, origin='pdf_numbered_line_candidate',
                             text=text, source=doc['file'],
                             location=f'{page}:line{line_index}',
                             source_sha256=doc.get('manifest_sha256'))
            record['pdf_table_header_on_page'] = context
            record['pdf_columns_and_wrapped_lines_not_reconstructed'] = True
            if not context:
                record['qa_reason'] = 'pdf_heading_or_clause_line_requires_manual_table_review'
            result.append(record)
            if len(result) >= MAX_CANDIDATES:
                return result, {'backend': backend, 'pages': page_count,
                                'candidate_limit_reached': True}
    return result, {'backend': backend, 'pages': page_count,
                    'candidate_limit_reached': False}


def _a7_lexical_candidates(a7: dict, already: set[tuple[str, str]]) -> list[dict]:
    """Keep number references/TOC/dates explicitly as unreviewed, not clauses."""
    out = []
    for key, refs in sorted(a7.get('numbered_document_text_candidates', {}).items()):
        if not isinstance(key, str) or ':' not in key or not isinstance(refs, list):
            continue
        version, number = key.split(':', 1)
        if version not in VERSIONS or not ID.fullmatch(number) or (version, number) in already:
            continue
        if not refs or not isinstance(refs[0], dict):
            continue
        item = refs[0]
        record = _record(version, number, origin='a7_lexical_number_only',
                         text=str(item.get('snippet') or ''),
                         source=str(item.get('source') or ''),
                         location=str(item.get('location') or ''),
                         source_sha256=item.get('source_sha256'))
        record['qa_reason'] = 'a7_lexical_number_may_be_toc_reference_or_date'
        record['full_requirement_wording_available'] = False
        out.append(record)
    return out


def _registered_requirements(a7: dict) -> list[dict]:
    out = []
    for version in VERSIONS:
        for row in a7['versions'][version]['requirement_rows']:
            rule = row.get('extract_validation') or {}
            candidate = {
                'candidate_id': f'{version}:dwm:{row["requirement_id"]}',
                'noark_version': version, 'number': None,
                'origin': 'existing_dwm_partial_requirements_registry',
                'registered_id': row['requirement_id'],
                'source': row.get('source_id'), 'location': row.get('source_location'),
                'source_sha256': None,
                'text': row.get('normative_summary') or '',
                'text_truncated': False, 'requirement_class': '',
                'metadata_ids_mentioned': [row['metadata_id']] if row.get('metadata_id') else [],
                'condition': '',
                'source_wording_independently_reviewed': bool(row.get('source_document_text_reviewed_for_rule')),
                'normative_requirement_approved': False,
                'dwm_implementation_verified': False,
                'extract_testable_registered': rule.get('directly_testable_from_extract'),
                'qa_severity': row.get('qa_severity', 'WARNING'),
                'qa_reason': row.get('qa_reason') or 'registered_rule_needs_independent_review',
            }
            out.append(candidate)
    return out


def _infer_scope_for_review(text: str) -> str:
    """Only triage candidates. Never turn heuristics into an executable rule."""
    t = text.casefold()
    extract_terms = ('arkivuttrekk', 'avleveringspakke', 'arkivstruktur.xml',
                     'endringslogg.xml', 'dokumentobjekt', 'sjekksum', 'xml-skjema',
                     'utf-8', 'addml', 'arkivperiode')
    functional_terms = ('skal kunne', 'bør kunne', 'tjeneste/funksjon',
                        'autoriserte brukere', 'systemet skal', 'ved opprettelse',
                        'ved søk', 'skal være mulig')
    if any(term in t for term in functional_terms):
        return 'candidate_system_functionality_not_proven_from_extract'
    if any(term in t for term in extract_terms):
        return 'candidate_extract_observation_requires_qa'
    return 'undetermined_requires_qa'


def _metadata_links(a7: dict) -> dict[tuple[str, str], list[str]]:
    return {(v, r['metadata_id']): list(r.get('xpath_lexical_test_ids') or [])
            for v in VERSIONS for r in a7['versions'][v]['metadata_rows']}


def _git_head(root: Path | None) -> str | None:
    if root is None or not (root / '.git').exists():
        return None
    try:
        proc = subprocess.run(['git','-C',str(root),'rev-parse','HEAD'],
                              capture_output=True,text=True,timeout=5,check=False)
    except (OSError,subprocess.TimeoutExpired):
        return None
    sha = proc.stdout.strip() if proc.returncode == 0 else ''
    return sha if re.fullmatch(r'[0-9a-f]{40}',sha) else None


def _source_integrity_issues(a7: dict, source_root: Path | None) -> list[dict]:
    issues = []
    if not a7.get('source_checkout_commit_verified'):
        issues.append({'severity': 'WARNING', 'kind': 'a7_source_revision_unverified'})
    if not a7.get('source_commit_matches_semantic_registry'):
        issues.append({'severity': 'WARNING', 'kind': 'a7_source_revision_mismatch'})
    for x in a7.get('source_xsd', []):
        if x.get('identity') not in ('identical_bytes', 'matches_original_after_restoring_crlf'):
            issues.append({'severity': 'FEIL', 'kind': 'a7_xsd_integrity_not_verified',
                           'source': x.get('file')})
    if source_root is None:
        issues.append({'severity': 'NOTE', 'kind': 'original_specification_files_not_reopened_in_a8'})
    return issues


def build_review(a7_report: dict, *, source_root: Path | str | None = None,
                 dwm_root: Path | str | None = None,
                 progress: Callable[[str], None] | None = None) -> dict:
    """Read-only; original source files need a local checkout for full candidates."""
    if a7_report.get('report_type') != A7_REPORT_TYPE:
        raise ValueError('Forventet rapport av typen Noark 5 a7 kravmatrise')
    if a7_report.get('source_files_modified') is not False:
        raise ValueError('Ukjent kildeendringsstatus i a7-rapporten')
    if not isinstance(a7_report.get('versions'), dict) or not all(
            version in a7_report['versions'] for version in VERSIONS):
        raise ValueError('A7 mangler én eller flere Noark-versjoner')
    source = Path(source_root).resolve() if source_root else None
    dwm = Path(dwm_root).resolve() if dwm_root else Path(__file__).resolve().parents[1]
    if source is not None and not source.is_dir():
        raise FileNotFoundError('Kilderepositoriet finnes ikke')
    if source is not None and (source == dwm or source in dwm.parents or dwm in source.parents):
        raise ValueError('DWM og kilderepositoriet må være separate')
    issues = _source_integrity_issues(a7_report, source)
    current_git_head = _git_head(source)
    if current_git_head and current_git_head != a7_report.get('source_checkout_commit'):
        issues.append({'severity':'WARNING','kind':'source_checkout_commit_changed_since_a7',
                       'source':'IKAMR/digital-archive-workflow'})
    elif source and current_git_head is None:
        issues.append({'severity':'NOTE','kind':'source_checkout_git_revision_unavailable_now'})
    candidates: list[dict] = []
    source_rows = {}
    for version in VERSIONS:
        filename = REQ_FILES[version]
        path, status, doc = _source_document(source, a7_report, version, filename)
        source_rows[version] = {'file': doc.get('file') or filename,
                                'sha256_identity': status, 'extraction_completed': False}
        if status != 'identical_bytes':
            issues.append({'severity': 'FEIL' if status in ('source_sha256_mismatch','unsafe_source_path')
                           else 'WARNING', 'kind': status, 'noark_version': version,
                           'source': doc.get('file') or filename})
            continue
        if progress:
            progress(f'Noark {version}: leser originalt kravgrunnlag {filename}')
        if version == '3.1':
            extracted = _parse_xlsx_requirements(path, version, doc)
            info = {'backend': 'xlsx_xml', 'candidate_limit_reached': False}
        else:
            extracted, info = _parse_pdf_requirements(path, version, doc, progress)
        source_rows[version].update(info)
        source_rows[version]['extraction_completed'] = True
        source_rows[version]['candidates'] = len(extracted)
        if info.get('candidate_limit_reached'):
            issues.append({'severity': 'WARNING', 'kind': 'candidate_limit_reached',
                           'noark_version': version, 'source': filename})
        candidates.extend(extracted)
    verified_by_number = {(c['noark_version'], c['number']) for c in candidates}
    lexical = _a7_lexical_candidates(a7_report, verified_by_number)
    candidates.extend(lexical)
    candidates.extend(_registered_requirements(a7_report))
    if len(candidates) > MAX_CANDIDATES:
        raise ValueError('Kravkandidater overstiger sikkerhetsgrensen')
    links = _metadata_links(a7_report)
    for row in candidates:
        mids = row.get('metadata_ids_mentioned') or []
        row['xpath_lexical_candidates'] = sorted(set(
            test_id for mid in mids for test_id in links.get((row['noark_version'],mid), [])))
        row['xpath_candidates_are_not_verified_controls'] = True
        row['triage_extract_scope_only'] = (_infer_scope_for_review(row.get('text',''))
            if row['origin'] != 'existing_dwm_partial_requirements_registry'
            else 'existing_dwm_rule_has_explicit_extract_testability')
    # Retain separate observations for duplicate/revised clauses; never merge.
    groups = defaultdict(list)
    for r in candidates:
        if r['origin'] != 'existing_dwm_partial_requirements_registry':
            groups[(r['noark_version'], r['number'])].append(r['candidate_id'])
    duplicate_groups = {f'{v}:{num}': ids for (v, num), ids in groups.items()
                        if len(ids) > 1}
    diagnostics = []
    if source is not None:
        for doc in a7_report['versions']['5.0']['documents']:
            if not str(doc.get('file','')).lower().endswith('.docx'):
                continue
            if doc.get('readable_sections'):
                continue
            rel = Path(doc['file'])
            root = (source / 'docs/kilder/noark').resolve()
            p = (root / rel).resolve()
            if not p.is_relative_to(root) or not p.is_file():
                diagnostics.append({'file':doc['file'], 'status':'source_file_unavailable'})
                continue
            if sha256(p.read_bytes()).hexdigest() != doc.get('manifest_sha256'):
                diagnostics.append({'file':doc['file'], 'status':'source_sha256_mismatch'})
                issues.append({'severity':'FEIL', 'kind':'docx_sha256_mismatch', 'source':doc['file']})
                continue
            diagnostics.append({'file':doc['file'], **diagnose_docx(p)})
    from app.noark5_kdrs_semantic_audit_v021_a8 import audit_implementation
    kdrs = audit_implementation(dwm)
    for issue in kdrs.get('issues', ()):
        issues.append(issue)
    per_version = {}
    for v in VERSIONS:
        vs = [r for r in candidates if r['noark_version'] == v]
        per_version[v] = {
            'source_candidates': sum(r['origin'] in ('xlsx_numbered_row', 'pdf_numbered_line_candidate') for r in vs),
            'a7_lexical_only': sum(r['origin']=='a7_lexical_number_only' for r in vs),
            'existing_dwm_registered': sum(r['origin']=='existing_dwm_partial_requirements_registry' for r in vs),
            'qa_counts': dict(Counter(r['qa_severity'] for r in vs)),
            'a7_xsd_metadata': a7_report['versions'][v]['xsd_metadata_types'],
            'a7_dwm_metadata_registered': a7_report['versions'][v]['registered_metadata'],
        }
    return {
        'report_format_version': 1, 'report_type': REPORT_TYPE,
        'source_repository': a7_report['source_repository'],
        'source_checkout_commit': a7_report.get('source_checkout_commit'),
        'source_checkout_commit_current':current_git_head,
        'source_checkout_commit_current_verified': bool(
            current_git_head and current_git_head == a7_report.get('source_checkout_commit')),
        'a7_report_sha256': None,  # filled by main() after reading input bytes
        'a7_report_verified_format': True,
        'original_source_checkout_supplied': source is not None,
        'source_data_modified': False, 'normative_requirements_approved': False,
        'static_extract_conformance_verified': False,
        'saxon_lxml_semantic_parity_verified': False,
        'source_tables': source_rows, 'versions': per_version,
        'candidate_rows': candidates, 'duplicate_number_groups': duplicate_groups,
        'docx_diagnostics': diagnostics, 'kdrs_audit': kdrs,
        'qa_issues': issues,
        'method': ('XLSX numbered row / PDF numbered line / A7 lexical reference / existing partial DWM registry. '
                   'All are distinct evidence types; no newly discovered requirement is approved.'),
    }


def filter_review_rows(report: dict, *, version: str = '', severity: str = '',
                       origin: str = '', query: str = '') -> list[dict]:
    if report.get('report_type') != REPORT_TYPE:
        raise ValueError('Ukjent a8-rapport')
    if version not in ('', *VERSIONS) or severity not in ('', 'FEIL', 'WARNING', 'NOTE'):
        raise ValueError('Ukjent Noark-versjon eller QA-status')
    rows = report.get('candidate_rows') or []
    result = []
    q = query.casefold().strip()
    for row in rows:
        if version and row['noark_version'] != version:
            continue
        if severity and row['qa_severity'] != severity:
            continue
        if origin and row['origin'] != origin:
            continue
        if q and not any(q in str(row.get(f) or '').casefold() for f in
                         ('number','registered_id','text','source','condition','origin')):
            continue
        result.append(row)
    return result


def _csv_safe(value: Any) -> str:
    """Prevent formula execution on CSV open; JSON contains exact source text."""
    result = '' if value is None else str(value)
    if result.lstrip().startswith(('=','+','-','@')):
        return "'" + result
    return result


def _csv(rows: list[dict], fields: tuple[str, ...]) -> str:
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({f:_csv_safe(', '.join(row[f]) if isinstance(row.get(f), list)
                                  else row.get(f,'')) for f in fields})
    return stream.getvalue()


def markdown_summary(report: dict) -> str:
    lines = ['# Noark 5: kildebasert krav- og KDRS-review (a8)', '',
        'Dette er et **QA-register med kildekandidater**, ikke verifisert normativ kravdekning.',
        f"Kilderevisjon (fra a7): `{report.get('source_checkout_commit') or 'ukjent'}`.", '',
        '| Versjon | XLSX-/PDF-kandidater | Bare a7-talltreff | Registrerte DWM-krav |',
        '| --- | ---: | ---: | ---: |']
    for v in VERSIONS:
        data = report['versions'][v]
        lines.append(f"| {v} | {data['source_candidates']} | {data['a7_lexical_only']} | "
                     f"{data['existing_dwm_registered']} |")
    k = report['kdrs_audit'].get('summary', {})
    lines += ['', f"KDRS-katalog: {k.get('catalog_tests',0)} tester, "
              f"{k.get('special_handler_tests',0)} spesialbehandlere; "
              f"{k.get('dispatch_missing',0)} mangler teknisk dispatch.",
              'Dispatch til en Python-funksjon er ikke bevis på Saxon-paritet.', '',
              '## QA-funn', '']
    for issue in report.get('qa_issues',[])[:80]:
        lines.append('- ' + str(issue.get('severity','WARNING')) + ': '
                     + str(issue.get('kind')) + ' – ' + str(issue.get('source') or issue.get('noark_version') or ''))
    lines += ['', '## Avgrensning', '',
        '- PDF-kolonner og linjebrudd er ikke automatisk rekonstruert til komplette krav.',
        '- Bokstaver O/B/V er registrert bare der de er egne kildeceller i XLSX.',
        '- Funksjonskrav kan ikke bevises gjennom et statisk uttrekk.',
        '- XPath-/M-ID-treff er ikke bevis på en implementert valideringsregel.',
        '- Ingen M300-normalisering eller semantiske aliaser er godkjent her.',
        '- Ingen XML, kildefiler eller normregistre er endret.', '']
    return '\n'.join(lines)


def write_reports(report: dict, output_dir: Path | str, *, source_root=None,
                  dwm_root=None) -> list[Path]:
    output = Path(output_dir).resolve()
    for folder in (source_root, dwm_root):
        if folder is None:
            continue
        root = Path(folder).resolve()
        if output == root or output.is_relative_to(root) or root.is_relative_to(output):
            raise ValueError('Resultatmappe må ligge utenfor både DWM og kilde-repo')
    files = [output / name for name in OUTPUT_NAMES]
    if any(p.exists() for p in files):
        raise FileExistsError('A8-rapporter finnes allerede; overskriving er sperret')
    compact = {key:value for key,value in report.items() if key != 'kdrs_audit'}
    compact['kdrs_audit'] = report['kdrs_audit']
    fields = ('noark_version','number','registered_id','origin','requirement_class',
              'text','condition','source','location','source_sha256','qa_severity',
              'qa_reason','triage_extract_scope_only','metadata_ids_mentioned',
              'xpath_lexical_candidates','source_wording_independently_reviewed')
    kdrs_fields = ('test_id','legacy_id','execution_kind','source_xml',
                   'special_handler','dispatch_verdict','original_source_status',
                   'a2_source_link_status','qa_severity','qa_reason')
    contents = [json.dumps(compact,ensure_ascii=False,indent=2)+'\n',
                _csv(report['candidate_rows'],fields),
                _csv(report['kdrs_audit'].get('tests',[]),kdrs_fields),
                json.dumps(report['docx_diagnostics'],ensure_ascii=False,indent=2)+'\n',
                markdown_summary(report)]
    if max(len(c.encode('utf-8')) for c in contents) > MAX_OUTPUT_BYTES:
        raise ValueError('A8-rapport overstiger sikkerhetsgrensen')
    output.mkdir(parents=True, exist_ok=True)
    for path, content in zip(files,contents):
        with path.open('x',encoding='utf-8',newline='') as handle:
            handle.write(content)
    return files


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--a7-report',type=Path,required=True,help='JSON fra a7-kildeanalysen')
    parser.add_argument('--source-root',type=Path,default=None,
                        help='Lokal utsjekking av digital-archive-workflow (full kildelesing)')
    parser.add_argument('--dwm-root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output-dir',type=Path,required=True,
                        help='Ny QA-mappe utenfor begge repoer')
    parser.add_argument('--quiet',action='store_true',help='Skjul leseframdrift')
    args=parser.parse_args(argv)
    try:
        a7=_json(args.a7_report)
        progress=None if args.quiet else lambda value: print(value,flush=True)
        report=build_review(a7,source_root=args.source_root,
                            dwm_root=args.dwm_root,progress=progress)
        report['a7_report_sha256']=sha256(args.a7_report.read_bytes()).hexdigest()
        paths=write_reports(report,args.output_dir,source_root=args.source_root,dwm_root=args.dwm_root)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        parser.error(str(exc))
    for p in paths:
        print(p)
    for v,row in report['versions'].items():
        print(f"Noark {v}: {row['source_candidates']} kildebaserte kandidater, "
              f"{row['a7_lexical_only']} rene talltreff, "
              f"{row['existing_dwm_registered']} eksisterende registrerte DWM-krav")
    print('Normativ kravdekning: IKKE godkjent. KDRS/Saxon-paritet: IKKE verifisert.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
