"""DWM v0.2.7-a6: source-bound document-file format view and selected-copy.

This is a projection of a *completed, Work-owned* DWM/Siegfried run.
It cannot run tests, authorize a Noark 5 deposit, or modify Source evidence.
All file paths and totals must originate from the same verified inventory/raw pair.
"""
from __future__ import annotations

from collections import Counter
from contextlib import closing
from functools import lru_cache
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable
import csv
import json
import os
import re
import shutil
import sqlite3
import stat
import tempfile
from uuid import uuid4

MODEL = 'dwm.noark5.document-formats.v027-a6.v1'
INDEX_DIR = 'noark5_evidence/document_formats_v027_a6'
RUNS = 'external_evidence/siegfried'
MAX_CONTROL_BYTES = 2_000_000
MAX_LINE_BYTES = 2_000_000
MAX_DOC_FILES = 30_000_000
MAX_PAGE = 250
PSEUDO = {'__unidentified__': 'Uidentifisert', '__ambiguous__': 'Flertydig',
          '__error__': 'Identifikasjonsfeil'}
KNOWN_PUID = re.compile(r'(?:fmt|x-fmt)/\d+\Z', re.IGNORECASE)
HEX_SHA = re.compile(r'[a-f0-9]{64}\Z')


class DocumentWorkbenchError(ValueError):
    pass


def _sha(path: Path) -> str:
    digest = sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _linked(path: Path) -> bool:
    return path.is_symlink() or bool(getattr(path, 'is_junction', lambda: False)())


def _safe_file(root: Path, relative: str) -> Path:
    if (not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative
            or '\x00' in relative or relative.startswith('/') or len(relative) > 2048):
        raise DocumentWorkbenchError('Ugyldig relativ dokumentfilsti')
    parts = relative.split('/')
    if any(not p or p in ('.', '..') for p in parts):
        raise DocumentWorkbenchError('Dokumentstien kan ikke gå ut av registrert Source')
    candidate = root
    for part in parts:
        candidate = candidate / part
        if _linked(candidate):
            raise DocumentWorkbenchError('Dokumentsti går gjennom symbolsk lenke eller junction')
    if not candidate.resolve(strict=False).is_relative_to(root):
        raise DocumentWorkbenchError('Dokumentsti peker utenfor registrert Source')
    return candidate


def _same_source_filename(reported: object, expected: Path) -> bool:
    """Match a Siegfried filename to the exact inventoried file, not its spelling.

    On Windows the same file may be named through a junction, a short path or
    an alternate canonical spelling.  Comparing normcase(string) is therefore
    not a reliable identity test.  Both paths must resolve to the *same path*;
    a different hard link to the same inode is not the inventoried filename.
    """
    if (not isinstance(reported, str) or not reported or '\x00' in reported
            or len(reported) > 32767):
        return False
    raw_path = Path(reported)
    if not raw_path.is_absolute():
        return False
    try:
        return (raw_path.resolve(strict=True) == expected.resolve(strict=True)
                and raw_path.is_file() and expected.is_file())
    except (OSError, ValueError, RuntimeError):
        return False


def _json(path: Path, max_bytes: int = MAX_CONTROL_BYTES) -> dict:
    if _linked(path) or not path.is_file() or path.stat().st_size > max_bytes:
        raise DocumentWorkbenchError('Mangler sikker kontrollfil: ' + path.name)
    try:
        result = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError, UnicodeError) as exc:
        raise DocumentWorkbenchError('Uleselig kontrollfil: ' + path.name) from exc
    if not isinstance(result, dict):
        raise DocumentWorkbenchError('Kontrollfilen må inneholde et objekt: ' + path.name)
    return result


def _work(snapshot: Any) -> tuple[Path, Path, str, str]:
    from app.noark_object_browser_v027_a5 import _root
    root, report, uid = _root(snapshot)
    return root, report, uid, _sha(report)


def _source_root(work: Path, raw: str) -> Path:
    """Bind a completed Siegfried run to the SAME Work/job.json Source.

    Read the persisted job definition directly.  Importing a separate XML
    evidence reader here made this identity check depend on module state in a
    large Windows unittest run; the Work job is the authoritative source.
    Never fall back to a sibling job, prior run or guessed Source directory.
    """
    if not isinstance(raw, str) or not raw:
        raise DocumentWorkbenchError('Siegfried mangler registrert Source')
    path = Path(raw)
    if not path.is_absolute() or _linked(path) or not path.is_dir():
        raise DocumentWorkbenchError('Siegfried sin Source er ikke tilkoblet eller sikker')
    root = path.resolve(strict=True)
    definition = _json(work / 'job.json')
    if definition.get('file_type') != 'dwm-work-job':
        raise DocumentWorkbenchError('Work har ugyldig jobbdefinisjon')
    job = definition.get('job')
    if not isinstance(job, dict):
        raise DocumentWorkbenchError('Work mangler registrerte Source-felt')
    for key in ('source_extraction', 'source_unzipped', 'source_root'):
        recorded = job.get(key)
        if not isinstance(recorded, str) or not recorded.strip():
            continue
        candidate = Path(recorded)
        if not candidate.is_absolute() or _linked(candidate):
            continue
        try:
            registered = candidate.resolve(strict=True)
            if registered.is_file():
                registered = registered.parent
            if registered == root:
                return root
        except (OSError, ValueError, RuntimeError):
            continue
    raise DocumentWorkbenchError('Siegfried-kilden tilhører ikke valgt Work-jobb')


