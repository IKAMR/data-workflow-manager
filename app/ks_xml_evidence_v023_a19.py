"""A19: read-only, source-scoped XML evidence for a selected Guided KS finding.

A Work finding's file and line are an *anchor reported by a tool*, not proof that
current Source bytes are unchanged. Never invent an XPath, hierarchy, systemID
or sibling total. The job's explicitly configured Source is the sole locator.
"""
from __future__ import annotations

from collections import deque
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Callable


class XmlEvidenceError(ValueError):
    """An XML anchor cannot safely be located or inspected."""


ALLOWED_XML = frozenset({
    'arkivstruktur.xml', 'arkivuttrekk.xml', 'loependejournal.xml',
    'offentligjournal.xml', 'endringslogg.xml',
})
ARCHIVE_CHAIN = frozenset({
    'arkiv', 'arkivdel', 'klassifikasjonssystem', 'klasse', 'mappe',
    'registrering', 'dokumentbeskrivelse', 'dokumentobjekt',
})
MAX_LINE = 20_000_000
MAX_LINE_BYTES = 256 * 1024
MAX_SCAN_BYTES = 768 * 1024 * 1024
MAX_DEPTH = 96
MAX_POST_EVENTS = 180_000
MAX_JSON_JOB = 2 * 1024 * 1024


def _check_cancel(cancelled: Callable[[], bool] | None) -> None:
    if cancelled and cancelled():
        raise XmlEvidenceError('XML-inspeksjonen ble avbrutt')


def _filename(name: Any) -> str:
    """A reported *basename*, never a Source search path or external URL."""
    if not isinstance(name, str) or name.casefold() not in ALLOWED_XML or name != Path(name).name:
        raise XmlEvidenceError('Ingen entydig støttet XML-fil i funnets kildereferanse')
    if '/' in name or '\\' in name or ':' in name or '\x00' in name:
        raise XmlEvidenceError('Utrygt XML-filnavn i kildereferansen')
    return name


def documented_anchors(finding: dict, *, display_limit: int = 1000) -> dict:
    """Show only source-reported line numbers; never turn an aggregate into hits."""
    if type(display_limit) is not int or not 0 <= display_limit <= 1000:
        raise XmlEvidenceError('Ugyldig grense for ankerforhåndsvisning')
    filename = str(finding.get('file') or '')
    try:
        filename = _filename(filename)
    except XmlEvidenceError:
        return {'rows': [], 'total': 0, 'supported': False,
                'message': 'Funnet mangler et entydig støttet XML-filnavn.'}
    original = finding.get('lines')
    if not isinstance(original, (list, tuple)):
        return {'rows': [], 'total': 0, 'supported': True,
                'message': 'Ingen dokumenterte XML-linjenumre. Treff kan ikke utledes av hovedtall.'}
    lines = [n for n in original if type(n) is int and 1 <= n <= MAX_LINE]
    if len(lines) != len(original):
        return {'rows': [], 'total': 0, 'supported': False,
                'message': 'Kilden inneholder ugyldige XML-linjereferanser.'}
    sha = str(finding.get('source_xml_sha256') or '').strip()
    if sha and not re.fullmatch(r'[a-fA-F0-9]{64}', sha):
        return {'rows': [], 'total': 0, 'supported': False,
                'message': 'Ugyldig SHA-256 for oppgitt Source XML.'}
    if not str(finding.get('source_ref') or ''):
        return {'rows': [], 'total': 0, 'supported': False,
                'message': 'Funnets Work-evidensreferanse mangler.'}
    rows = [{
        'test_id': str(finding.get('test_id') or ''),
        'line': n, 'file': filename,
        'archive_part_id': str(finding.get('archive_part_id') or ''),
        'object_id': str(finding.get('object_id') or ''),
        'reported_xpath': str(finding.get('xpath') or ''),
        'source_ref': str(finding.get('source_ref') or ''),
        'source_xml_sha256': sha.lower(),
        'reported_by': str(finding.get('source') or ''),
    } for n in lines[:display_limit]]
    return {'rows': rows, 'total': len(lines), 'supported': True,
            'message': ('Ingen dokumenterte XML-linjenumre.' if not lines else ''),
            'truncated_preview': len(lines) > len(rows)}


