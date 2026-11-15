"""a9: source-bound, reviewable Noark 5 requirement clauses from DOCX/XLSX.

Read-only examination of local IKAMR/digital-archive-workflow checkout:
* v3.1: XLSX requirement table is primary; DOCX is cross-check evidence.
* v4.0/v5.0: main DOCX is primary *transcription*, matched to the source PDF.
* Source integrity, duplicate IDs, unreadable documents and uncertain table rows
  are surfaced as FEIL/WARNING/NOTE and NEVER silently approved.

A fully captured DOCX table cell is not necessarily a complete or faithful
transcription of the original PDF. Normative review and DWM test coverage remain
separate tasks. No sources, XSD files or XPath definitions are modified.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from difflib import SequenceMatcher
from hashlib import sha1, sha256
import io
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable
from zipfile import ZipFile

from app.noark5_requirement_review_v021_a8 import (
    REPORT_TYPE as A8_REPORT_TYPE, _csv_safe,
)
from app.noark5_source_document_reader_v021_a7 import (
    M_ID, _xlsx_sections, read_docx_structured, MAX_DOCX_BYTES,
)

REPORT_TYPE = 'noark5_a9_docx_clause_registry_unapproved_not_conformance'
VERSIONS = ('3.1', '4.0', '5.0')
DOCX_MAIN = {
    '3.1': 'Noark5_v3.1_standarden.docx',
    '4.0': 'Noark5v4 Standard for elektronisk arkiv (01.12.2016).docx',
    '5.0': 'Noark 5 v 5.docx',
}
XLSX_31 = 'Noark5_v3.1_tabelloversikt_krav.xlsx'
REPORT_NAMES = (
    'noark5-a9-requirements.json', 'noark5-a9-requirements.csv',
    'noark5-a9-source-inventory.json', 'noark5-a9-unresolved.csv',
    'noark5-a9-summary.md',
)
MAX_REPORT_INPUT_BYTES = 24_000_000
MAX_MANIFEST_BYTES = 8_000_000
MAX_OUTPUT_BYTES = 80_000_000
MAX_DOCUMENTS = 40
MAX_CLAUSES = 16_000
MAX_CLAUSE_CHARS = 24_000
DEFAULT_DOCX_SIGNATURES = (Path(__file__).resolve().parents[1] /
    'config/noark5/standards/noark5_docx_signatures_v021_a9.json')
NUM = re.compile(r'^\s*(\d{1,2}\.\d{1,2}\.\d{1,3})\s*$')
NUMBERED_START = re.compile(r'^\s*(\d{1,2}\.\d{1,2}\.\d{1,3})\s+(.{25,})', re.S)
TYPES = {'O', 'B', 'V'}
TOC_LEADER = re.compile(r'(?:\.{5,}|…{3,}).*\d+\s*$')
WORD_REQUIREMENT_PREFIX = re.compile(
    r'^\s*(?:(?P<prefix>Krav(?:\s+nr\.?)?|Kravnummer|Nr\.?)\s*[:#-]?\s*)?'
    r'(?P<number>\d{1,2}\.\d{1,2}\.\d{1,3})'
    r'(?=$|\s|[:;,.-])(?P<tail>[\s\S]*)$', re.I)
NOT_A_REQUIREMENT_PREFIX = re.compile(r'^\s*(?:se|tidligere|jf\.?|jfr\.?)\s+krav\b',re.I)
REQUIREMENT_MODAL = re.compile(r'\b(?:skal|bør|må)\b',re.I)
HEADING_STYLE = re.compile(r'(?:heading|overskrift|toc|innhold)',re.I)
TRUE_HEADING_STYLE = re.compile(r'(?:heading|overskrift)', re.I)
TOC_STYLE = re.compile(r'(?:^toc|innhold|table.?of.?contents)', re.I)
LITERAL_SECTION_HEADING = re.compile(
    r'^\s*(\d{1,2}(?:\.\d{1,2}){0,2})\s+([^\t\n]{3,150})\s*$')
TOC_PAGE_ENDING = re.compile(r'\t\s*\d{1,4}\s*$')


def _reliable_heading_context(text: str, style: str, generated: str) -> str | None:
    """Track real chapter context; never promote a TOC page reference.

    Original Word standards often use generated numbering for Heading styles.
    When a context cannot be established, leave it blank rather than labeling
    unrelated requirements with the final table-of-contents heading.
    """
    if not text or TOC_STYLE.search(style) or TOC_PAGE_ENDING.search(text):
        return None
    literal = LITERAL_SECTION_HEADING.fullmatch(text)
    is_heading_style = bool(TRUE_HEADING_STYLE.search(style))
    if is_heading_style:
        if literal:
            return text.strip()
        if re.fullmatch(r'\d{1,2}(?:\.\d{1,2}){0,2}', generated):
            return (generated + ' ' + text.strip())[:220]
        return text.strip()[:220] if len(text) <= 220 else None
    # Non-heading style: accept only short, literal chapter/subchapter titles.
    # Three-part numerals plus normative prose are almost always requirement
    # clauses, not headings. They must not overwrite prior heading context.
    if literal and literal.group(1).count('.') <= 1 and \
            not REQUIREMENT_MODAL.search(literal.group(2)):
        return text.strip()
    return None


def _read_json(path: Path, limit: int) -> dict:
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError('Manglende eller for stor inngangsfil: ' + str(path))
    obj = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(obj, dict):
        raise ValueError('Forventet JSON-objekt: ' + str(path))
    return obj


def _git_commit(path: Path) -> str | None:
    if not (path / '.git').exists():
        return None
    try:
        result = subprocess.run(['git','-C',str(path),'rev-parse','HEAD'],
                                timeout=5, text=True, capture_output=True, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    sha = result.stdout.strip()
    return sha if result.returncode == 0 and re.fullmatch('[a-f0-9]{40}',sha) else None


def _digest(path: Path, limit: int = MAX_DOCX_BYTES) -> str:
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError(str(path))
    if path.stat().st_size > limit:
        raise ValueError('Kildefil overstiger størrelsesgrensen: ' + str(path))
    h = sha256()
    with path.open('rb') as source:
        for part in iter(lambda: source.read(1_048_576), b''):
            h.update(part)
    return h.hexdigest()


def _git_blob_sha1(path: Path) -> str:
    """Git blob identity, including the byte-size header (not raw SHA-1)."""
    n=path.stat().st_size
    h=sha1(f'blob {n}\0'.encode('ascii'))
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1_048_576), b''):
            h.update(block)
    return h.hexdigest()


def _load_docx_signatures(path: Path) -> tuple[dict[str,str],str]:
    document=_read_json(path,200_000)
    if document.get('source_repository')!='IKAMR/digital-archive-workflow':
        raise ValueError('Ukjent signaturregister for DOCX-kilder')
    rows=document.get('documents')
    if not isinstance(rows,list) or len(rows)<3:
        raise ValueError('DOCX-signaturregisteret er ufullstendig')
    result={}
    for row in rows:
        name=row.get('path')
        digest=row.get('git_blob_sha1')
        if (not isinstance(name,str) or name in result or
            not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{40}',digest)):
            raise ValueError('Ugyldig DOCX-signatur')
        result[name]=digest
    return result,_digest(path,200_000)


def _get_manifest(root: Path) -> tuple[dict[str, dict], str]:
    path = root / 'docs/kilder/noark/SOURCE-MANIFEST.json'
    report = _read_json(path, MAX_MANIFEST_BYTES)
    rows = report.get('files')
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise ValueError('Ukjent format for kildemanifest')
    index: dict[str, dict] = {}
    for item in rows:
        name = item.get('path')
        if not isinstance(name, str) or name in index:
            raise ValueError('Ugyldig eller duplisert manifeststi')
        index[name] = item
    return index, _digest(path, MAX_MANIFEST_BYTES)


def _safe_source(root: Path, relative: str) -> Path:
    base = (root / 'docs/kilder/noark').resolve()
    candidate = Path(relative)
    if candidate.is_absolute() or '..' in candidate.parts:
        raise ValueError('Usikker relativ kildesti')
    target = (base / candidate).resolve()
    if not target.is_relative_to(base):
        raise ValueError('Kildesti utenfor kilderepo')
    return target


def _issue(severity: str, kind: str, *, version: str = '', source: str = '',
           location: str = '', detail: str = '') -> dict:
    return {'severity': severity, 'kind': kind, 'noark_version': version,
            'source': source, 'location': location, 'detail': detail[:900]}


def _compare_text(a: str, b: str) -> float:
    # Ignore formatting/spacing artifacts, not substantive missing text.
    a = ''.join(ch for ch in a.casefold() if ch.isalnum())
    b = ''.join(ch for ch in b.casefold() if ch.isalnum())
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return round(SequenceMatcher(None, a[:5000], b[:5000], autojunk=False).ratio(), 4)


def _clause(version: str, number: str, text: str, *, origin: str,
            source: str, location: str, docx_sha: str, requirement_class: str = '',
            remarks: str = '', class_provenance: str = '', heading: str = '') -> dict:
    if len(text) > MAX_CLAUSE_CHARS or len(remarks) > MAX_CLAUSE_CHARS:
        raise ValueError('Kravcelle for lang; krever manuell undersøkelse')
    retired = bool(re.match(r'^\s*utgår\b', text, re.I))
    return {
        'candidate_id': f'{version}:{number}:' + sha256(
            (source+'|'+location+'|'+origin).encode('utf-8')).hexdigest()[:16],
        'noark_version': version, 'number': number,
        'origin': origin, 'text': text.strip(), 'full_source_cell_text_captured': True,
        'requirement_class': requirement_class,
        'class_provenance': class_provenance,
        'remarks_or_conditions': remarks.strip(),
        'source': source, 'location': location, 'source_sha256': docx_sha,
        'source_heading_context': heading,
        'printed_pdf_page_verified': False,
        'metadata_ids_mentioned': sorted(set(M_ID.findall(text+' '+remarks))),
        'review_state': 'PENDING_MANUAL_QA',
        'source_wording_independently_reviewed': False,
        'normative_requirement_approved': False,
        'dwm_implementation_verified': False,
        'saxon_lxml_semantic_parity_verified': False,
        'retired_text': retired,
        'qa_severity': 'NOTE' if retired else 'WARNING',
        'qa_reasons': ['retired_clause_requires_review' if retired else
                       'docx_transcription_not_normatively_approved'],
    }


def _word_requirement_prefix(text: str) -> tuple[str, str, bool] | None:
    if not text or NOT_A_REQUIREMENT_PREFIX.match(text) or TOC_LEADER.search(text):
        return None
    match = WORD_REQUIREMENT_PREFIX.match(text)
    if not match:
        return None
    return (match.group('number'),match.group('tail').strip(' \n\t:.-'),
            bool(match.group('prefix')))


def extract_docx_clauses(document: dict, *, version: str, source: str,
                         source_sha256: str) -> tuple[list[dict], list[dict]]:
    """Index explicit and Word-generated requirement identifiers conservatively.

    Original Word documents may use automatic OOXML numbering rather than a
    literal number in w:t. A number and complete text in the same Word row or
    numbered paragraph are evidence candidates; neither is normative approval.
    Ambiguous/empty paragraphs remain review-only evidence, not fabricated rows.
    """
    rows, unstructured = [], []
    heading = ''
    seen = set()

    def append_clause(number: str, text: str, *, anchor: str, origin: str,
                      grade: str = '', remarks: str = '', grade_from: str = '',
                      header_confirmed: bool = False, uncertain: bool = False) -> None:
        key = (number,anchor)
        if key in seen:
            return
        seen.add(key)
        if not text:
            unstructured.append({'noark_version':version,'number':number,
                'text':text,'source':source,'location':anchor,
                'qa_severity':'WARNING','qa_reason':'short_or_empty_numbered_source_requires_manual_review'})
            return
        try:
            clause = _clause(version,number,text,origin=origin,source=source,
                location=anchor,docx_sha=source_sha256,requirement_class=grade,
                remarks=remarks,class_provenance=grade_from,heading=heading)
        except ValueError as exc:
            unstructured.append({'noark_version':version,'number':number,
                'text':text[:250],'source':source,'location':anchor,
                'qa_severity':'FEIL','qa_reason':'overlong_requirement_cell',
                'detail':str(exc)})
            return
        if not grade and not clause['retired_text']:
            clause['qa_reasons'].append('missing_explicit_requirement_class')
        if grade and not header_confirmed and not grade_from.endswith('xlsx'):
            clause['qa_reasons'].append('requirement_class_header_not_confirmed')
        if len(text) < 24 and not clause['retired_text']:
            clause['qa_reasons'].append('short_clause_requires_manual_review')
        if uncertain:
            clause['qa_reasons'].append('numbering_or_paragraph_structure_requires_manual_review')
        rows.append(clause)
        if len(rows) > MAX_CLAUSES:
            raise ValueError('For mange kravrader i DOCX')

    for block in document['blocks']:
        if block['kind'] == 'paragraph':
            text = block['text'].strip()
            style = block.get('style','')
            generated = block.get('numbering_label','')
            current_heading = _reliable_heading_context(text,style,generated)
            if current_heading is not None:
                heading = current_heading
            parsed = _word_requirement_prefix(text)
            generated_match = NUM.fullmatch(generated)
            # Only promote literal 'Krav N: text' or a verified Word list label
            # with plausible requirement prose. Never turn normal headings or TOC
            # lines into mandatory requirements.
            if generated_match and not HEADING_STYLE.search(style) and \
                    REQUIREMENT_MODAL.search(text) and len(text) >= 25:
                append_clause(generated,text,anchor=block['anchor'],
                    origin='docx_word_numbered_paragraph',uncertain=True)
            elif parsed and parsed[2] and REQUIREMENT_MODAL.search(parsed[1]) and \
                    len(parsed[1]) >= 20:
                append_clause(parsed[0],parsed[1],anchor=block['anchor'],
                    origin='docx_explicit_krav_paragraph',uncertain=True)
            elif parsed and REQUIREMENT_MODAL.search(parsed[1]) and len(parsed[1]) >= 25:
                unstructured.append({'noark_version':version,'number':parsed[0],
                    'text':text,'source':source,'location':block['anchor'],
                    'qa_severity':'WARNING','qa_reason':'numbered_paragraph_requires_manual_table_review'})
            continue
        header_seen = False
        for row in block['rows']:
            cells = [str(c.get('text') or '').strip() for c in row['cells']]
            if not cells:
                continue
            if any(c.casefold().strip(' :.') in {'krav','kravnr','krav nr',
                       'kravnummer','kravtekst'} for c in cells[:2]) and any(
                c.casefold().strip(' :. ') in {'type','kravtype','krav type','kravklasse'}
                for c in cells):
                header_seen = True
                continue
            candidates = []
            for ci,cell in enumerate(row['cells']):
                # Numeric column, optionally prefixed 'Krav' and/or containing
                # text in the same cell. Do not misread prose references.
                literal = _word_requirement_prefix(cells[ci])
                if literal and ci <= 2:
                    candidates.append((ci,literal[0],literal[1],False,row['anchor']))
                for item in cell.get('paragraphs',[]):
                    label=item.get('numbering_label','')
                    if (NUM.fullmatch(label) and not HEADING_STYLE.search(item.get('style',''))
                            and (ci <= 2 or REQUIREMENT_MODAL.search(item.get('text','')))):
                        candidates.append((ci,label,item['text'],True,item['anchor']))
            if not candidates:
                continue
            # A row can contain several genuine auto-numbered paragraphs. Do
            # not concatenate them into a fictitious single requirement.
            if len({(c[1],c[4]) for c in candidates}) > 1:
                for ci,number,text,auto,anchor in candidates:
                    if auto:
                        append_clause(number,text,anchor=anchor,
                            origin='docx_word_numbered_table_paragraph',uncertain=True)
                    else:
                        unstructured.append({'noark_version':version,'number':number,
                            'text':text or ' | '.join(cells),'source':source,
                            'location':anchor,'qa_severity':'WARNING',
                            'qa_reason':'multiple_numbered_items_in_single_word_row'})
                continue
            ci,number,text,auto,anchor = candidates[0]
            remaining = cells[ci+1:]
            embedded_grade = ''
            if text.upper() in TYPES:
                embedded_grade,text = text.upper(),''
            else:
                typed = re.match(r'^([OBV])\s*\n\s*(.+)$', text, re.S)
                if typed:
                    embedded_grade,text=typed.group(1),typed.group(2).strip()
                else:
                    typed = re.match(r'^(.+?)\s*\n\s*([OBV])$',text,re.S)
                    if typed:
                        embedded_grade,text=typed.group(2),typed.group(1).strip()
            if not text:
                # The number is in the first cell, the text is often the next
                # nonempty cell (possibly after a standalone type column).
                non_grade = [(k,v) for k,v in enumerate(remaining) if v and v.upper() not in TYPES]
                if non_grade:
                    next_index,text=non_grade[0]
                    remaining=remaining[:next_index]+remaining[next_index+1:]
            grade,grade_from = (embedded_grade, 'embedded_type_token_unverified') if embedded_grade else ('', '')
            for i,val in enumerate(remaining):
                if val.upper() in TYPES and not grade:
                    grade=val.upper()
                    grade_from='named_type_column' if header_seen else 'table_cell_header_unverified'
                    remaining=remaining[:i]+remaining[i+1:]
                    break
            remarks=' | '.join(v for v in remaining if v)
            append_clause(number,text,anchor=anchor,origin=(
                'docx_word_numbered_table_paragraph' if auto else 'docx_numbered_table_row'),
                grade=grade,remarks=remarks,grade_from=grade_from,
                header_confirmed=header_seen,uncertain=auto)
    return rows, unstructured


def _xlsx_primary(a8: dict, *, root: Path, manifest: dict[str, dict],
                  issues: list[dict]) -> list[dict]:
    """Reopen the original v3.1 table; a8 textual rows are not blindly trusted."""
    rel = 'noark5/v3.1/spesifikasjoner/' + XLSX_31
    path = _safe_source(root,rel)
    item = manifest.get(rel)
    if item is None or not item.get('sha256'):
        issues.append(_issue('FEIL','xlsx_manifest_entry_missing',version='3.1',source=rel))
        return []
    try:
        digest = _digest(path)
    except (OSError, ValueError) as exc:
        issues.append(_issue('FEIL','xlsx_missing_or_unreadable',version='3.1',source=rel,detail=str(exc)))
        return []
    if digest != item['sha256']:
        issues.append(_issue('FEIL','xlsx_sha256_mismatch',version='3.1',source=rel))
        return []
    try:
        with ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos)>20_000 or sum(x.file_size for x in infos)>80_000_000:
                raise ValueError('For stort eller uvanlig XLSX-innhold')
        xlsx_sections = _xlsx_sections(path)
    except (OSError,ValueError,KeyError) as exc:
        issues.append(_issue('FEIL','xlsx_read_failed',version='3.1',source=rel,detail=type(exc).__name__))
        return []
    records = []
    for location, raw in xlsx_sections:
        cells = [x.strip() for x in raw.split(' | ')]
        if len(cells)<2 or not NUM.fullmatch(cells[0]):
            continue
        number, full_text = cells[0], cells[1]
        if not full_text:
            issues.append(_issue('WARNING','empty_xlsx_requirement_text',version='3.1',
                                 source=rel,location=location,detail=number))
            continue
        grade_index=next((i for i,v in enumerate(cells[2:],2) if v.upper() in TYPES),None)
        grade=cells[grade_index].upper() if grade_index is not None else ''
        comments=' | '.join(cells[grade_index+1:] if grade_index is not None else cells[2:])
        try:
            row = _clause('3.1',number,full_text,origin='xlsx_requirement_row',
                          source=rel,location=location,docx_sha=digest,
                          requirement_class=grade, remarks=comments,
                          class_provenance='xlsx_class_cell' if grade else '')
        except ValueError:
            issues.append(_issue('FEIL','xlsx_clause_exceeds_limit',version='3.1',
                                 source=rel,location=location))
            continue
        records.append(row)
    return records


def _enrich_v31_with_docx(rows: list[dict], docx: list[dict],
                           passages: list[dict], issues: list[dict]) -> None:
    indexed = defaultdict(list)
    for row in docx:
        indexed[row['number']].append(row)
    standalone = {r['number'] for r in passages}
    for row in rows:
        matches = indexed.get(row['number'],[])
        row['docx_main_standalone_reference'] = row['number'] in standalone
        row['docx_main_row_references'] = [m['location'] for m in matches]
        if not matches:
            reason = ('docx_requirement_in_paragraph_not_table' if row['docx_main_standalone_reference']
                      else 'xlsx_requirement_not_found_in_docx_table')
            row['qa_reasons'].append(reason)
            issues.append(_issue('WARNING',reason,version='3.1',source=row['source'],
                                 location=row['location'],detail=row['number']))
            row['docx_xlsx_similarity'] = None
            continue
        scores = [_compare_text(row['text'],m['text']) for m in matches]
        row['docx_xlsx_similarity'] = max(scores)
        if row['docx_xlsx_similarity'] < 0.85:
            row['qa_reasons'].append('docx_xlsx_wording_differs_or_is_incomplete')
            issues.append(_issue('WARNING','docx_xlsx_text_differs',version='3.1',
                                 source=row['source'],location=row['location'],
                                 detail=f"{row['number']}: score {row['docx_xlsx_similarity']}"))


def _mark_duplicates(rows: list[dict], issues: list[dict]) -> dict[str, list[str]]:
    groups: dict[tuple[str,str],list[dict]] = defaultdict(list)
    for row in rows:
        groups[(row['noark_version'],row['number'])].append(row)
    repeats = {}
    for (version,number),vals in groups.items():
        if len(vals) < 2:
            continue
        key=f'{version}:{number}'
        repeats[key]=[r['location'] for r in vals]
        texts={re.sub(r'\s+',' ',r['text']).casefold() for r in vals}
        different=len(texts)>1
        reason='duplicate_conflicting_clause_text' if different else 'duplicate_clause_occurrence'
        locations=' | '.join(r['location'] for r in vals)
        variants=' | '.join(f"{r['location']}: {r['text'][:95]}" for r in vals)
        issues.append(_issue('FEIL' if different else 'WARNING',reason,
                             version=version,source=vals[0]['source'],
                             location=locations[:400],detail=f'{key}; {variants}'))
        for row in vals:
            row['qa_reasons'].append(reason)
            if different:
                row['qa_severity']='FEIL'
    return repeats


def build_register(a8: dict, *, source_root: Path | str,
                   progress: Callable[[str], None] | None = None,
                   signatures_path: Path | str | None = None) -> dict:
    if a8.get('report_type') != A8_REPORT_TYPE or a8.get('normative_requirements_approved') is not False:
        raise ValueError('Forventet en ikke-godkjent Noark 5 a8-kravrapport')
    if not isinstance(a8.get('versions'),dict) or set(a8['versions']) != set(VERSIONS):
        raise ValueError('A8-rapporten mangler standardversjoner')
    root=Path(source_root).resolve()
    if not root.is_dir():
        raise FileNotFoundError('Kilderepositoriet finnes ikke')
    manifest, manifest_digest = _get_manifest(root)
    signatures, signatures_digest = _load_docx_signatures(
        Path(signatures_path) if signatures_path is not None else DEFAULT_DOCX_SIGNATURES)
    current_commit = _git_commit(root)
    issues = []
    if not current_commit:
        issues.append(_issue('WARNING','source_git_commit_not_verified'))
    if current_commit == a8.get('source_checkout_commit'):
        issues.append(_issue('NOTE','source_checkout_has_no_new_commit_since_a8'))
    rows = []
    inventory = []
    per_version = {}
    main_docx_row_by_version = {}
    paragraph_candidate_evidence = []
    for version in VERSIONS:
        folder_rel=f'noark5/v{version}/spesifikasjoner'
        folder=_safe_source(root,folder_rel)
        if not folder.is_dir():
            issues.append(_issue('FEIL','specification_directory_missing',version=version,
                                 source=folder_rel))
            per_version[version]={'requirements_indexed':0,'sources_read':0}
            continue
        docs=sorted(x for x in folder.iterdir() if x.suffix.lower()=='.docx' and not x.name.startswith('~$'))
        if len(docs)>MAX_DOCUMENTS:
            raise ValueError('For mange dokumentfiler i versjonens katalog')
        main_rows=[]
        main_unstructured=[]
        read_count=0
        for p in docs:
            relative=folder_rel+'/'+p.name
            rec={'noark_version':version,'file':relative,
                 'role':'main_specification' if p.name==DOCX_MAIN[version] else 'appendix_or_example',
                 'docx_sha256':None,'pdf_source':None,'pdf_manifest_sha256':None,
                 'docx_manifest_status':'not_registered_derived_working_copy',
                 'git_blob_sha1_verified':False, 'git_blob_sha1_expected':signatures.get(relative),
                 'pdf_sha256_verified':False,'text_readable':False,
                 'ooxml_variant':None,'tables':0,'paragraphs':0,'word_cells':0}
            try:
                docx_sha=_digest(p)
                rec['docx_sha256']=docx_sha
                expected_blob=signatures.get(relative)
                rec['git_blob_sha1_verified'] = bool(
                    expected_blob and _git_blob_sha1(p)==expected_blob)
                if not rec['git_blob_sha1_verified']:
                    issues.append(_issue('FEIL','docx_unverified_against_pinned_git_blob',
                                         version=version,source=relative))
                    inventory.append(rec)
                    continue
                docx_manifest = manifest.get(relative)
                if docx_manifest is not None:
                    rec['docx_manifest_status'] = ('sha256_verified' if docx_manifest.get('sha256')==docx_sha
                                                   else 'sha256_conflict')
                    if rec['docx_manifest_status']=='sha256_conflict':
                        issues.append(_issue('FEIL','docx_manifest_sha256_mismatch',version=version,
                                             source=relative))
                        inventory.append(rec)
                        continue
                pdf_name=p.name.replace(' (word).docx','.pdf') if p.name.endswith(' (word).docx') else p.stem+'.pdf'
                pdf_relative=folder_rel+'/'+pdf_name
                rec['pdf_source']=pdf_relative
                listed=manifest.get(pdf_relative)
                if listed is None or not listed.get('sha256'):
                    issues.append(_issue('WARNING','corresponding_pdf_not_listed_in_manifest',
                                         version=version,source=relative))
                else:
                    rec['pdf_manifest_sha256']=listed['sha256']
                    try:
                        pdf_sha=_digest(_safe_source(root,pdf_relative),25_000_000)
                        rec['pdf_sha256_verified'] = pdf_sha==listed['sha256']
                    except (OSError,ValueError) as exc:
                        issues.append(_issue('FEIL','pdf_source_missing_or_unreadable',
                                             version=version,source=pdf_relative,detail=str(exc)))
                    else:
                        if not rec['pdf_sha256_verified']:
                            issues.append(_issue('FEIL','pdf_original_sha256_mismatch',
                                                 version=version,source=pdf_relative))
                if progress:
                    progress(f'Noark {version}: leser {p.name}')
                doc=read_docx_structured(p)
                rec.update({'text_readable':bool(doc['text_characters']),
                            'ooxml_variant':doc['namespace'], 'tables':doc['tables'],
                            'paragraphs':doc['paragraphs'],'word_cells':doc['cells'],
                            'text_characters':doc['text_characters'],
                            'word_numbering_paragraphs':doc['word_numbering_paragraphs'],
                            'word_numbering_unresolved':doc['word_numbering_unresolved'],
                            'original_pdf_wording_equivalence_verified':False})
                if not rec['text_readable']:
                    issues.append(_issue('FEIL','docx_no_readable_text',version=version,source=relative))
                else:
                    read_count+=1
                if p.name==DOCX_MAIN[version] and rec['text_readable']:
                    if rec['pdf_sha256_verified']:
                        main_rows,main_unstructured=extract_docx_clauses(doc,version=version,
                            source=relative,source_sha256=docx_sha)
                    else:
                        issues.append(_issue('FEIL','main_docx_without_verified_pdf_source',
                                             version=version,source=relative))
                inventory.append(rec)
            except (OSError,ValueError,KeyError) as exc:
                rec['read_error']=type(exc).__name__+': '+str(exc)[:350]
                issues.append(_issue('FEIL','docx_read_failed',version=version,
                                     source=relative,detail=rec['read_error']))
                inventory.append(rec)
        if not any(d['file'].endswith('/'+DOCX_MAIN[version]) for d in inventory if d['noark_version']==version):
            issues.append(_issue('FEIL','main_specification_docx_missing',version=version,
                                 source=folder_rel+'/'+DOCX_MAIN[version]))
        main_docx_row_by_version[version]=main_rows
        paragraph_candidate_evidence.extend(main_unstructured)
        if version=='3.1':
            primary=_xlsx_primary(a8,root=root,manifest=manifest,issues=issues)
            if main_rows or main_unstructured:
                _enrich_v31_with_docx(primary,main_rows,main_unstructured,issues)
            elif primary:
                issues.append(_issue('FEIL','v31_docx_crosscheck_unavailable',version='3.1',
                                     source=folder_rel+'/'+DOCX_MAIN[version]))
            rows.extend(primary)
            indexed_count=len(primary)
        else:
            rows.extend(main_rows)
            indexed_count=len(main_rows)
        per_version[version]={
            'requirements_indexed':indexed_count,
            'sources_found':len(docs),'sources_read':read_count,
            'main_docx_rows':len(main_rows),
            'paragraph_candidates_for_manual_review':len(main_unstructured),
            'main_docx_numbering_paragraphs':next((d.get('word_numbering_paragraphs',0)
                for d in inventory if d['noark_version']==version and d['role']=='main_specification'),0),
            'main_docx_unresolved_numbering':next((d.get('word_numbering_unresolved',0)
                for d in inventory if d['noark_version']==version and d['role']=='main_specification'),0),
            'a8_pdf_numbered_line_candidates':int(a8['versions'][version].get('source_candidates') or 0),
            'xlsx_is_primary':version=='3.1',
            'normative_review_completed':False,
        }
        if indexed_count==0:
            issues.append(_issue('FEIL','no_requirement_rows_indexed',version=version,
                                 source=folder_rel+'/'+DOCX_MAIN[version]))
    if len(rows)>MAX_CLAUSES:
        raise ValueError('Det totale kravregisteret overstiger sikkerhetsgrensen')
    duplicates=_mark_duplicates(rows,issues)
    # We do not guess missing classes or transform an algorithmic suggestion to a control.
    for row in rows:
        if row.get('requirement_class') not in TYPES and not row.get('retired_text'):
            row['qa_reasons'].append('requirement_class_not_verified')
        row['static_extract_testability'] = 'NOT_REVIEWED'
        row['xpath_control_mapping'] = 'NOT_VERIFIED'
    per_version_qa={v:dict(Counter(r['qa_severity'] for r in rows if r['noark_version']==v))
                    for v in VERSIONS}
    for v in VERSIONS:
        per_version.setdefault(v,{}).update({
            # Candidate statuses differ from individually actionable QA issues.
            'qa_counts':per_version_qa[v],
            'qa_issue_counts':dict(Counter(i['severity'] for i in issues
                                           if i['noark_version']==v)),
        })
    return {
        'report_format_version':1,'report_type':REPORT_TYPE,
        'source_repository':'IKAMR/digital-archive-workflow',
        'source_checkout_commit_current':current_commit,
        'source_manifest_sha256':manifest_digest,
        'docx_git_blob_signature_registry_sha256':signatures_digest,
        'a8_source_checkout_commit_historical':a8.get('source_checkout_commit'),
        'a8_report_sha256':None,
        'source_files_modified':False,
        'original_pdf_wording_equivalence_verified':False,
        'normative_requirements_approved':False,
        'full_normative_coverage_verified':False,
        'dwm_implementation_coverage_verified':False,
        'saxon_lxml_semantic_parity_verified':False,
        'versions':per_version,
        'candidate_rows':rows,
        'unstructured_paragraph_candidates':paragraph_candidate_evidence,
        'duplicate_number_groups':duplicates,
        'source_inventory':inventory,
        'qa_issues':issues,
        'extraction_method':(
            'Noark 5 v3.1: verified XLSX requirement cells with DOCX cross-check. '
            'v4.0/v5.0: separate native DOCX table cells, numbered OOXML list '
            'paragraphs, explicit Krav-prefixes and anchored rows; '
            'ambiguous paragraphs are segregated, not approved. Source PDF bytes '
            'are checked against manifest, DOCX exact SHA is recorded; full PDF/DOCX '
            'wording equality and requirement interpretation need independent QA.'),
    }


def filter_register_rows(report: dict, *, version: str = '', severity: str = '',
                         origin: str = '', query: str = '') -> list[dict]:
    if report.get('report_type')!=REPORT_TYPE:
        raise ValueError('Ikke en gjenkjennelig a9-kravrapport')
    if version not in ('',*VERSIONS) or severity not in ('','FEIL','WARNING','NOTE'):
        raise ValueError('Ukjent versjon eller QA-filter')
    q=query.strip().casefold()
    return [r for r in report.get('candidate_rows',[]) if
            (not version or r['noark_version']==version) and
            (not severity or r['qa_severity']==severity) and
            (not origin or r['origin']==origin) and
            (not q or q in ' '.join(str(r.get(k) or '') for k in
             ('number','text','source','location','remarks_or_conditions','requirement_class')).casefold())]


def _csv(rows: list[dict], keys: tuple[str, ...]) -> str:
    f=io.StringIO(newline='')
    writer=csv.DictWriter(f,fieldnames=keys,lineterminator='\n')
    writer.writeheader()
    for r in rows:
        writer.writerow({k:_csv_safe(' | '.join(str(x) for x in r[k]) if isinstance(r.get(k),list)
                                  else r.get(k)) for k in keys})
    return f.getvalue()


def markdown_summary(report: dict) -> str:
    lines=['# Noark 5 - kravregister for manuell normativ QA (a9)','',
        '**Ikke attestert normativt fullstendig eller kontrollert mot hele PDF-ordlyden.**',
        'Ingen kildefiler, XSD-er eller XPath-tester er endret.','',
        'Kilderepo-commit: `'+str(report.get('source_checkout_commit_current') or 'UKJENT')+'`.',
        'Manifest SHA-256: `'+str(report['source_manifest_sha256'])+'`.','',
        '| Noark | Registrerte kildekrav | DOCX tabellrader | DOCX filer lest | Uavklarte avsnitt | Word-nummerering (uavklart) |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for v in VERSIONS:
        d=report['versions'][v]
        lines.append(f"| {v} | {d['requirements_indexed']} | {d['main_docx_rows']} | "
                     f"{d['sources_read']}/{d['sources_found']} | "
                     f"{d['paragraph_candidates_for_manual_review']} | "
                     f"{d.get('main_docx_numbering_paragraphs',0)} "
                     f"({d.get('main_docx_unresolved_numbering',0)}) |")
    qa=Counter(x['severity'] for x in report['qa_issues'])
    lines += ['',f"Uavklarte kilde-/innholdsavvik: FEIL {qa['FEIL']}, WARNING {qa['WARNING']}, NOTE {qa['NOTE']}.",'',
        '## Faglige grenser','',
        '- Word-nummerering som ikke er gjenskapt, kan også være punktlister eller andre listeformater; dette tallet er ikke antallet manglende krav.',
        '- Kapittelkontekst brukes bare fra gjenkjente overskrifter, aldri fra innholdsfortegnelsens sidenumre. Tom kontekst betyr ikke verifisert side-/kapittelplassering.',
        '- QA-antall for kravkandidater og antall individuelle kilde-QA-saker er to forskjellige størrelser.',
        '- v3.1: XLSX er primær; manglende eller avvikende DOCX-transkripsjoner markeres for manuell kontroll.',
        '- v4/v5: kravtekst, type og merknader leses fra Word-tabellceller og nummererte Word-avsnitt; uavklart nummerering og tvetydige treff krever manuell QA.',
        '- DOCX-ankre er Word/XML-posisjoner, ikke verifiserte sidetall fra original-PDF.',
        '- PDF-hashverifisering dokumenterer kildefilens identitet, **ikke** at DOCX-teksten er identisk.',
        '- QA-status er kildebehandling. Den er ikke feilklassifikasjon for et arkivuttrekk.',
        '- Ingen krav eller kontroller blir normativt godkjent automatisk.','',
        '## QA-funn (første 100)','']
    for issue in report['qa_issues'][:100]:
        lines.append('- '+str(issue['severity'])+' / '+str(issue['kind'])+': '+str(issue.get('source') or issue.get('noark_version') or '')
                     +' '+str(issue.get('detail') or ''))
    if len(report['qa_issues'])>100:
        lines.append(f"- ... se JSON/CSV for {len(report['qa_issues'])-100} flere funn")
    lines.append('')
    return '\n'.join(lines)


def write_reports(report: dict, output_dir: Path | str, *, source_root: Path | str) -> list[Path]:
    dest=Path(output_dir).resolve()
    root=Path(source_root).resolve()
    dwm=Path(__file__).resolve().parents[1]
    for prohibited in (root,dwm):
        if dest==prohibited or dest.is_relative_to(prohibited) or prohibited.is_relative_to(dest):
            raise ValueError('Rapportmappe må ligge utenfor kode- og kilderepo')
    files=[dest/n for n in REPORT_NAMES]
    if any(x.exists() for x in files):
        raise FileExistsError('En eller flere a9-rapporter finnes; overskriving er sperret')
    fields=('noark_version','number','origin','requirement_class','text',
            'remarks_or_conditions','source','location','source_sha256',
            'docx_xlsx_similarity','qa_severity','qa_reasons','review_state',
            'printed_pdf_page_verified')
    issues_fields=('severity','kind','noark_version','source','location','detail')
    outputs=[json.dumps(report,ensure_ascii=False,indent=2)+'\n',
             _csv(report['candidate_rows'],fields),
             json.dumps({'source_checkout_commit_current':report['source_checkout_commit_current'],
                         'source_manifest_sha256':report['source_manifest_sha256'],
                         'documents':report['source_inventory']},ensure_ascii=False,indent=2)+'\n',
             _csv(report['qa_issues'],issues_fields),markdown_summary(report)]
    if max(len(s.encode('utf-8')) for s in outputs)>MAX_OUTPUT_BYTES:
        raise ValueError('For stor generert rapport')
    dest.mkdir(parents=True,exist_ok=True)
    for path,data in zip(files,outputs):
        with path.open('x',encoding='utf-8',newline='') as writer:
            writer.write(data)
    return files


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--a8-report',type=Path,required=True,
                        help='noark5-a8-requirements.json fra forrige analyse')
    parser.add_argument('--source-root',type=Path,required=True,
                        help='Utsjekket IKAMR/digital-archive-workflow')
    parser.add_argument('--output-dir',type=Path,required=True,
                        help='Ny resultatmappe utenfor begge repoer')
    parser.add_argument('--quiet',action='store_true')
    args=parser.parse_args(argv)
    try:
        a8=_read_json(args.a8_report,MAX_REPORT_INPUT_BYTES)
        result=build_register(a8,source_root=args.source_root,
                    progress=None if args.quiet else lambda message:print(message,flush=True))
        result['a8_report_sha256']=_digest(args.a8_report,MAX_REPORT_INPUT_BYTES)
        paths=write_reports(result,args.output_dir,source_root=args.source_root)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        parser.error(str(exc))
    for path in paths:
        print(path)
    for v,info in result['versions'].items():
        print(f"Noark 5 v{v}: {info['requirements_indexed']} kildebaserte kravkandidater, "
              f"{info['main_docx_rows']} DOCX-tabellrader, "
              f"{info['sources_read']}/{info['sources_found']} DOCX lest, "
              f"Word-lister: {info.get('main_docx_numbering_paragraphs',0)} "
              f"({info.get('main_docx_unresolved_numbering',0)} uten gjenskapt tall; "
              'kan omfatte punktlister)')
    severity=Counter(i['severity'] for i in result['qa_issues'])
    print(f"Kilde-QA: FEIL={severity['FEIL']} WARNING={severity['WARNING']} NOTE={severity['NOTE']}")
    print('Full normativ kravdekning: IKKE godkjent. Arkivuttrekksamsvar: IKKE verifisert.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