def _run(snapshot: Any) -> dict:
    """Choose newest completed SAME-JOB run; never look at .partial-* files."""
    work, report, uid, report_sha = _work(snapshot)
    folder = work / RUNS
    if _linked(work / 'external_evidence') or _linked(folder) or not folder.is_dir():
        raise DocumentWorkbenchError('Ingen komplett DWM/Siegfried-kjøring i valgt Work')
    candidates = sorted((p for p in folder.iterdir() if p.is_dir() and not _linked(p)
                         and not p.name.startswith('.')), reverse=True)
    for candidate in candidates[:150]:
        try:
            manifest = _json(candidate / 'manifest.json')
        except (DocumentWorkbenchError, OSError):
            # Unknown directories cannot supply file-level evidence.
            continue
        if manifest.get('file_type') != 'dwm-siegfried-run' or manifest.get('job_uid') != uid:
            continue
        # Once the newest matching completed run is found, it is authoritative.
        # Never silently use a stale older run when this run is incomplete,
        # disconnected, or has a contradictory source/manifest.
        if (manifest.get('run_id') != candidate.name
                or manifest.get('raw_file') != 'siegfried_files.jsonl'):
            raise DocumentWorkbenchError('Nyeste Siegfried-kjøring har feil run-ID eller råfilreferanse')
        total = manifest.get('files_total')
        if type(total) is not int or total < 0 or total > MAX_DOC_FILES:
            raise DocumentWorkbenchError('Nyeste Siegfried-kjøring har ugyldig filantall')
        digest = str(manifest.get('raw_sha256') or '').lower()
        inventory_sha = str(manifest.get('inventory_sha256') or '').lower()
        if not HEX_SHA.fullmatch(digest) or not HEX_SHA.fullmatch(inventory_sha):
            raise DocumentWorkbenchError('Nyeste Siegfried-kjøring mangler gyldige kildehasher')
        raw = candidate / 'siegfried_files.jsonl'
        inventory = candidate / 'file_inventory.jsonl'
        if any(_linked(p) or not p.is_file() for p in (raw, inventory)):
            raise DocumentWorkbenchError('Nyeste Siegfried-kjøring mangler komplett råinventar')
        root = _source_root(work, str(manifest.get('source_root') or ''))
        return dict(work=work, report=report, uid=uid, report_sha=report_sha,
                    folder=candidate, source=root, manifest=manifest,
                    raw=raw, inventory=inventory, raw_sha=digest,
                    inventory_sha=inventory_sha, total=total)
    raise DocumentWorkbenchError('Ingen komplett, identitetsmatchende DWM/Siegfried-kjøring i valgt Work')


def _registry_folder(work: Path) -> Path:
    parent = work / 'noark5_evidence'
    target = work / INDEX_DIR
    for path in (parent, target):
        if _linked(path) or (path.exists() and not path.is_dir()):
            raise DocumentWorkbenchError('Utrygg Work-katalog for dokumentindeksen')
        path.mkdir(exist_ok=True)
    return target


def _raw_record(item: dict) -> tuple[str, str, str, str]:
    if not isinstance(item, dict) or not isinstance(item.get('matches'), (list, type(None))):
        raise DocumentWorkbenchError('Ugyldig Siegfried-filoppføring')
    if item.get('errors'):
        return '__error__', PSEUDO['__error__'], '', 'error'
    matches = [x for x in (item.get('matches') or []) if isinstance(x, dict)
               and KNOWN_PUID.fullmatch(str(x.get('id') or ''))]
    if len(matches) > 1:
        return '__ambiguous__', PSEUDO['__ambiguous__'], '', 'ambiguous'
    if not matches:
        return '__unidentified__', PSEUDO['__unidentified__'], '', 'unidentified'
    match = matches[0]
    return str(match['id']).casefold(), str(match.get('format') or '')[:300], \
        str(match.get('version') or '')[:100], 'identified'


def _normalized_ref(raw: str) -> str:
    """No basename guessing: require an explicit relative path under DOKUMENT."""
    if not isinstance(raw, str):
        return ''
    value = raw.strip().replace('\\', '/')
    while value.startswith('./'):
        value = value[2:]
    if (not value or value.startswith('/') or ':' in value or '\x00' in value
            or len(value) > 2048):
        return ''
    parts = value.split('/')
    if any(x in ('', '.', '..') for x in parts):
        return ''
    # A bare filename or URL is never sufficient to assign an archive part.
    if len(parts) < 2 or parts[0].casefold() != 'dokument':
        return ''
    return value.casefold()