def _job_sources(work: Path) -> list[Path]:
    p = work / 'job.json'
    if not p.is_file() or p.is_symlink() or p.stat().st_size > MAX_JSON_JOB:
        raise XmlEvidenceError('Mangler sikker Work-jobbdefinisjon')
    try:
        with p.open('r', encoding='utf-8-sig') as handle:
            job = json.load(handle)
    except (OSError, UnicodeError, ValueError) as exc:
        raise XmlEvidenceError('Uleselig Work-jobbdefinisjon') from exc
    props = job.get('job') if isinstance(job, dict) else None
    if (not isinstance(job, dict) or job.get('file_type') != 'dwm-work-job'
            or not job.get('job_uid') or not isinstance(props, dict)
            or (props.get('job_uid') and props['job_uid'] != job['job_uid'])):
        raise XmlEvidenceError('Work og jobbidentitet stemmer ikke overens')
    sources = []
    for key in ('source_extraction', 'source_unzipped', 'source_root'):
        raw = props.get(key)
        if not isinstance(raw, str) or not raw.strip():
            continue
        path = Path(raw)
        if not path.is_absolute() or path.is_symlink():
            continue
        try:
            if path.exists():
                sources.append(path.resolve(strict=True))
        except (OSError, ValueError, RuntimeError):
            pass
    return sources


def resolve_source_xml(work: str | Path, filename: str) -> Path | None:
    """Only exact configured Source roots and their known `content` child.

    Never recursively search siblings, a previous job, or any unrelated Source.
    Two different matching files are ambiguous and must not be auto-selected.
    """
    name = _filename(filename)
    root = Path(work).resolve(strict=True)
    if not root.is_dir():
        raise XmlEvidenceError('Valgt Work-katalog finnes ikke')
    choices: list[Path] = []
    for source in _job_sources(root):
        if source.is_file():
            if source.name.casefold() == name.casefold() and not source.is_symlink():
                choices.append(source)
            continue
        if not source.is_dir():
            continue
        for folder in (source, source / 'content'):
            if not folder.is_dir() or folder.is_symlink():
                continue
            candidate = folder / name
            if candidate.is_symlink() or not candidate.is_file():
                continue
            try:
                real = candidate.resolve(strict=True)
                if real.is_relative_to(folder.resolve(strict=True)):
                    choices.append(real)
            except (OSError, ValueError, RuntimeError):
                continue
    distinct: list[Path] = []
    for choice in choices:
        try:
            if not any(choice.samefile(existing) for existing in distinct):
                distinct.append(choice)
        except OSError:
            continue
    if len(distinct) > 1:
        raise XmlEvidenceError('Flere ulike XML-kilder i registrert Source; velg entydig Source-jobb')
    return distinct[0] if distinct else None


def _file_hash(path: Path, cancelled: Callable[[], bool] | None) -> str:
    digest = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            _check_cancel(cancelled)
            digest.update(block)
    return digest.hexdigest()


def _signature(path: Path) -> tuple[int, int, int, int]:
    stat = path.stat()
    return (stat.st_size, stat.st_mtime_ns, stat.st_dev, stat.st_ino)


def _excerpt(path: Path, line: int, *, cancelled: Callable[[], bool] | None) -> str:
    previous: deque[tuple[int, str]] = deque(maxlen=10)
    following: list[tuple[int, str]] = []
    total_bytes = 0
    with path.open('rb') as stream:
        for number, raw in enumerate(stream, 1):
            if number % 4096 == 0:
                _check_cancel(cancelled)
            total_bytes += len(raw)
            if total_bytes > MAX_SCAN_BYTES:
                raise XmlEvidenceError('XML er for stor for sikker, avgrenset linjevisning')
            if number > line + 10:
                break
            if number < line - 10:
                continue
            if len(raw) > MAX_LINE_BYTES:
                value = '[XML-linjen overstiger grensen for lesbar forhåndsvisning]'
            else:
                value = raw.decode('utf-8-sig', errors='replace').rstrip('\r\n')
            (previous if number < line else following).append((number, value))
    _check_cancel(cancelled)
    if not following or following[0][0] != line:
        raise XmlEvidenceError(f'XML mangler dokumentert linje {line}')
    return '\n'.join(('> ' if n == line else '  ') + f'{n:>9}: {value}'
                     for n, value in (*previous, *following))


