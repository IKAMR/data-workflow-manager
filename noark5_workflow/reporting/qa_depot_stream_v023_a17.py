"""A17: source-bound streaming projection of a large DWM depot validation report.

Read *every* JSON event, keeping only the fields actually consumed by the
established a12/a3 KS snapshot builders. Ignored per-test detail payloads are
neither materialized nor presented as complete evidence. Original Source and
Work evidence remain untouched. This does not approve an extraction.

The projection returns its SHA-256 over the bytes read by the parser. The
caller must verify it against the independently hashed Work manifest before
using the projection, to detect replacement between the two reads.
"""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
import math
from pathlib import Path
from typing import Any, Iterator


class DepotStreamError(ValueError):
    """An oversized depot report cannot be projected safely or completely."""


MAX_SCALAR_BYTES = 8 * 1024 * 1024
MAX_RETAINED_FIELD_BYTES = 256 * 1024
MAX_SECTION_BYTES = 3 * 1024 * 1024
MAX_SECTION_DEPTH = 64

# Maps of direct scalar fields needed by the existing report/snapshot readers.
_COLLECTION_FIELDS: dict[str, frozenset[str]] = {
    'archive_parts': frozenset((
        'archive_part.system_id', 'archive_part.title', 'archive_part.status',
        'archive_part.document_medium', 'archive_part.created_date',
        'archive_part.closed_date', 'archive_part.archive_period_start_date',
        'archive_part.archive_period_end_date', 'folder_count',
        'registration_count', 'document_object_count',
    )),
    'deviations': frozenset(('category', 'severity', 'summary', 'requires_review')),
    'technical_validation.tests': frozenset(('test_id', 'status', 'test_point')),
    'external_validation.arkade5.imports': frozenset(('normalized_file', 'source_sha256')),
}


class _HashingReader:
    """Feed ijson and SHA-256 from the same byte stream."""

    def __init__(self, stream):
        self.stream = stream
        self.digest = sha256()
        self.size = 0

    def read(self, size: int = -1) -> bytes:
        block = self.stream.read(size)
        if block:
            self.digest.update(block)
            self.size += len(block)
        return block

    def readable(self) -> bool:
        return True


def _scalar(event: str, value: Any) -> Any:
    if event == 'string':
        if not isinstance(value, str) or len(value.encode('utf-8')) > MAX_SCALAR_BYTES:
            raise DepotStreamError('Depotrapport har et uventet stort tekstfelt')
        return value
    if event == 'number':
        if isinstance(value, Decimal):
            if not value.is_finite():
                raise DepotStreamError('Depotrapport har et ikke-endelig tall')
            value = float(value)
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            raise DepotStreamError('Depotrapport har et ugyldig tall')
        return value
    if event == 'integer':
        if type(value) is not int:
            raise DepotStreamError('Depotrapport har ugyldig heltall')
        return value
    if event == 'boolean':
        if type(value) is not bool:
            raise DepotStreamError('Depotrapport har ugyldig sannhetsverdi')
        return value
    if event == 'null':
        return None
    raise DepotStreamError('Ukjent JSON-verdi i depotrapport')