def _map_document_objects(conn: sqlite3.Connection, snapshot: Any,
                          source_root: Path, *, cancelled=None) -> dict:
    """Optional actual XML object->file mapping; never infer from folder name."""
    from app.ks_xml_evidence_v023_a19 import resolve_source_xml
    from app.noark_object_browser_v027_a5 import _expected_source_sha
    from lxml import etree
    xml = resolve_source_xml(snapshot.work, 'arkivstruktur.xml')
    if xml is None or _linked(xml) or not xml.is_file():
        return {'state': 'not_available', 'reason': 'arkivstruktur.xml er ikke tilgjengelig'}
    expected = _expected_source_sha(snapshot)
    if not expected:
        return {'state': 'not_attested', 'reason': 'Work har ikke kildehash for arkivstruktur.xml'}
    if _sha(xml) != expected:
        return {'state': 'sha_mismatch', 'reason': 'arkivstruktur.xml samsvarer ikke med Work-evidens'}
    conn.execute('CREATE TABLE xml_refs (rel TEXT PRIMARY KEY, part_id TEXT NOT NULL, '
                 'object_id TEXT NOT NULL, description_id TEXT NOT NULL, '
                 'line INTEGER NOT NULL, ambiguous INTEGER NOT NULL)')
    frames: list[dict] = []
    event_count = 0
    mapped = duplicates = 0
    try:
        with xml.open('rb') as stream:
            for event, element in etree.iterparse(stream, events=('start', 'end'),
                                                  resolve_entities=False, load_dtd=False,
                                                  no_network=True, huge_tree=False):
                event_count += 1
                if event_count % 8192 == 0 and cancelled and cancelled():
                    raise DocumentWorkbenchError('Avbrutt under dokumentkobling')
                name = element.tag.rsplit('}', 1)[-1] if isinstance(element.tag, str) else ''
                if event == 'start':
                    if len(frames) >= 128:
                        raise DocumentWorkbenchError('For dyp XML-struktur')
                    frames.append({'name': name, 'id': '', 'ref': '', 'line': int(element.sourceline or 0)})
                    continue
                frame = frames[-1]
                if name == 'systemID' and len(frames) >= 2:
                    frames[-2]['id'] = (element.text or '').strip()[:500]
                if name == 'referanseDokumentfil' and len(frames) >= 2:
                    frames[-2]['ref'] = (element.text or '').strip()
                if name == 'dokumentobjekt':
                    rel = _normalized_ref(frame['ref'])
                    part = next((x['id'] for x in reversed(frames[:-1])
                                 if x['name'] == 'arkivdel'), '')
                    desc = next((x['id'] for x in reversed(frames[:-1])
                                 if x['name'] == 'dokumentbeskrivelse'), '')
                    if rel and part:
                        old = conn.execute('SELECT ambiguous FROM xml_refs WHERE rel=?', (rel,)).fetchone()
                        if old:
                            duplicates += 1
                            conn.execute('UPDATE xml_refs SET ambiguous=1 WHERE rel=?', (rel,))
                        else:
                            conn.execute('INSERT INTO xml_refs VALUES (?,?,?,?,?,0)',
                                         (rel, part, frame['id'], desc, frame['line']))
                            mapped += 1
                frames.pop()
                element.clear()
                if element.getparent() is not None:
                    while element.getprevious() is not None:
                        del element.getparent()[0]
    except etree.XMLSyntaxError as exc:
        raise DocumentWorkbenchError('Kan ikke lese komplett XML for arkivdelkobling') from exc
    if frames or _sha(xml) != expected:
        raise DocumentWorkbenchError('Kilden ble endret eller XML var ufullstendig')
    return {'state': 'work_sha256_verified', 'mapped_references': mapped,
            'ambiguous_references': duplicates, 'xml_sha256': expected}


