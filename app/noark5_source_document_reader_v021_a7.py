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
from zipfile import ZipFile

M_ID = re.compile(r'(?<![A-Za-z0-9])M\d{3}(?![A-Za-z0-9])')
REQUIREMENT_ID = re.compile(r'\b\d+\.\d+\.\d+\b')
WORD_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
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


def _docx_sections(path: Path) -> list[tuple[str, str]]:
    sections = []
    with ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name == 'word/document.xml'
                   or re.fullmatch(r'word/(?:footnotes|endnotes|header\d+|footer\d+)\.xml', name)]
        for member in members:
            root = ET.fromstring(archive.read(member))
            ptag, ttag = f'{{{WORD_NS}}}p', f'{{{WORD_NS}}}t'
            for i, paragraph in enumerate(root.iter(ptag), 1):
                value = ''.join(node.text or '' for node in paragraph.iter(ttag)).strip()
                if value:
                    sections.append((f'{member}:p{i}', value))
    return sections


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
    except (OSError, ValueError, KeyError, ET.ParseError) as exc:
        return [], f'parse_error:{type(exc).__name__}'
