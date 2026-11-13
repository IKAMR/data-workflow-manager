"""Bounded, read-only contextual source inspection for selected Noark XML hits.

The supplied instance XPath must come from a previously scanned real occurrence.
No XML content or document is written, and no external entity is resolved.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import hashlib
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
import re
from typing import Optional


@dataclass(frozen=True)
class ContextLevel:
    element: str
    position: int
    total: Optional[int]
    system_id: str
    title: str
    selected: bool


@dataclass(frozen=True)
class XmlContext:
    source: str
    xpath: str
    line: int
    scope: str
    levels: tuple[ContextLevel, ...]
    xml: str
    truncated: bool


def _name(tag) -> str:
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


def _direct_text(element, child_name: str) -> str:
    for child in element:
        if _name(child.tag) == child_name:
            return (child.text or '').strip()[:180]
    return ''


def inspect_xml_context(path: str | Path, xpath: str, *, max_nodes: int = 25000,
                        max_chars: int = 120000) -> XmlContext:
    """Locate one exact instance path and inspect its enclosing mappe/registration.

    Ancestors above the captured subtree report an ordinal but no invented
    sibling total. Within the captured subtree, sibling totals are computed
    from actual XML children. A huge subtree fails closed rather than consuming
    unlimited memory or displaying an incomplete subtree as complete.
    """
    from lxml import etree

    source = Path(path)
    if source.name.casefold() != 'arkivstruktur.xml' or not source.is_file():
        raise ValueError('Velg en eksisterende arkivstruktur.xml')
    if not xpath.startswith('/arkiv[') or len(xpath) > 8000:
        raise ValueError('Forventet konkret XPath fra XML-evidens')
    if not 100 <= max_chars <= 500000 or not 100 <= max_nodes <= 100000:
        raise ValueError('Ugyldig grense for XML-kontekst')

    # XML parser reads source only. No DTD resolution, entities or network I/O.
    stream = source.open('rb')
    parser = etree.iterparse(stream, events=('start', 'end'),
                             resolve_entities=False, no_network=True,
                             load_dtd=False, huge_tree=True)
    frames: list[dict] = []
    scopes = list(re.finditer(r'/mappe\[\d+\]', xpath))
    if not scopes:
        scopes = list(re.finditer(r'/registrering\[\d+\]', xpath))
    # Keep only the chosen subtree. Other subtrees are released while parsing.
    scope_xpath = xpath[:scopes[-1].end()] if scopes else xpath.rsplit('/', 1)[0]
    captured_index = -1
    selected_index = -1
    selected_line = 0
    scope_node = None
    selected_node = None
    selected_frames = None
    scoped_events = 0
    try:
        for event, element in parser:
            tag = _name(element.tag)
            if event == 'start':
                siblings = frames[-1]['children'] if frames else {}
                ordinal = siblings.get(tag, 0) + 1
                if frames:
                    siblings[tag] = ordinal
                frames.append({'name': tag, 'position': ordinal,
                               'children': {}, 'system_id': '', 'title': ''})
                concrete = '/' + '/'.join(f"{frame['name']}[{frame['position']}]" for frame in frames)
                if concrete == scope_xpath:
                    captured_index = len(frames) - 1
                    scope_node = element
                if captured_index >= 0:
                    scoped_events += 1
                    if scoped_events > max_nodes:
                        raise ValueError('XML-seksjonen er for stor for kontekstvisning. Velg et mindre utdrag.')
                continue

            if tag == 'systemID' and len(frames) > 1:
                frames[-2]['system_id'] = (element.text or '').strip()[:120]
            if tag == 'tittel' and len(frames) > 1:
                frames[-2]['title'] = (element.text or '').strip()[:180]
            concrete = '/' + '/'.join(f"{frame['name']}[{frame['position']}]" for frame in frames)
            if concrete == xpath:
                selected_index = len(frames) - 1
                selected_node = element
                selected_frames = [dict(frame) for frame in frames]
                selected_line = int(element.sourceline or 0)
                # Selected scope has been retained since its opening element.

            if (captured_index >= 0 and selected_node is not None
                    and len(frames) - 1 == captured_index and element is scope_node):
                # All siblings inside this selected scope have now been parsed.
                from lxml import etree as E
                content = E.tostring(element, encoding='unicode', pretty_print=True, with_tail=False)
                truncated = len(content) > max_chars
                if truncated:
                    content = content[:max_chars] + '\n<!-- XML-utdrag avkortet for visning; original uendret -->'
                chain = []
                node = selected_node
                while node is not None and node is not scope_node:
                    chain.append(node)
                    node = node.getparent()
                chain.append(scope_node)
                chain.reverse()
                scope_idx = captured_index
                levels = []
                for i, frame in enumerate(selected_frames):
                    if i < scope_idx:
                        total = None
                        sid = frame['system_id']
                        title = frame['title']
                    elif i - scope_idx < len(chain):
                        current = chain[i - scope_idx]
                        parent = current.getparent()
                        total = (sum(1 for c in parent if _name(c.tag) == frame['name'])
                                 if parent is not None and i > scope_idx else None)
                        sid = _direct_text(current, 'systemID') or frame['system_id']
                        title = _direct_text(current, 'tittel') or frame['title']
                    else:
                        break
                    levels.append(ContextLevel(frame['name'], frame['position'], total,
                                               sid, title, i == selected_index))
                return XmlContext(str(source), xpath, selected_line,
                                  frames[scope_idx]['name'], tuple(levels), content, truncated)
            # The source may have changed since the original hit was found.
            # Release an inspected scope without a matching target and stop
            # retaining its descendants rather than scanning unboundedly.
            if (captured_index >= 0 and selected_node is None
                    and len(frames) - 1 == captured_index and element is scope_node):
                captured_index = -1
                scope_node = None
            frames.pop()
            if captured_index < 0:
                element.clear()
                while element.getprevious() is not None:
                    del element.getparent()[0]
    except etree.XMLSyntaxError as exc:
        raise ValueError('XML kan ikke leses: ' + str(exc)) from exc
    finally:
        del parser
        stream.close()
    raise ValueError('XPath finnes ikke lenger i den valgte kildefilen. Kjør kildeoppslag på nytt.')


def readable_xml(xml_text: str) -> str:
    """Indent an isolated XML fragment for viewing, without changing text values.

    Only whitespace-only formatting nodes are discarded; meaningful text nodes
    and attributes are preserved. This is presentation, not original file bytes.
    """
    from lxml import etree
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False,
                             no_network=True, remove_blank_text=True, huge_tree=False)
    try:
        element = etree.fromstring(xml_text.encode('utf-8'), parser=parser)
    except etree.XMLSyntaxError as exc:
        raise ValueError('Ufullstendig XML kan ikke formateres som et helt element') from exc
    etree.indent(element, space='  ')
    return etree.tostring(element, encoding='unicode', pretty_print=False, with_tail=False)


def save_xml_extract(work: str | Path, *, source: str | Path, xpath: str,
                     xml_text: str, scope: str, line: int, test_id: str,
                     full_section: bool = True) -> Path:
    """Export one complete XML fragment and a provenance manifest inside Work.

    Never write to Source. The caller must provide an already selected, complete
    XML element/section; a truncated preview is deliberately not accepted.
    """
    from lxml import etree
    work_path = Path(work)
    if not (work_path.is_dir() and (work_path / 'job.json').is_file()):
        raise ValueError('Fant ikke et godkjent Work-område med job.json')
    source_path = Path(source)
    if source_path.name.casefold() != 'arkivstruktur.xml' or not source_path.is_file():
        raise ValueError('XML-kilden må være en eksisterende arkivstruktur.xml')
    if not xpath.startswith('/arkiv[') or len(xpath) > 8000:
        raise ValueError('Ugyldig kilde-XPath')
    if not isinstance(xml_text, str) or not xml_text or len(xml_text) > 500000:
        raise ValueError('XML-utdrag mangler eller er for stort')
    if 'XML-utdrag avkortet for visning' in xml_text:
        raise ValueError('Avkortet XML-kontekst kan ikke eksporteres som fullstendig XML')
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
    try:
        etree.fromstring(xml_text.encode('utf-8'), parser=parser)
    except etree.XMLSyntaxError as exc:
        raise ValueError('XML-utdraget er ikke et komplett, gyldig XML-element') from exc
    export_root = work_path / 'custom_work' / 'xml_extracts'
    # Do not follow pre-existing symlinked export directories outside Work.
    base = work_path.resolve(strict=True)
    for folder in (work_path / 'custom_work', export_root):
        if folder.exists() and (folder.is_symlink() or not folder.is_dir()):
            raise ValueError('Arbeidsmappen er ikke en vanlig katalog')
    export_root.mkdir(parents=True, exist_ok=True)
    if not export_root.resolve().is_relative_to(base):
        raise ValueError('Eksportmålet er utenfor Work')
    identifier = str(uuid4())
    destination = export_root / ('XML-' + identifier)
    destination.mkdir(mode=0o700)
    raw = xml_text.encode('utf-8')
    try:
        (destination / 'extract.xml').write_bytes(raw)
        manifest = {
            'schema_version': '1.0',
            'export_id': identifier,
            'created_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'type': 'complete_xml_section' if full_section else 'complete_xml_element',
            'test_id': test_id,
            'source_xml': str(source_path),
            'source_xpath': xpath,
            'source_line': line,
            'scope': scope,
            'export_filename': 'extract.xml',
            'export_sha256': hashlib.sha256(raw).hexdigest(),
            'original_source_unchanged': True,
            'serialization': 'lxml; not a byte-identical original file excerpt',
        }
        (destination / 'manifest.json').write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    except BaseException:
        for child in destination.iterdir():
            child.unlink()
        destination.rmdir()
        raise
    return destination