def _publish_manifest(folder: Path, path: Path, meta: dict) -> None:
    temporary = folder / ('.a6-' + uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as out:
            json.dump(meta, out, ensure_ascii=False, indent=2)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def build_document_index(snapshot: Any, *, cancelled: Callable[[], bool] | None = None,
                         progress: Callable[[int], None] | None = None,
                         reuse: bool = True) -> dict:
    run = _run(snapshot)
    if reuse:
        prior = find_document_index(snapshot)
        if prior and prior.get('run_id') == run['manifest']['run_id']:
            return prior
    folder = _registry_folder(run['work'])
    fd, temporary = tempfile.mkstemp(prefix='.a6-', suffix='.sqlite', dir=folder)
    os.close(fd)
    stage = Path(temporary)
    db = None
    published = None
    try:
        db = sqlite3.connect(stage)
        db.execute('PRAGMA journal_mode=DELETE')
        db.execute('PRAGMA synchronous=FULL')
        db.execute('CREATE TABLE files (id INTEGER PRIMARY KEY, rel TEXT NOT NULL, '
                   'puid TEXT NOT NULL, fmt TEXT NOT NULL, version TEXT NOT NULL, '
                   'ident_state TEXT NOT NULL, size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL, '
                   'part_id TEXT NOT NULL, doc_id TEXT NOT NULL, description_id TEXT NOT NULL, '
                   'xml_line INTEGER NOT NULL, search TEXT NOT NULL)')
        db.execute('CREATE INDEX files_by_format ON files(puid,id)')
        db.execute('CREATE INDEX files_by_part ON files(part_id,puid,id)')
        # XML mapping is optional, but if it is claimed as verified it must be complete.
        mapping = _map_document_objects(db, snapshot, run['source'], cancelled=cancelled)
        counts: Counter = Counter()
        raw_hash, inventory_hash = sha256(), sha256()
        total = 0
        with run['raw'].open('rb') as raw, run['inventory'].open('rb') as inventory:
            while True:
                raw_line = raw.readline(MAX_LINE_BYTES + 1)
                inventory_line = inventory.readline(MAX_LINE_BYTES + 1)
                if not raw_line and not inventory_line:
                    break
                if (not raw_line or not inventory_line or len(raw_line) > MAX_LINE_BYTES
                        or len(inventory_line) > MAX_LINE_BYTES):
                    raise DocumentWorkbenchError('Siegfried-inventar og filresultater er ufullstendige')
                raw_hash.update(raw_line)
                inventory_hash.update(inventory_line)
                try:
                    result = json.loads(raw_line)
                    reference = json.loads(inventory_line)
                except (ValueError, UnicodeError) as exc:
                    raise DocumentWorkbenchError('Uleselig Siegfried-filhendelse') from exc
                if not isinstance(result, dict) or not isinstance(reference, dict):
                    raise DocumentWorkbenchError('Ugyldig filregistrering')
                rel = reference.get('path')
                if (not isinstance(rel, str) or type(reference.get('size')) is not int
                        or type(reference.get('mtime_ns')) is not int
                        or reference['size'] < 0 or reference['mtime_ns'] < 0):
                    raise DocumentWorkbenchError('Ugyldig filinventar')
                expected = _safe_file(run['source'], rel)
                # The native sf path may use a different spelling/alias than
                # the canonical Source path on Windows.  Resolve both; never
                # accept a different document that merely shares a basename or
                # file contents (including a distinct hard link).
                if not _same_source_filename(result.get('filename'), expected):
                    raise DocumentWorkbenchError('Siegfried-resultat og filinventar viser ulike filer')
                puid, fmt, version, state = _raw_record(result)
                part = doc_id = desc = ''
                xml_line = 0
                if mapping['state'] == 'work_sha256_verified':
                    ref = db.execute('SELECT part_id,object_id,description_id,line,ambiguous '
                                     'FROM xml_refs WHERE rel=?', (rel.casefold(),)).fetchone()
                    if ref and not ref[4]:
                        part, doc_id, desc, xml_line = ref[:4]
                search = ' '.join((rel, puid, fmt, version, part, doc_id)).casefold()
                db.execute('INSERT INTO files (rel,puid,fmt,version,ident_state,size,mtime_ns,'
                           'part_id,doc_id,description_id,xml_line,search) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                           (rel, puid, fmt, version, state, reference['size'],
                            reference['mtime_ns'], part, doc_id, desc, xml_line, search))
                counts[puid] += 1
                total += 1
                if total > MAX_DOC_FILES:
                    raise DocumentWorkbenchError('Dokumentindeksen er for stor')
                if total % 1000 == 0:
                    if cancelled and cancelled():
                        raise DocumentWorkbenchError('Dokumentindeksering avbrutt')
                    if progress:
                        progress(total)
        if (total != run['total'] or raw_hash.hexdigest() != run['raw_sha']
                or inventory_hash.hexdigest() != run['inventory_sha']):
            raise DocumentWorkbenchError('Siegfried-raw/inventar stemmer ikke med fullført kjøringsmanifest')
        if cancelled and cancelled():
            raise DocumentWorkbenchError('Dokumentindeksering avbrutt')
        if db is not None:
            linked_files = db.execute("SELECT count(*) FROM files WHERE part_id<>''").fetchone()[0]
            db.execute('DROP TABLE IF EXISTS xml_refs')
            db.commit()
            db.close()
            db = None
        digest = _sha(stage)
        key = uuid4().hex
        destination = folder / (key + '.sqlite')
        meta = {
            'model_id': MODEL, 'complete': True,
            'job_uid': run['uid'], 'report_sha256': run['report_sha'],
            'run_id': run['manifest']['run_id'], 'run_raw_sha256': run['raw_sha'],
            'run_inventory_sha256': run['inventory_sha'], 'source_root': str(run['source']),
            'index_relative_path': INDEX_DIR + '/' + destination.name,
            'index_sha256': digest, 'index_size': stage.stat().st_size,
            'index_mtime_ns': stage.stat().st_mtime_ns, 'files_total': total,
            'formats_total': len(counts), 'by_puid': dict(sorted(counts.items())),
            'linked_files': linked_files, 'unlinked_files': total - linked_files,
            'xml_mapping': mapping, 'automatic_approval': False,
        }
        os.replace(stage, destination)
        published = destination
        _publish_manifest(folder, destination.with_suffix('.json'), meta)
        if progress:
            progress(total)
        return meta
    except (OSError, sqlite3.Error, UnicodeError) as exc:
        raise DocumentWorkbenchError('Kunne ikke bygge dokumentindeks: ' + str(exc)) from exc
    finally:
        if db is not None:
            db.close()
        stage.unlink(missing_ok=True)
        if published is not None and not published.with_suffix('.json').is_file():
            published.unlink(missing_ok=True)


