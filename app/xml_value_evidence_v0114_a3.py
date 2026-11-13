"""Read-only, bounded Noark 5 XML occurrence lookup.

Saved aggregate report counts are not source-object references. This scanner
returns genuine line numbers and instance XPaths in the selected source XML.
No transformations of observed strings, no version inference, no writes.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json


@dataclass(frozen=True)
class XmlOccurrence:
    line: int
    xpath: str
    system_id: str
    value: str
    xml: str


# Exact sources from config/noark5/tests/xpath_catalog_2026_05_26.json.
# Adding another field requires a reviewed mapping, never a guessed XPath.
_SOURCE_XPATHS = {
    ('kdrs.c02', 'document_medium'): '//arkivdel//dokumentbeskrivelse/dokumentmedium',
    ('kdrs.c15', 'journalpost_type'): '//registrering/journalposttype',
    ('kdrs.f08', 'access_restriction'): '//skjerming/tilgangsrestriksjon',
    ('kdrs.f08', 'screening_metadata'): '//skjerming/skjermingMetadata',
}

def source_xpath_for_finding(test_id: str, field: str) -> str | None:
    return _SOURCE_XPATHS.get((test_id.casefold(), field))

def source_xml_for_work(work: str | Path | None) -> Path | None:
    """Use a Work-local, saved source reference. Never search unrelated disks."""
    if not work:
        return None
    try:
        job_file = Path(work) / 'job.json'
        if not job_file.is_file() or job_file.stat().st_size > 2_000_000:
            return None
        obj = json.loads(job_file.read_text(encoding='utf-8-sig'))
        data = obj.get('job', obj) if isinstance(obj, dict) else {}
        if not isinstance(data, dict):
            return None
        for key in ('source_extraction', 'source_unzipped', 'source_root'):
            raw = data.get(key)
            if not isinstance(raw, str) or not raw.strip():
                continue
            root = Path(raw)
            candidate = root / 'arkivstruktur.xml' if root.is_dir() else root
            if candidate.name.casefold() == 'arkivstruktur.xml' and candidate.is_file():
                return candidate
    except (OSError, ValueError, UnicodeError, TypeError, RuntimeError):
        return None
    return None

def describe_xml_source(path: str | Path) -> str:
    return str(path)

def _local(tag: str) -> str:
    return tag.rsplit('}', 1)[-1] if '}' in tag else tag

def find_xml_values(path: str | Path, xpath: str, value: str, *, limit: int = 25) -> tuple[XmlOccurrence, ...]:
    """Stream an actual XML file; capture exact text, parser line and XPath.

    XPath is a reviewed catalog selector. Only the terminal element is searched;
    this does not promise full XPath evaluation for new selectors.
    """
    if xpath not in _SOURCE_XPATHS.values():
        raise ValueError('XPath er ikke en godkjent kildehenvisning')
    source = Path(path)
    if source.name.casefold() != 'arkivstruktur.xml' or not source.is_file():
        raise ValueError('Velg en eksisterende arkivstruktur.xml')
    if not isinstance(value, str) or not value:
        raise ValueError('Observert verdi mangler')
    if not 1 <= limit <= 100:
        raise ValueError('Ugyldig treffgrense')
    from lxml import etree
    target = xpath.split('/')[-1]
    # The catalog selectors all terminate in a unique local element name.
    context = etree.iterparse(str(source), events=('start', 'end'),
                              resolve_entities=False, no_network=True,
                              load_dtd=False, huge_tree=True)
    frames = []
    matches = []
    try:
        for event, element in context:
            name = _local(element.tag) if isinstance(element.tag, str) else ''
            if event == 'start':
                if frames:
                    siblings = frames[-1]['children']
                    siblings[name] = siblings.get(name, 0) + 1
                    number = siblings[name]
                else:
                    number = 1
                frames.append({'name': name, 'number': number, 'children': {},
                               'system_id': ''})
                continue
            if name == 'systemID' and len(frames) >= 2:
                frames[-2]['system_id'] = (element.text or '').strip()
            if name == target and (element.text or '').strip() == value:
                # Enforce the relevant parent path, not just any matching leaf.
                names = [frame['name'] for frame in frames]
                parents = xpath.split('/')
                if xpath.startswith('//arkivdel//'):
                    valid = 'arkivdel' in names and len(names) >= 2 and names[-2] == parents[-2]
                else:
                    valid = len(names) >= 2 and names[-2] == parents[-2]
                if valid:
                    concrete = '/' + '/'.join(f"{f['name']}[{f['number']}]" for f in frames)
                    system_id = next((f['system_id'] for f in reversed(frames[:-1])
                                      if f['system_id']), '')
                    excerpt = etree.tostring(element, encoding='unicode', with_tail=False)
                    matches.append(XmlOccurrence(int(element.sourceline or 0), concrete,
                                                 system_id, value, excerpt[:4000]))
                    if len(matches) >= limit:
                        break
            frames.pop()
            element.clear()
            while element.getprevious() is not None:
                del element.getparent()[0]
    except etree.XMLSyntaxError as exc:
        raise ValueError('XML er ikke lesbar: ' + str(exc)) from exc
    finally:
        del context
    return tuple(matches)
