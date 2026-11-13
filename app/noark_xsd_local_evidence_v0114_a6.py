"""Local, export-ready XSD evidence; no network, no modification of Source.

The Work-local catalogue is scoped to one job. Reobserving the same variant
updates dates/count and preserves earlier records. A digest is content identity,
not an authority that a schema is conformant or safe.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import tempfile
import uuid

from app.noark_xsd_version_v0114_a5 import VersionEvidence, _hash_schema

SCHEMA_VERSION = '1.0'
MAX_CATALOG_BYTES = 5_000_000
NAMESPACE = uuid.UUID('4b3d890b-e4c8-427f-90b4-7ea03d9224ba')


def evidence_path(work: Path) -> Path:
    """Work must be an explicit directory, never Source or a guessed parent."""
    return Path(work) / 'noark5_evidence' / 'xsd_variants.json'


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def save_xsd_evidence(evidence: VersionEvidence, work: Path, *, timestamp: str | None = None) -> Path:
    """Persist provenance of examined XSDs; atomic replacement, idempotent by digest.

    Caller must pass an established Work path distinct from the selected Source.
    This never reads original document contents into the ledger.
    """
    target = evidence_path(work)
    work = Path(work).resolve()
    if not work.is_dir():
        raise ValueError('Work-området finnes ikke')
    if evidence.source is None or not evidence.schemas:
        raise ValueError('Ingen XSD-evidens å lagre')
    source = evidence.source.resolve()
    if work == source or source in work.parents or work in source.parents:
        raise ValueError('Work må være adskilt fra original Source')
    when = timestamp or _timestamp()
    if target.exists():
        if target.stat().st_size > MAX_CATALOG_BYTES:
            raise ValueError('Lokal XSD-katalog overskrider størrelsesgrensen')
        obj = json.loads(target.read_text(encoding='utf-8'))
        if obj.get('schema_version') != SCHEMA_VERSION or not isinstance(obj.get('variants'), list):
            raise ValueError('Ukjent lokal XSD-katalog: ingen overskriving')
    else:
        obj = {'schema_version': SCHEMA_VERSION, 'catalog_type': 'noark5_xsd_variants',
               'repository_publication': 'local_only', 'variants': [], 'observations': []}
    obj.setdefault('observations', [])
    existing = {x['sha256']: x for x in obj['variants']}
    for item in evidence.schemas:
        digest = item.digest
        if not digest or len(digest) != 64:
            continue
        # Re-hash during save: if Source changed since inspection, refuse stale evidence.
        if _hash_schema(item.path) != digest:
            raise ValueError(f'XSD er endret siden undersøkelsen: {item.path.name}')
        record = existing.get(digest)
        if record is None:
            record = {'variant_id': str(uuid.uuid5(NAMESPACE, 'sha256:' + digest)),
                      'sha256': digest, 'filename': item.path.name,
                      'size_bytes': item.path.stat().st_size,
                      'schema_version_declared': item.declared_version,
                      'noark_version_identified': item.version,
                      'reference_path': item.reference,
                      'identification': item.status,
                      'maintenance_note': item.maintenance_note,
                      'first_observed': when, 'last_observed': when, 'observation_count': 0}
            obj['variants'].append(record)
            existing[digest] = record
        # This counter represents saving evidence, not number of unique extracts.
        record['last_observed'] = when
        record['observation_count'] += 1
        obj['observations'].append({
            'observation_id': str(uuid.uuid4()), 'variant_id': record['variant_id'],
            'observed_at': when, 'source_file': str(item.path),
            'source': str(source), 'source_xsd_version_status': evidence.status,
            'source_noark_version': evidence.version,
        })
    if not obj['variants']:
        raise ValueError('Ingen hash-verifiserte XSD-filer')
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix='.xsd-', suffix='.tmp', dir=target.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            json.dump(obj, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return target


def work_from_report(report_path: Path | str | None) -> Path | None:
    """Authoritative per-job Work, never guessed from a depot report folder."""
    if not report_path:
        return None
    for ancestor in Path(report_path).parents:
        if (ancestor / 'job.json').is_file():
            return ancestor
    return None