def _checked_db(snapshot: Any, meta: dict, *, digest: bool = False) -> Path:
    work, report, uid, report_sha = _work(snapshot)
    if (not isinstance(meta, dict) or meta.get('model_id') != MODEL
            or meta.get('complete') is not True or meta.get('job_uid') != uid
            or meta.get('report_sha256') != report_sha):
        raise DocumentWorkbenchError('Dokumentregisteret tilhører en annen jobb/rapport')
    rel = meta.get('index_relative_path')
    if (not isinstance(rel, str) or not re.fullmatch(
            r'noark5_evidence/document_formats_v027_a6/[a-f0-9]{32}\.sqlite', rel)):
        raise DocumentWorkbenchError('Ugyldig dokumentregisterreferanse')
    db = work / rel
    manifest = db.with_suffix('.json')
    if (any(_linked(p) for p in (work / 'noark5_evidence', db.parent, db, manifest))
            or not db.is_file() or not manifest.is_file()
            or manifest.stat().st_size > MAX_CONTROL_BYTES):
        raise DocumentWorkbenchError('Dokumentregister eller manifest mangler')
    if _json(manifest) != meta:
        raise DocumentWorkbenchError('Dokumentmanifest er endret')
    stat_ = db.stat()
    if stat_.st_size != meta.get('index_size') or stat_.st_mtime_ns != meta.get('index_mtime_ns'):
        raise DocumentWorkbenchError('Dokumentindeksen er endret')
    if digest and _sha(db) != meta.get('index_sha256'):
        raise DocumentWorkbenchError('Dokumentindeks har endret SHA-256')
    return db


def find_document_index(snapshot: Any) -> dict | None:
    try:
        work, _, uid, report_sha = _work(snapshot)
        folder = work / INDEX_DIR
        if _linked(folder) or not folder.is_dir():
            return None
        for candidate in sorted(folder.glob('*.json'), reverse=True)[:100]:
            try:
                if _linked(candidate) or not re.fullmatch(r'[a-f0-9]{32}\.json', candidate.name):
                    continue
                meta = _json(candidate)
                if meta.get('job_uid') == uid and meta.get('report_sha256') == report_sha:
                    _checked_db(snapshot, meta, digest=True)
                    return meta
            except (OSError, ValueError):
                continue
    except (OSError, ValueError):
        pass
    return None


def _select_files(snapshot: Any, meta: dict, *, puids: Iterable[str] = (),
                  part_id: str = '', search: str = '', status: str = '',
                  limit: int = 100, offset: int = 0) -> dict:
    if (type(limit) is not int or not 1 <= limit <= MAX_PAGE
            or type(offset) is not int or offset < 0
            or not isinstance(search, str) or len(search) > 240):
        raise DocumentWorkbenchError('Ugyldig listefilter')
    selected = tuple(dict.fromkeys(puids))
    if len(selected) > 900 or any(not isinstance(p, str) or len(p) > 150 for p in selected):
        raise DocumentWorkbenchError('For mange eller ugyldige PUID-filter')
    clauses = []
    args: list[Any] = []
    if selected:
        clauses.append('puid IN (' + ','.join('?' for _ in selected) + ')')
        args.extend(selected)
    if part_id:
        if meta.get('xml_mapping', {}).get('state') != 'work_sha256_verified':
            raise DocumentWorkbenchError('Arkivdelfilter krever kildeverifisert XML-kobling')
        clauses.append('part_id=?')
        args.append(part_id)
    if status:
        clauses.append('ident_state=?')
        args.append(status)
    if search.strip():
        clauses.append('instr(search,?) > 0')
        args.append(search.strip().casefold())
    condition = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
    db = _checked_db(snapshot, meta)
    try:
        with closing(sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)) as conn:
            conn.execute('PRAGMA query_only=ON')
            count = conn.execute('SELECT count(*) FROM files' + condition, args).fetchone()[0]
            rows = [dict(zip(('id','rel','puid','fmt','version','ident_state','size','mtime_ns',
                              'part_id','doc_id','description_id','xml_line'), value))
                    for value in conn.execute('SELECT id,rel,puid,fmt,version,ident_state,size,'
                                              'mtime_ns,part_id,doc_id,description_id,xml_line '
                                              'FROM files' + condition + ' ORDER BY id LIMIT ? OFFSET ?',
                                              (*args, limit, offset))]
        return {'rows': rows, 'total': count, 'complete': True,
                'page': offset // limit, 'pages': (count + limit - 1) // limit}
    except sqlite3.Error as exc:
        raise DocumentWorkbenchError('Kan ikke lese dokumentoversikt') from exc


def file_page(snapshot: Any, meta: dict, *, puids: Iterable[str] = (), part_id: str = '',
              search: str = '', status: str = '', page: int = 0, page_size: int = 100) -> dict:
    if type(page) is not int or page < 0:
        raise DocumentWorkbenchError('Ugyldig sidenummer')
    return _select_files(snapshot, meta, puids=puids, part_id=part_id, search=search,
                         status=status, limit=page_size, offset=page * page_size)


def format_groups(snapshot: Any, meta: dict, part_id: str = '') -> tuple[dict, ...]:
    db = _checked_db(snapshot, meta)
    try:
        with closing(sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)) as conn:
            conn.execute('PRAGMA query_only=ON')
            if part_id:
                if meta.get('xml_mapping', {}).get('state') != 'work_sha256_verified':
                    raise DocumentWorkbenchError('Ingen verifisert arkivdeltilordning')
                where, args = ' WHERE part_id=?', (part_id,)
            else:
                where, args = '', ()
            return tuple({'puid': row[0], 'name': row[1], 'version': row[2], 'count': row[3]}
                         for row in conn.execute('SELECT puid, min(fmt), min(version), count(*) '
                                                 'FROM files' + where +
                                                 ' GROUP BY puid ORDER BY count(*) DESC, puid', args))
    except sqlite3.Error as exc:
        raise DocumentWorkbenchError('Kan ikke lese filformatene') from exc