def _context_at_line(source: Path, line: int, *, cancelled: Callable[[], bool] | None) -> dict:
    """Bounded lxml iterparse: concrete path and observed ancestors only.

    Counts are preceding sibling ordinals, never a guessed total. Multiple
    elements starting on one source line make the line-to-XPath mapping
    ambiguous; the candidate must not be presented as an exact XPath.
    """
    from lxml import etree
    frames: list[dict] = []
    selected: tuple[dict, ...] = ()
    scope: dict | None = None
    candidate_count = 0
    after_hit = 0
    truncated = False
    selected_value = ''
    event_count = 0
    with source.open('rb') as stream:
        try:
            events = etree.iterparse(stream, events=('start', 'end'),
                                      resolve_entities=False, load_dtd=False,
                                      no_network=True, huge_tree=False)
            for event, node in events:
                event_count += 1
                if event_count % 8192 == 0:
                    _check_cancel(cancelled)
                if len(frames) > MAX_DEPTH:
                    raise XmlEvidenceError('XML-hierarkiet overskrider sikker dybde')
                if not isinstance(node.tag, str):
                    continue
                tag = etree.QName(node).localname
                if event == 'start':
                    ordinal = 1
                    if frames:
                        counts = frames[-1]['children']
                        ordinal = counts.get(tag, 0) + 1
                        counts[tag] = ordinal
                    frame = {'name': tag, 'ordinal': ordinal, 'line': node.sourceline or 0,
                             'children': {}, 'system_id': '', 'title': ''}
                    frames.append(frame)
                    if node.sourceline == line:
                        candidate_count += 1
                        if len(frames) >= len(selected):
                            selected = tuple(frames)
                            scope = next((f for f in reversed(frames) if f['name'] in ARCHIVE_CHAIN), frames[-1])
                            after_hit = 0
                    if selected:
                        after_hit += 1
                else:
                    if selected and frames[-1] is selected[-1]:
                        selected_value = (node.text or '').strip()[:1000]
                    if tag in ('systemID', 'tittel', 'arkivskaperNavn') and len(frames) > 1:
                        value = (node.text or '').strip()[:240]
                        parent = frames[-2]
                        if tag == 'systemID':
                            parent['system_id'] = value
                        elif tag == 'tittel':
                            parent['title'] = value
                    if selected:
                        after_hit += 1
                    closing_scope = scope is not None and frames[-1] is scope
                    frames.pop()
                    node.clear()
                    while node.getprevious() is not None:
                        del node.getparent()[0]
                    if closing_scope:
                        break
                if after_hit and after_hit >= MAX_POST_EVENTS:
                    truncated = True
                    break
        except etree.XMLSyntaxError as exc:
            raise XmlEvidenceError('Original XML kan ikke tolkes trygt: ' + str(exc)) from exc
        finally:
            if 'events' in locals():
                del events
    if not selected:
        return {'xpath': '', 'hierarchy': [], 'selected': '', 'ambiguous': False,
                'note': 'Ingen entydig starttagg på angitt linje; XPath og objekt-ID er ikke verifisert.'}
    levels = [{
        'element': item['name'], 'position': item['ordinal'],
        'total_siblings': None,
        'system_id': item['system_id'], 'title': item['title'],
        'line': item['line'], 'selected': i == len(selected) - 1,
    } for i, item in enumerate(selected)]
    ambiguous = candidate_count > 1
    return {
        'xpath': '' if ambiguous else '/' + '/'.join(f"{item['name']}[{item['ordinal']}]" for item in selected),
        'hierarchy': ([] if ambiguous else [row for row in levels if row['element'] in ARCHIVE_CHAIN or row['selected']]),
        'selected': selected[-1]['name'], 'element': selected[-1]['name'],
        'xml_value': '' if ambiguous else selected_value,
        'system_id': '' if ambiguous else next((f['system_id'] for f in reversed(selected) if f['system_id']), ''),
        'title': '' if ambiguous else next((f['title'] for f in reversed(selected) if f['title']), ''),
        'ambiguous': ambiguous,
        'note': ('Flere XML-elementer begynner på samme linje; eksakt XPath kan ikke fastslås.'
                 if ambiguous else ('Delvis lest objekt (sikker prosesseringsgrense); manglende felt er ikke null.'
                                    if truncated else 'Faktisk hierarki fra nåværende Source; søskentotal er ukjent.')),
        'context_complete': not truncated,
    }


