"""Import preserved, same-job Arkade PRONOM output without a Noark report.

Legacy CLI manifests authenticate logs, not the original CSV. The import
records a new CSV digest; it never asserts that the CSV was hashed at run time.
Only Work is read/written. No CLI invocation and no synthetic Noark report.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile

_FIELDS = {'Format-ID', 'Filtype', 'Formatversjon', 'RAF-220301', 'Antall'}
_LIMIT = 16 * 1024 * 1024


def _token(value):
    return str(value or '').replace('\\', '/').rstrip('/').casefold()


def _safe(root, path):
    path = Path(path)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Arkade-evidens peker utenfor Work')
    for item in (path, *path.parents):
        if item == root:
            break
        if item.is_symlink():
            raise ValueError('Symbolsk lenke i Arkade-evidens')
    return path


def _bytes(root, path):
    path = _safe(root, path)
    if not path.is_file() or path.stat().st_size > _LIMIT:
        raise ValueError('Manglende eller for stor Arkade-evidens: ' + str(path.name))
    return path.read_bytes()


def _json(root, path):
    result = json.loads(_bytes(root, path).decode('utf-8-sig'))
    if not isinstance(result, dict):
        raise ValueError('Ugyldig Arkade-manifest')
    return result


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _normalized(raw, name):
    text = raw.decode('utf-8-sig')
    delimiter = csv.Sniffer().sniff(text[:65536], delimiters=',;\t').delimiter
    reader = csv.DictReader(io.StringIO(text, newline=''), delimiter=delimiter)
    if not _FIELDS.issubset(reader.fieldnames or ()) or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError('Ukjente eller dupliserte PRONOM-felt')
    rows = []
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise ValueError('Ufullstendig PRONOM-rad')
        if not row['Format-ID'].strip() or not 0 <= int(row['Antall']) <= 100_000_000:
            raise ValueError('Ugyldig PRONOM-rad')
        rows.append(row)
    if not rows:
        raise ValueError('Tom PRONOM-statistikk')
    return {'format_version': 1, 'evidence_type': 'arkade5_pronom_format_statistics',
            'source_system': 'Arkade 5', 'identification_engine': 'Siegfried / PRONOM',
            'source': {'original_name': name, 'size_bytes': len(raw), 'sha256': _hash(raw)},
            'csv': {'encoding': 'utf-8-sig', 'delimiter': delimiter,
                    'fieldnames': reader.fieldnames, 'row_count': len(rows), 'rows': rows}}


def _immutable(root, path, data):
    path = _safe(root, path)
    if path.exists():
        if _bytes(root, path) != data:
            raise ValueError('Bevart PRONOM-import har endret innhold')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.a20-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # Work is locked by the normal workflow runner. Never overwrite a
        # conflicting historical import, even if another writer appeared.
        try:
            os.link(name, path)
        except FileExistsError:
            if _bytes(root, path) != data:
                raise ValueError('Konflikt i PRONOM-import')
        except OSError:
            # Filesystems without hard links: exclusive creation, no overwrite.
            try:
                with path.open('xb') as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
            except FileExistsError:
                if _bytes(root, path) != data:
                    raise ValueError('Konflikt i PRONOM-import')
    finally:
        Path(name).unlink(missing_ok=True)


def _encode(data):
    return (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def import_preserved_pronom(work, *, job_id, job_uid, expected_run_id=None):
    root = Path(work).resolve(strict=True)
    owner = _json(root, root / 'job.json')
    job = owner.get('job') or {}
    if (owner.get('file_type') != 'dwm-work-job' or owner.get('job_uid') != job_uid
            or job.get('job_id') != job_id or not re.fullmatch(r'[A-Za-z0-9._-]+', job_id)):
        raise ValueError('Arkade PRONOM: Work-identitet stemmer ikke')
    if 'arkade5_pronom_analysis' not in (job.get('workflow_ids') or []):
        return None
    base = root / 'external_runs' / 'arkade5' / job_id / 'pronom_analysis'
    _safe(root, base)
    manifests = sorted(base.glob('*/manifest.json'), reverse=True)
    if not manifests:
        return None
    manifest = manifests[0]
    if expected_run_id is not None and manifest.parent.name != expected_run_id:
        raise ValueError("Arkade PRONOM: siste manifest gjelder ikke forventet kjøring")
    raw_manifest = _bytes(root, manifest)
    data = json.loads(raw_manifest.decode('utf-8-sig'))
    meta = data.get('metadata') or {}
    if (data.get('tool_id') != 'arkade5' or data.get('operation_id') != 'pronom_analysis'
            or data.get('job_id') != job_id or data.get('run_id') != manifest.parent.name
            or data.get('ok') is not True or data.get('exit_code') != 0
            or data.get('cancelled') or data.get('timed_out') or data.get('launch_error')):
        return None
    source = _token(job.get('source_extraction') or job.get('source_root'))
    if not source or _token(meta.get('source_extraction')) != source:
        raise ValueError('Arkade PRONOM: Source stemmer ikke')
    work_token = _token(meta.get('work_operations'))
    if not work_token or work_token not in {_token(root), _token(job.get('work_operations'))}:
        raise ValueError('Arkade PRONOM: Work stemmer ikke')
    original_output = str(meta.get('arkade_output_dir') or '').replace('\\', '/').rstrip('/')
    if not _token(original_output).startswith(work_token + '/'):
        raise ValueError('Arkade PRONOM: output utenfor Work')
    relative = original_output[len(work_token) + 1:]
    parts = relative.split('/')
    if len(parts) != 2 or parts[-1].casefold() != 'pronom' or any(p in ('', '.', '..') or ':' in p for p in parts):
        raise ValueError('Arkade PRONOM: uventet output-layout')
    output = _safe(root, root.joinpath(*parts))
    for kind in ('stdout', 'stderr'):
        log = _bytes(root, manifest.parent / (kind + '.txt'))
        digest = (data.get(kind) or {}).get('sha256_utf8')
        if digest not in {_hash(log), _hash(log.replace(b'\r\n', b'\n'))}:
            raise ValueError('Arkade PRONOM: logghash stemmer ikke')
        if re.search(rb'^\s*\[Error\]|finished with errors', log, re.I | re.M):
            return None
        if kind == 'stdout' and b'successfully finished' not in log.lower():
            return None
    csv_path = output / 'filformatinfo-statistikk.csv'
    if not csv_path.is_file():
        return None
    inventory = _safe(root, output / 'filformatinfo')
    if not inventory.is_file() or inventory.stat().st_size == 0:
        return None
    raw = _bytes(root, csv_path)
    normalized = _normalized(raw, csv_path.name)
    digest = _hash(raw)
    import_id = _hash((job_uid + '|' + data['run_id'] + '|' + digest).encode())
    folder = root / 'external_evidence' / 'arkade5_pronom' / import_id
    preserved = folder / 'source' / csv_path.name
    stat = folder / 'normalized' / 'pronom_statistics.json'
    target_manifest = folder / 'manifest.json'
    rel = lambda p: p.relative_to(root).as_posix()
    normalized['source']['preserved_file'] = rel(preserved)
    payload = _encode(normalized)
    record = {'format_version': 1, 'evidence_type': 'arkade5_pronom_standalone',
              'job_uid': job_uid, 'job_id': job_id, 'run_id': data['run_id'],
              'source_extraction': meta['source_extraction'],
              'tool_version': meta.get('tool_version'),
              'cli_manifest': rel(manifest), 'cli_manifest_sha256': _hash(raw_manifest),
              'source': {'original_file': rel(csv_path), 'preserved_file': rel(preserved),
                         'sha256': digest, 'size_bytes': len(raw)},
              'normalized_file': rel(stat), 'normalized_sha256': _hash(payload),
              'detailed_inventory': {'file': rel(inventory), 'size_bytes': inventory.stat().st_size,
                                     'imported': False},
              'original_csv_hashed_at_cli_run': False, 'depot_approval': None}
    _immutable(root, preserved, raw)
    _immutable(root, stat, payload)
    _immutable(root, target_manifest, _encode(record))
    return {'file': rel(stat), 'sha256': _hash(payload),
            'manifest': rel(target_manifest), 'manifest_sha256': _hash(_encode(record))}


def verify_standalone_reference(work, reference, *, job_id, job_uid):
    """Recheck independent import and its preserved source; no repairs/writes."""
    root = Path(work).resolve(strict=True)
    manifest_path = _safe(root, root / reference['manifest'])
    raw_manifest = _bytes(root, manifest_path)
    manifest = json.loads(raw_manifest.decode('utf-8'))
    if manifest.get('evidence_type') != 'arkade5_pronom_standalone':
        return False
    if (_hash(raw_manifest) != reference['manifest_sha256']
            or manifest.get('job_id') != job_id or manifest.get('job_uid') != job_uid
            or manifest.get('normalized_file') != reference['file']):
        raise ValueError('Selvstendig Arkade PRONOM-manifest stemmer ikke')
    stat_path = _safe(root, root / reference['file'])
    source = manifest['source']
    preserved = _safe(root, root / source['preserved_file'])
    if (stat_path.parent != manifest_path.parent / 'normalized'
            or preserved.parent != manifest_path.parent / 'source'):
        raise ValueError('PRONOM-kilde ligger utenfor importen')
    raw = _bytes(root, preserved)
    if _hash(raw) != source['sha256'] or len(raw) != source['size_bytes']:
        raise ValueError('Bevart PRONOM-CSV stemmer ikke med manifestet')
    normalized = _normalized(raw, preserved.name)
    normalized['source']['preserved_file'] = source['preserved_file']
    digest = _hash(_encode(normalized))
    if (digest != _hash(_bytes(root, stat_path))
            or digest != reference['sha256'] or digest != manifest['normalized_sha256']):
        raise ValueError('Normalisert PRONOM-statistikk stemmer ikke med CSV')
    cli = _bytes(root, root / manifest['cli_manifest'])
    if _hash(cli) != manifest['cli_manifest_sha256']:
        raise ValueError('Opprinnelig Arkade-kjoremanifest er endret')
    return True