def _assessment_target(meta: dict, puid: str) -> str:
    return 'analysis-a6:' + json.dumps([meta['run_raw_sha256'], puid],
                                        ensure_ascii=False, separators=(',', ':'))


def format_annotations(snapshot: Any, meta: dict, puid: str) -> tuple[dict, ...]:
    from noark5_workflow.analysis.depot_annotations import list_depot_annotations
    _checked_db(snapshot, meta)
    return tuple(list_depot_annotations(snapshot.report_path, view_id='analysis',
                 target_id=_assessment_target(meta, puid)))


def latest_assessment(snapshot: Any, meta: dict, puid: str) -> str:
    notes = format_annotations(snapshot, meta, puid)
    for note in reversed(notes):
        target_type = str((note.get('target') or {}).get('target_type') or '')
        if target_type.startswith('format_assessment_'):
            value = target_type[len('format_assessment_'):]
            if value in ('accepted', 'deviation', 'clarify'):
                return value
    return ''


def save_format_annotation(snapshot: Any, meta: dict, puid: str, *,
                           assessment: str, kind: str, text: str, user: Any) -> dict:
    """A6 append-only professional *review*, not a technical test rewrite."""
    from noark5_workflow.analysis.depot_annotations import record_depot_annotation
    if not puid or puid not in meta.get('by_puid', {}):
        raise DocumentWorkbenchError('Filtypen finnes ikke i dette uttrekket')
    if assessment not in ('', 'accepted', 'deviation', 'clarify'):
        raise DocumentWorkbenchError('Ukjent faglig formatstatus')
    if kind not in ('note', 'deviation', 'question', 'follow_up', 'accepted_deviation'):
        raise DocumentWorkbenchError('Ukjent merknadstype')
    if not str(text or '').strip():
        raise DocumentWorkbenchError('Begrunnelse eller merknad kan ikke være tom')
    _checked_db(snapshot, meta, digest=True)
    report = Path(snapshot.report_path)
    if _linked(report.with_name('depot_annotations.json')):
        raise DocumentWorkbenchError('Kommentarregister kan ikke være en symbolsk lenke')
    target_type = 'format_assessment_' + assessment if assessment else 'format_note'
    if assessment == 'deviation':
        kind = 'deviation'
    return record_depot_annotation(
        report, annotation_type=kind, text=text.strip(), user=user, view_id='analysis',
        target_type=target_type, target_id=_assessment_target(meta, puid),
        target_label='Filformat ' + PSEUDO.get(puid, puid) +
                     (' / faglig vurdering: ' + assessment if assessment else ''))