def inspect_xml_anchor(work: str | Path, anchor: dict, *,
                       cancelled: Callable[[], bool] | None = None) -> dict:
    """Inspect precisely one documented source XML line, without editing Source."""
    if not isinstance(anchor, dict):
        raise XmlEvidenceError('Mangler dokumentert XML-anker')
    line = anchor.get('line')
    if type(line) is not int or not 1 <= line <= MAX_LINE:
        raise XmlEvidenceError('Ingen gyldig dokumentert XML-linje')
    filename = _filename(anchor.get('file'))
    expected = str(anchor.get('source_xml_sha256') or '').strip().lower()
    if expected and not re.fullmatch(r'[a-f0-9]{64}', expected):
        raise XmlEvidenceError('Ugyldig oppgitt XML-kildehash')
    source = resolve_source_xml(work, filename)
    if source is None:
        return {'available': False, 'line': line, 'source_path': None,
                'message': 'Original ' + filename + ' er ikke tilgjengelig i den valgte jobbens registrerte Source. '
                           'Funnets opprinnelige kildehenvisning beholdes i Work.'}
    before = _signature(source)
    digest = _file_hash(source, cancelled) if expected else None
    if expected and digest != expected:
        raise XmlEvidenceError('Source XML har endret SHA-256 siden funnets kildebelegg ble lagret')
    excerpt = _excerpt(source, line, cancelled=cancelled)
    context = _context_at_line(source, line, cancelled=cancelled)
    # An anchor with several start tags on the *same* physical line cannot
    # certify which node the reporting tool meant, even when the streaming
    # parser stopped at the first enclosing object boundary.
    selected_excerpt = next((part.split(': ', 1)[1] for part in excerpt.splitlines()
                             if part.startswith('> ') and ': ' in part), '')
    if len(re.findall(r'<\s*(?![!?/])[A-Za-z_][\w.:-]*(?=[\s/>])', selected_excerpt)) > 1:
        context['xpath'] = ''
        context['hierarchy'] = []
        context['ambiguous'] = True
        context['xml_value'] = ''
        context['system_id'] = ''
        context['title'] = ''
        context['note'] = 'Flere starttagger på dokumentert XML-linje; entydig XPath kan ikke fastslås.'
    _check_cancel(cancelled)
    if _signature(source) != before:
        raise XmlEvidenceError('Source XML ble endret under inspeksjonen')
    if expected and _file_hash(source, cancelled) != expected:
        raise XmlEvidenceError('Source XML ble endret under inspeksjonen (SHA-256)')
    return {
        'available': True, 'source_path': str(source), 'line': line,
        'excerpt': excerpt, 'metadata': context,
        'source_identity': 'sha256_verified' if expected else 'not_attested',
        'expected_source_sha256': expected or None,
        'reported_xpath': str(anchor.get('reported_xpath') or ''),
        'reported_object_id': str(anchor.get('object_id') or ''),
        'reported_archive_part_id': str(anchor.get('archive_part_id') or ''),
        'provenance_note': ('SHA-256 samsvarer med dokumentert XML-kilde.' if expected else
                            'Nåværende Source er lest, men byteidentitet mot opprinnelig kontroll er IKKE dokumentert.'),
    }