def _bounded_map(events: Iterator, name: str) -> dict:
    """Consume one arbitrary summary map with bounded retained memory."""
    root: dict = {}
    stack: list[dict | list] = [root]
    pending: list[str | None] = [None]
    size = 0

    def insert(value: Any) -> None:
        parent = stack[-1]
        if isinstance(parent, list):
            parent.append(value)
        else:
            key = pending[-1]
            if key is None or key in parent:
                raise DepotStreamError('Duplisert eller manglende JSON-feltnavn i depotrapport')
            parent[key] = value
            pending[-1] = None

    for prefix, event, value in events:
        if event == 'map_key':
            if not isinstance(stack[-1], dict) or pending[-1] is not None:
                raise DepotStreamError('Ugyldig nøkkel i depotrapportens sammendrag')
            if not isinstance(value, str):
                raise DepotStreamError('Ugyldig JSON-feltnavn')
            size += len(value.encode('utf-8'))
            pending[-1] = value
        elif event in ('start_map', 'start_array'):
            if len(stack) >= MAX_SECTION_DEPTH:
                raise DepotStreamError('For dyp struktur i depotrapportens sammendrag')
            child: dict | list = {} if event == 'start_map' else []
            insert(child)
            stack.append(child)
            pending.append(None)
        elif event in ('end_map', 'end_array'):
            expected = dict if event == 'end_map' else list
            if not isinstance(stack[-1], expected) or pending[-1] is not None:
                raise DepotStreamError('Ugyldig struktur i depotrapportens sammendrag')
            stack.pop()
            pending.pop()
            if not stack:
                if prefix != name or event != 'end_map':
                    raise DepotStreamError('Sammendrag avsluttes på feil JSON-nivå')
                return root
        elif event in ('string', 'integer', 'number', 'boolean', 'null'):
            scalar = _scalar(event, value)
            size += len(scalar.encode('utf-8')) if isinstance(scalar, str) else 16
            insert(scalar)
        else:
            raise DepotStreamError('Ukjent JSON-hendelse i sammendrag')
        if size > MAX_SECTION_BYTES:
            raise DepotStreamError('Depotrapportens sammendrag overstiger sikker grense')
    raise DepotStreamError('Ufullstendig sammendrag i depotrapport')


def _put_field(item: dict, field: str, scalar: Any) -> None:
    if isinstance(scalar, str) and len(scalar.encode('utf-8')) > MAX_RETAINED_FIELD_BYTES:
        raise DepotStreamError('Felt i depotrapportens KS-projeksjon er for stort: ' + field)
    if '.' in field:
        first, second = field.split('.', 1)
        parent = item.setdefault(first, {})
        if not isinstance(parent, dict) or second in parent:
            raise DepotStreamError('Duplisert eller ugyldig arkivdelsfelt: ' + field)
        parent[second] = scalar
    else:
        if field in item:
            raise DepotStreamError('Duplisert depotrapportfelt: ' + field)
        item[field] = scalar