def arkade_raf_by_puid(work: Path) -> dict[str, str]:
    """Historic Arkade RAF is *aggregate* context, never a per-file fact."""
    folder = work / 'external_evidence' / 'arkade5'
    if not folder.is_dir() or _linked(folder):
        return {}
    result: dict[str, set[str]] = {}
    for entry in list(folder.iterdir())[:250]:
        if not entry.is_dir() or _linked(entry):
            continue
        path = entry / 'normalized' / 'pronom_statistics.json'
        if _linked(path) or not path.is_file() or path.stat().st_size > 16_000_000:
            continue
        try:
            model = _json(path, 16_000_000)
            if model.get('evidence_type') != 'arkade5_pronom_format_statistics':
                continue
            for row in (model.get('csv') or {}).get('rows') or ():
                if not isinstance(row, dict):
                    continue
                puid = str(row.get('Format-ID') or row.get('PUID') or '').casefold()
                if KNOWN_PUID.fullmatch(puid):
                    result.setdefault(puid, set()).add(str(row.get('RAF-220301') or '').strip())
        except (OSError, ValueError, TypeError):
            continue
    return {puid: (next(iter(values)) if len(values) == 1 else 'Motstridende historiske vurderinger')
            for puid, values in result.items()}


@lru_cache(maxsize=1)
def _national_profile():
    from app.format_policy_v0110_a4 import FORMAT_PROFILE_DIR, load_format_policy
    return load_format_policy(FORMAT_PROFILE_DIR / 'nasjonalarkivet_2026-11-10.json')


def format_policy_label(puid: str, source: str, *, raf: dict[str, str] | None = None) -> tuple[str, str]:
    """Use chosen authority from Setup. An external status never approves deposit."""
    from app.format_assessment_v0111_a2 import (
        FORMAT_SOURCE_NASJONALARKIVET, FORMAT_SOURCE_ARKADE_RAF,
        historical_arkade_status,
    )
    if puid in PSEUDO:
        return 'Ikke identifisert entydig', 'PRONOM har ikke en sikker, unik PUID.'
    if source == FORMAT_SOURCE_NASJONALARKIVET:
        from app.format_policy_v0110_a4 import evaluate_puid
        profile = _national_profile()
        decision = evaluate_puid(puid, profile)
        return decision.label, decision.explanation
    if source == FORMAT_SOURCE_ARKADE_RAF:
        value = (raf or {}).get(puid, '')
        if not value:
            return 'Arkade: ukjent', 'Ingen separat historisk RAF-vurdering for PUID i valgt Work.'
        result = historical_arkade_status(value)
        return ('Arkade: ' + result.label,
                'Historisk aggregat-observasjon, ikke resultat for en bestemt Siegfried-fil: ' + value)
    raise DocumentWorkbenchError('Ukjent vurderingsgrunnlag fra Setup')


def _safe_destination(folder: Path, work: Path, source: Path) -> Path:
    if not folder.is_absolute() or not folder.is_dir() or _linked(folder):
        raise DocumentWorkbenchError('Velg en eksisterende, sikker målmappe')
    target = folder.resolve(strict=True)
    if (target == work or target.is_relative_to(work) or work.is_relative_to(target)
            or target == source or target.is_relative_to(source) or source.is_relative_to(target)):
        raise DocumentWorkbenchError('Målmappe kan ikke overlappe Source eller Work')
    return target


def _stream_copy(src: Path, dst: Path, *, cancelled: Callable[[], bool] | None = None) -> str:
    digest = sha256()
    with src.open('rb') as inp, dst.open('xb') as out:
        for block in iter(lambda: inp.read(1024 * 1024), b''):
            if cancelled and cancelled():
                raise DocumentWorkbenchError('Kopiering avbrutt')
            digest.update(block)
            out.write(block)
        out.flush()
        os.fsync(out.fileno())
    if _sha(dst) != digest.hexdigest():
        raise DocumentWorkbenchError('Verifikasjon av kopiert fil feilet')
    return digest.hexdigest()


