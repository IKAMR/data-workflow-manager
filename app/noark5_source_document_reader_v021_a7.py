"""Bounded, source-first document text extraction for DWM QA candidates.

The PDF/DOCX/XLSX original source documents are kept outside DWM in the
IKAMR/digital-archive-workflow checkout. Extracted text is never approved as a
normative rule, and printed PDF pages are not fabricated for Word/Excel files.
These helpers stay in the packaged ``app`` tree so Qt can import them without
requiring the repository-only ``tools`` scripts on the runtime PYTHONPATH.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from app.noark5_word_numbering_v021_a91 import WordNumberingResolver

M_ID = re.compile(r'(?<![A-Za-z0-9])M\d{3}(?![A-Za-z0-9])')
REQUIREMENT_ID = re.compile(r'\b\d+\.\d+\.\d+\b')
WORD_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
WORD_NS_STRICT = 'http://purl.oclc.org/ooxml/wordprocessingml/main'
WORD_NAMESPACES = frozenset((WORD_NS, WORD_NS_STRICT))
MAX_DOCX_BYTES = 15_000_000
MAX_UNCOMPRESSED_OOXML_BYTES = 80_000_000
MAX_OOXML_MEMBERS = 20_000
MAX_XML_MEMBER_BYTES = 28_000_000
SHEET_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'


def manifest_sha_status(raw: bytes, expected_sha256: str | None) -> str:
    """Record byte identity or EOL-only restoration, never modify the file."""
    if not expected_sha256:
        return 'manifest_digest_missing'
    if hashlib.sha256(raw).hexdigest() == expected_sha256:
        return 'identical_bytes'
    if b'\r\n' not in raw and hashlib.sha256(raw.replace(b'\n', b'\r\n')).hexdigest() == expected_sha256:
        return 'matches_original_after_restoring_crlf'
    return 'hash_mismatch_qa'


def _word_tag(ns: str, tag: str) -> str:
    return f'{{{ns}}}{tag}'


def _word_namespace(root: ET.Element) -> str:
    if not root.tag.startswith('{'):
        raise ValueError('DOCX uten kjent Word/XML-navnerom')
    ns = root.tag[1:].split('}', 1)[0]
    if ns not in WORD_NAMESPACES:
        raise ValueError('Ukjent WordprocessingML-navnerom: ' + ns)
    return ns


def _bounded_docx_members(path: Path) -> tuple[list[str], dict[str, bytes]]:
    """Read only bounded Word XML members; never extract paths to the disk."""
    if path.stat().st_size > MAX_DOCX_BYTES:
        raise ValueError('DOCX overstiger maksimal kildefilstørrelse')
    with ZipFile(path) as archive:
        infos = archive.infolist()
        if (len(infos) > MAX_OOXML_MEMBERS or
                sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_OOXML_BYTES):
            raise ValueError('DOCX overskrider sikkerhetsgrensen for OOXML-pakke')
        names = [info.filename for info in infos]
        if 'word/document.xml' not in names:
            raise ValueError('DOCX mangler word/document.xml')
        parts = {}
        for info in infos:
            name = info.filename
            if name in ('word/document.xml','word/numbering.xml','word/styles.xml') or re.fullmatch(
                    r'word/(?:footnotes|endnotes|header\d+|footer\d+)\.xml', name):
                if info.file_size > MAX_XML_MEMBER_BYTES:
                    raise ValueError('For stor Word/XML-del: ' + name)
                parts[name] = archive.read(info)
    return names, parts


def _paragraph_text(p: ET.Element, ns: str) -> str:
    """Preserve text runs, tabs and breaks without including deleted revisions."""
    t = _word_tag(ns, 't')
    tab = _word_tag(ns, 'tab')
    br = _word_tag(ns, 'br')
    cr = _word_tag(ns, 'cr')
    deleted = _word_tag(ns, 'del')
    output = []

    def visit(node: ET.Element) -> None:
        if node.tag == deleted:
            return
        if node.tag == t:
            output.append(node.text or '')
        elif node.tag == tab:
            output.append('\t')
        elif node.tag == br or node.tag == cr:
            output.append('\n')
        else:
            for child in node:
                visit(child)
    visit(p)
    return ''.join(output).strip()


def _docx_sections(path: Path) -> list[tuple[str, str]]:
    """Legacy paragraph index, now supporting Transitional and Strict OOXML."""
    _, parts = _bounded_docx_members(path)
    sections = []
    for member, data in parts.items():
        root = ET.fromstring(data)
        ns = _word_namespace(root)
        for i, paragraph in enumerate(root.iter(_word_tag(ns, 'p')), 1):
            value = _paragraph_text(paragraph, ns)
            if value:
                sections.append((f'{member}:p{i}', value))
    return sections


def read_docx_structured(path: Path) -> dict:
    """Read editable Word paragraphs and table cells, preserving stable XML anchors.

    This is source text, *not* a Word-vs-PDF equivalence check.  No printed
    PDF page number is inferred from Word's body structure.
    """
    path = Path(path)
    names, parts = _bounded_docx_members(path)
    root = ET.fromstring(parts['word/document.xml'])
    ns = _word_namespace(root)
    numbers = WordNumberingResolver(ns, styles_xml=parts.get('word/styles.xml'),
                                    numbering_xml=parts.get('word/numbering.xml'))
    body = root.find('.//' + _word_tag(ns, 'body'))
    if body is None:
        raise ValueError('DOCX mangler hoveddokumentets body')
    pt, tt, trt, tc, grid = (_word_tag(ns, x) for x in
                              ('p', 'tbl', 'tr', 'tc', 'gridSpan'))
    blocks: list[dict] = []
    total_paragraphs = total_tables = total_cells = total_text = 0
    for child in body:
        if child.tag == pt:
            total_paragraphs += 1
            val = _paragraph_text(child, ns)
            number_info = numbers.paragraph_info(child)
            if val:
                total_text += len(val)
                blocks.append({'kind': 'paragraph', 'anchor': f'word/document.xml:p{total_paragraphs}',
                               'text': val, **number_info})
        elif child.tag == tt:
            total_tables += 1
            rows = []
            for row_idx, row in enumerate(child.findall(trt), 1):
                cells = []
                for cell_idx, cell in enumerate(row.findall(tc), 1):
                    paragraphs = []
                    for paragraph_idx, node in enumerate(cell.iter(pt), 1):
                        content = _paragraph_text(node, ns)
                        number_info = numbers.paragraph_info(node)
                        if content or number_info['numbering_label']:
                            paragraphs.append({'text':content, **number_info,
                                'anchor':f'word/document.xml:tbl{total_tables}:row{row_idx}:cell{cell_idx}:p{paragraph_idx}'})
                    value = '\n'.join(v['text'] for v in paragraphs if v['text']).strip()
                    span = cell.find('.//' + grid)
                    try:
                        grid_span = int(span.get(_word_tag(ns, 'val'), '1')) if span is not None else 1
                    except ValueError:
                        grid_span = 1
                    cells.append({'text': value, 'grid_span': max(1, min(grid_span, 100)),
                                  'paragraphs': paragraphs})
                    total_cells += 1
                    total_text += len(value)
                rows.append({'anchor': f'word/document.xml:tbl{total_tables}:row{row_idx}',
                             'cells': cells})
            blocks.append({'kind': 'table', 'anchor': f'word/document.xml:tbl{total_tables}',
                           'rows': rows})
    other_parts = []
    for part, data in parts.items():
        if part != 'word/document.xml' and part not in ('word/numbering.xml','word/styles.xml'):
            r = ET.fromstring(data)
            part_ns = _word_namespace(r)
            count = sum(bool(_paragraph_text(p, part_ns)) for p in r.iter(_word_tag(part_ns, 'p')))
            other_parts.append({'part': part, 'nonempty_paragraphs': count})
    return {
        'namespace': 'strict' if ns == WORD_NS_STRICT else 'transitional',
        'blocks': blocks,
        'paragraphs': total_paragraphs,
        'tables': total_tables,
        'cells': total_cells,
        'text_characters': total_text,
        'zip_members': len(names),
        'word_numbering_paragraphs': numbers.numbered_paragraphs,
        'word_numbering_unresolved': numbers.unresolved_numbered_paragraphs,
        'other_story_parts': other_parts,
        'printed_page_numbers_verified': False,
    }


def _xlsx_sections(path: Path) -> list[tuple[str, str]]:
    sections = []
    ns = f'{{{SHEET_NS}}}'
    with ZipFile(path) as archive:
        entries = set(archive.namelist())
        shared = []
        if 'xl/sharedStrings.xml' in entries:
            root = ET.fromstring(archive.read('xl/sharedStrings.xml'))
            shared = [''.join(x.text or '' for x in si.iter(ns+'t'))
                      for si in root.iter(ns+'si')]
        for sheet in sorted(x for x in entries if re.fullmatch(r'xl/worksheets/sheet\d+\.xml', x)):
            root = ET.fromstring(archive.read(sheet))
            for row in root.iter(ns+'row'):
                values = []
                for cell in row.findall(ns+'c'):
                    value, inline = cell.find(ns+'v'), cell.find(ns+'is')
                    if cell.get('t') == 's' and value is not None:
                        try:
                            values.append(shared[int(value.text or '-1')])
                        except (IndexError, ValueError):
                            pass
                    elif inline is not None:
                        values.append(''.join(x.text or '' for x in inline.iter(ns+'t')))
                    elif value is not None and value.text:
                        values.append(value.text)
                if values:
                    sections.append((f'{sheet}:row{row.get("r", "?")}', ' | '.join(values)))
    return sections


def _pdf_sections(path: Path) -> tuple[list[tuple[str, str]], str]:
    try:
        import fitz  # optional runtime package, PyMuPDF
        with fitz.open(str(path)) as pdf:
            return [(f'page{i + 1}', page.get_text() or '') for i, page in enumerate(pdf)], 'pymupdf'
    except ImportError:
        pass
    except Exception as exc:
        return [], f'pdf_parse_error:{type(exc).__name__}'
    try:
        from pypdf import PdfReader  # optional fallback
        pdf = PdfReader(str(path))
        return [(f'page{i + 1}', page.extract_text() or '')
                for i, page in enumerate(pdf.pages)], 'pypdf'
    except ImportError:
        return [], 'not_read_no_pdf_library'
    except Exception as exc:
        return [], f'pdf_parse_error:{type(exc).__name__}'


def read_source_document(path: Path) -> tuple[list[tuple[str, str]], str]:
    path = Path(path)
    try:
        if path.suffix.lower() == '.pdf':
            return _pdf_sections(path)
        if path.suffix.lower() == '.docx':
            return _docx_sections(path), 'docx_xml'
        if path.suffix.lower() == '.xlsx':
            return _xlsx_sections(path), 'xlsx_xml'
        return [], 'unsupported_format'
    except (OSError, ValueError, KeyError, ET.ParseError, BadZipFile) as exc:
        return [], f'parse_error:{type(exc).__name__}'


def diagnose_docx(path: Path) -> dict:
    """Report document readability without declaring PDF equivalence or OCR."""
    try:
        doc = read_docx_structured(Path(path))
        with ZipFile(path) as archive:
            files = archive.namelist()
            root = ET.fromstring(archive.read('word/document.xml'))
        ns = _word_namespace(root)
        t, drawing, pict, obj, alt = (_word_tag(ns, tag) for tag in
                                      ('t','drawing','pict','object','altChunk'))
        count = sum(bool(el.text and el.text.strip()) for el in root.iter(t))
        embeds = sum(name.startswith(('word/media/','word/embeddings/','word/afchunk'))
                     for name in files)
        drawings = sum(el.tag in (drawing,pict,obj) for el in root.iter())
        chunks = sum(el.tag == alt for el in root.iter())
        return {
            'status': 'text_found' if doc['text_characters'] else 'no_word_text_nodes',
            'text_readable': bool(doc['text_characters']),
            'word_text_nodes': count,
            'word_drawings_or_objects': drawings,
            'word_altchunk_nodes': chunks,
            'embedded_or_media_parts': embeds,
            'word_tables': doc['tables'],
            'word_table_cells': doc['cells'],
            'text_characters': doc['text_characters'],
            'ooxml_variant': doc['namespace'],
            'other_story_parts': doc['other_story_parts'],
            'zip_members': doc['zip_members'],
            'printed_page_numbers_verified': False,
            'not_ocr_or_rendered_equivalence': True,
        }
    except (OSError, ValueError, KeyError, ET.ParseError, BadZipFile) as exc:
        return {'status': ('docx_document_xml_missing'
                           if 'mangler word/document.xml' in str(exc)
                           else 'docx_diagnostic_error:' + type(exc).__name__),
                'detail': str(exc)[:300], 'text_readable': False}