def project_depot_report(path: str | Path) -> tuple[dict, str]:
    """Read a large report to EOF, return (relevant projection, exact SHA-256).

    A real ijson parser is mandatory for production. The projection deliberately
    retains every *relevant* archive-part, deviation, test ID/status and linked
    Arkade import, but never large unused technical-test result payloads.
    """
    try:
        import ijson
    except ImportError as exc:
        raise DepotStreamError('Strømlesing av depotrapport krever ijson (requirements-core.txt)') from exc

    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise DepotStreamError('Manglende eller utrygg depotrapport')
    before = path.stat()
    result: dict = {
        'report_type': None, 'summary': {},
        'technical_validation': {'tests': [], 'summary': {}, 'reconciliation': {}},
        'archive_parts': [], 'deviations': [], 'delivery_validation': None,
        'evidence': {}, 'external_validation': {'arkade5': {'imports': []}},
    }
    target_lists = {
        'archive_parts': result['archive_parts'],
        'deviations': result['deviations'],
        'technical_validation.tests': result['technical_validation']['tests'],
        'external_validation.arkade5.imports': result['external_validation']['arkade5']['imports'],
    }
    live: dict[str, dict] = {}
    seen: set[str] = set()
    seen_root: set[str] = set()
    root_start = root_end = False
    try:
        with path.open('rb') as source:
            reader = _HashingReader(source)
            events = iter(ijson.parse(reader))
            for prefix, event, value in events:
                # Reject duplicate *root* keys, including unknown sections.
                if prefix == '' and event == 'map_key':
                    if value in seen_root:
                        raise DepotStreamError('Duplisert rotfelt i depotrapport: ' + str(value))
                    seen_root.add(value)
                elif prefix == '' and event == 'start_map':
                    if root_start:
                        raise DepotStreamError('Flere rotobjekter i depotrapporten')
                    root_start = True
                elif prefix == '' and event == 'end_map':
                    root_end = True

                if prefix in ('summary', 'technical_validation.summary',
                              'technical_validation.reconciliation', 'delivery_validation'):
                    if prefix in seen:
                        raise DepotStreamError('Ugyldig eller duplisert sammendragsdel: ' + prefix)
                    if prefix == 'delivery_validation' and event == 'null':
                        seen.add(prefix)
                        continue
                    if event != 'start_map':
                        raise DepotStreamError('Forventet objekt i depotrapport: ' + prefix)
                    seen.add(prefix)
                    data = _bounded_map(events, prefix)
                    if prefix == 'summary':
                        result['summary'] = data
                    elif prefix == 'delivery_validation':
                        # A18: original a9/a10 per-finding register binding only.
                        # Never load an entire >24 MiB depot report just to bind
                        # its small SHA-/rule-based delivery metadata.
                        result['delivery_validation'] = data
                    else:
                        result['technical_validation'][prefix.rsplit('.', 1)[1]] = data
                    continue

                if prefix in target_lists:
                    if event == 'start_array':
                        if prefix in seen:
                            raise DepotStreamError('Duplisert liste i depotrapport: ' + prefix)
                        seen.add(prefix)
                    elif event == 'end_array':
                        if prefix not in seen or prefix in live:
                            raise DepotStreamError('Feil listeavslutning i depotrapport: ' + prefix)
                    else:
                        raise DepotStreamError('Forventet JSON-liste i depotrapport: ' + prefix)

                for name, rows in target_lists.items():
                    item_prefix = name + '.item'
                    if prefix == item_prefix:
                        if event == 'start_map':
                            if name in live or name not in seen:
                                raise DepotStreamError('Overlappende eller uventet depotrapportpost')
                            live[name] = {}
                        elif event == 'end_map':
                            if name not in live:
                                raise DepotStreamError('Uventet postslutt i depotrapport')
                            rows.append(live.pop(name))
                        elif event != 'map_key':
                            raise DepotStreamError('Depotrapportpost må være et JSON-objekt')
                    elif prefix.startswith(item_prefix + '.'):
                        field = prefix[len(item_prefix) + 1:]
                        if field in _COLLECTION_FIELDS[name]:
                            if event in ('start_map', 'start_array'):
                                raise DepotStreamError('Ugyldig type for depotrapportfelt: ' + field)
                            if event in ('string', 'integer', 'number', 'boolean', 'null'):
                                if name not in live:
                                    raise DepotStreamError('Felt utenfor depotrapportpost')
                                _put_field(live[name], field, _scalar(event, value))

                if event in ('string', 'integer', 'number', 'boolean', 'null'):
                    scalar = _scalar(event, value)
                    if prefix in ('report_type', 'technical_validation.status',
                                  'evidence.source_xpath_run'):
                        if prefix in seen:
                            raise DepotStreamError('Duplisert viktig depotrapportfelt: ' + prefix)
                        seen.add(prefix)
                        if not isinstance(scalar, str):
                            raise DepotStreamError('Ugyldig tekstfelt: ' + prefix)
                        if len(scalar.encode('utf-8')) > MAX_RETAINED_FIELD_BYTES:
                            raise DepotStreamError('Uventet stort identitetsfelt: ' + prefix)
                        if prefix == 'report_type':
                            result['report_type'] = scalar
                        elif prefix == 'technical_validation.status':
                            result['technical_validation']['status'] = scalar
                        else:
                            result['evidence']['source_xpath_run'] = scalar

            # Consume any remaining unread whitespace for exact byte hashing.
            for block in iter(lambda: reader.read(1024 * 1024), b''):
                pass
            digest = reader.digest.hexdigest()
            consumed = reader.size
        after = path.stat()
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise DepotStreamError('Depotrapporten ble endret under innlesing')
        if consumed != before.st_size:
            raise DepotStreamError('Depotrapporten ble ikke lest helt')
        if (not root_start or not root_end or live
                or result['report_type'] != 'noark5_depot_validation'
                or not result['evidence'].get('source_xpath_run')
                or 'archive_parts' not in seen or 'technical_validation.tests' not in seen
                or 'summary' not in seen):
            raise DepotStreamError('Depotrapport mangler påkrevd kilde- eller kontrollgrunnlag')
        return result, digest
    except (OSError, UnicodeError, ValueError, OverflowError,
            getattr(ijson, 'JSONError', ValueError)) as exc:
        if isinstance(exc, DepotStreamError):
            raise
        raise DepotStreamError('Ufullstendig eller ugyldig depotrapport: ' + str(path)) from exc