def copy_selected_files(snapshot: Any, meta: dict, *, selected_puids: Iterable[str],
                        destination: Path | str, structure: str = 'puid',
                        part_id: str = '', cancelled: Callable[[], bool] | None = None,
                        progress: Callable[[int, int], None] | None = None) -> dict:
    """Transactional copy into a NEW subdirectory under the selected output.

    No overwrites, no moves, no Source writes, no false 'all done' on missing files.
    A manifest with each actual Source and output SHA-256 is published last.
    """
    if structure not in ('puid', 'flat'):
        raise DocumentWorkbenchError('Velg flat kopiering eller PUID-undermapper')
    selected = tuple(dict.fromkeys(selected_puids))
    if not selected or any(x not in meta.get('by_puid', {}) for x in selected):
        raise DocumentWorkbenchError('Velg minst én filtype fra den fullførte indeksen')
    run = _run(snapshot)
    if (run['raw_sha'] != meta.get('run_raw_sha256')
            or run['inventory_sha'] != meta.get('run_inventory_sha256')
            or str(run['source']) != meta.get('source_root')):
        raise DocumentWorkbenchError('Siegfried-kjøringen er ikke den som ble indeksert')
    _checked_db(snapshot, meta, digest=True)
    if _sha(run['raw']) != run['raw_sha'] or _sha(run['inventory']) != run['inventory_sha']:
        raise DocumentWorkbenchError('Siegfried-evidens ble endret etter indeksering')
    dest = _safe_destination(Path(destination), run['work'], run['source'])
    db = _checked_db(snapshot, meta)
    keys = ','.join('?' for _ in selected)
    clause = ' WHERE puid IN (' + keys + ')' + (' AND part_id=?' if part_id else '')
    params: tuple = selected + ((part_id,) if part_id else ())
    if part_id:
        info = meta.get('xml_mapping', {})
        if info.get('state') != 'work_sha256_verified':
            raise DocumentWorkbenchError('Arkivdeltilordningen er ikke kildeverifisert')
        from app.ks_xml_evidence_v023_a19 import resolve_source_xml
        xml = resolve_source_xml(snapshot.work, 'arkivstruktur.xml')
        if xml is None or _linked(xml) or _sha(xml) != info.get('xml_sha256'):
            raise DocumentWorkbenchError('XML-kilden er endret; arkivdelutvalget kan ikke kopieres')
    stage = dest / ('.dwm-filutvalg-' + uuid4().hex + '.tmp')
    result = dest / ('DWM-filutvalg-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
                     + '-' + uuid4().hex[:8])
    completed = 0
    try:
        with closing(sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)) as conn:
            conn.execute('PRAGMA query_only=ON')
            total = conn.execute('SELECT count(*) FROM files' + clause, params).fetchone()[0]
            if not total:
                raise DocumentWorkbenchError('Ingen dokumentfiler samsvarer med PUID-/arkivdelvalget')
            stage.mkdir(exist_ok=False)
            manifest = stage / 'kopimanifest.jsonl'
            seen_names: set[str] = set()
            with manifest.open('x', encoding='utf-8', newline='\n') as log:
                cursor = conn.execute('SELECT rel,puid,size,mtime_ns,part_id,doc_id '
                                      'FROM files' + clause + ' ORDER BY id', params)
                for rel, puid, size, mtime, part, obj_id in cursor:
                    if cancelled and cancelled():
                        raise DocumentWorkbenchError('Kopiering avbrutt')
                    source_file = _safe_file(run['source'], rel)
                    if not source_file.is_file():
                        raise DocumentWorkbenchError('Kildedokument mangler: ' + rel)
                    before = source_file.stat(follow_symlinks=False)
                    if (not stat.S_ISREG(before.st_mode) or before.st_size != size
                            or before.st_mtime_ns != mtime):
                        raise DocumentWorkbenchError('Kildedokument er endret etter Siegfried: ' + rel)
                    folder_name = puid.replace('/', '_') if structure == 'puid' else ''
                    output_folder = stage / folder_name if folder_name else stage
                    output_folder.mkdir(exist_ok=True)
                    basename = source_file.name
                    key = (folder_name + '/' + basename).casefold()
                    if key in seen_names or (output_folder / basename).exists():
                        suffix = sha256(rel.encode('utf-8')).hexdigest()[:12]
                        basename = source_file.stem + '_' + suffix + source_file.suffix
                        key = (folder_name + '/' + basename).casefold()
                    if key in seen_names:
                        raise DocumentWorkbenchError('Kollisjon mellom dokumentfilnavn')
                    seen_names.add(key)
                    target = output_folder / basename
                    source_hash = _stream_copy(source_file, target, cancelled=cancelled)
                    after = source_file.stat(follow_symlinks=False)
                    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
                            after.st_size, after.st_mtime_ns, after.st_ino):
                        raise DocumentWorkbenchError('Kildedokument endret seg under kopiering')
                    record = {'source_relative': rel, 'source_path': str(source_file),
                              'output_relative': target.relative_to(stage).as_posix(),
                              'puid': puid, 'archive_part_id': part, 'document_object_id': obj_id,
                              'size': size, 'sha256': source_hash}
                    log.write(json.dumps(record, ensure_ascii=False) + '\n')
                    completed += 1
                    if progress and (completed % 10 == 0 or completed == total):
                        progress(completed, total)
                log.flush()
                os.fsync(log.fileno())
            if completed != total:
                raise DocumentWorkbenchError('Ufullstendig kopiering')
            summary = {'model_id': 'dwm.noark5.document-copy.v027-a6',
                       'work_job_uid': run['uid'], 'report_sha256': run['report_sha'],
                       'source_run_id': meta['run_id'],
                       'selected_puids': list(selected), 'archive_part_id': part_id,
                       'layout': structure, 'files_copied': total,
                       'file_manifest': 'kopimanifest.jsonl',
                       'file_manifest_sha256': _sha(manifest),
                       'note': 'Originalfiler er kopiert og sjekksumverifisert, ikke flyttet.'}
            with (stage / 'sammendrag.json').open('x', encoding='utf-8') as handle:
                json.dump(summary, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(stage, result)
            return {'path': str(result), 'files_copied': total,
                    'manifest': str(result / 'kopimanifest.jsonl')}
    except (OSError, sqlite3.Error) as exc:
        raise DocumentWorkbenchError('Filkopiering feilet: ' + str(exc)) from exc
    finally:
        if stage.exists():
            shutil.rmtree(stage)
