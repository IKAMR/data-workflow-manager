"""Bounded, incremental reader for native Siegfried JSON.

Only one ``files`` entry is decoded at a time. Unknown top-level values and
individual file records have a finite token limit, so input size does not
determine parser memory use.
"""
from __future__ import annotations

import json
from pathlib import Path

from .canonical_external_v0115_a5 import MAX_MATCHES, MAX_RECORDS

MAX_TOKEN = 2 * 1024 * 1024
MAX_FORMATS = 100_000


class StreamCapacityError(ValueError):
    pass


def _invalid_constant(value: str):
    raise ValueError(f'Non-standard JSON constant: {value}')


class _Reader:
    def __init__(self, path: Path):
        self.stream = path.open('r', encoding='utf-8-sig')
        self.buffer = ''
        self.end = False
        self.decoder = json.JSONDecoder(parse_constant=_invalid_constant)

    def close(self):
        self.stream.close()

    def _fill(self):
        chunk = self.stream.read(64 * 1024)
        self.end = not bool(chunk)
        self.buffer += chunk

    def _space(self):
        while True:
            self.buffer = self.buffer.lstrip()
            if self.buffer or self.end:
                return
            self._fill()

    def peek(self):
        self._space()
        return self.buffer[:1]

    def take(self, char: str):
        if self.peek() != char:
            raise ValueError(f'Expected {char!r} in JSON')
        self.buffer = self.buffer[1:]

    def value(self):
        self._space()
        while True:
            try:
                value, end = self.decoder.raw_decode(self.buffer)
                # A number can continue in the next chunk. Its delimiter must
                # be present before the token is accepted.
                if isinstance(value, (int, float)) and not self.end and end == len(self.buffer):
                    self._fill()
                    continue
                if len(self.buffer[:end].encode('utf-8')) > MAX_TOKEN:
                    raise StreamCapacityError(f'JSON element exceeds {MAX_TOKEN} bytes')
                self.buffer = self.buffer[end:]
                return value
            except json.JSONDecodeError as exc:
                if self.end:
                    raise ValueError(f'Malformed JSON: {exc.msg}') from exc
                if len(self.buffer.encode('utf-8')) > MAX_TOKEN:
                    raise StreamCapacityError(f'JSON element exceeds {MAX_TOKEN} bytes')
                self._fill()
            if len(self.buffer.encode('utf-8')) > MAX_TOKEN:
                raise StreamCapacityError(f'JSON element exceeds {MAX_TOKEN} bytes')


def inspect_siegfried_stream(path: Path) -> dict:
    """Summarize native Siegfried files without retaining files or matches."""
    reader = _Reader(path)
    signature = None
    has_files = False
    invalid_structure = False
    count = matched = unmatched = matches_count = 0
    identifiers: dict[str, int] = {}
    try:
        reader.take('{')
        while reader.peek() != '}':
            key = reader.value()
            if not isinstance(key, str):
                raise ValueError('JSON object key is not text')
            reader.take(':')
            if key == 'files':
                if has_files:
                    raise ValueError('Duplicate files field')
                has_files = True
                if reader.peek() != '[':
                    reader.value()
                    invalid_structure = True
                else:
                    reader.take('[')
                    while reader.peek() != ']':
                        file = reader.value()
                        count += 1
                        if count > MAX_RECORDS:
                            raise StreamCapacityError(f'File records exceed {MAX_RECORDS}')
                        if not isinstance(file, dict) or not isinstance(file.get('matches'), list):
                            invalid_structure = True
                        else:
                            matches = file['matches']
                            matches_count += len(matches)
                            if matches_count > MAX_MATCHES:
                                raise StreamCapacityError(f'Matches exceed {MAX_MATCHES}')
                            matched += bool(matches)
                            unmatched += not bool(matches)
                            for entry in matches:
                                if not isinstance(entry, dict):
                                    invalid_structure = True
                                    continue
                                namespace, identifier = entry.get('ns'), entry.get('id')
                                if isinstance(namespace, str) and isinstance(identifier, str) and namespace and identifier:
                                    key_id = namespace + ':' + identifier
                                    if key_id not in identifiers and len(identifiers) >= MAX_FORMATS:
                                        raise StreamCapacityError(f'Format identifiers exceed {MAX_FORMATS}')
                                    identifiers[key_id] = identifiers.get(key_id, 0) + 1
                        if reader.peek() != ']':
                            reader.take(',')
                            if reader.peek() == ']':
                                raise ValueError('Trailing comma in files array')
                    reader.take(']')
            else:
                value = reader.value()
                if key == 'siegfried':
                    signature = value
            if reader.peek() != '}':
                reader.take(',')
                if reader.peek() == '}':
                    raise ValueError('Trailing comma in JSON object')
        reader.take('}')
        if reader.peek():
            raise ValueError('Trailing data after JSON object')
    finally:
        reader.close()
    if not isinstance(signature, str) or not signature.strip() or not has_files:
        return {'format': 'unrecognized', 'interpretation': 'not_parsed', 'reason': 'No supported signature'}
    if invalid_structure:
        return {'format': 'siegfried_json', 'interpretation': 'not_parsed',
                'reason': 'Invalid file/matches structure'}
    return {'format': 'siegfried_json', 'interpretation': 'format_identification_only',
            'file_records': count, 'files_with_matches': matched, 'files_without_matches': unmatched,
            'format_matches': matches_count,
            'identifiers': [{'id': key, 'matches': value} for key, value in sorted(identifiers.items())],
            'technical_test_status': None, 'approval': None,
            'note': 'Formatidentifikasjon, ikke bevis paa filintegritet, Noark-validitet eller depotaksept.'}
