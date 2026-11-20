"""A16: read-only, bounded-memory projection of a large saved XPath master.

The complete JSON document is parsed to EOF with ijson. Only the handful of
scalar fields used for KS consistency and technical-test browsing are kept;
large per-test result payloads are never materialized or silently truncated.
This is not XPath execution, a new validation result, or a normative assertion.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any


class XPathMasterError(ValueError):
    """Reject an incomplete or unverifiable master rather than treat it as OK."""


# Per-scalar safety bound, not a cumulative file-size or test-count cap.
MAX_SCALAR_BYTES = 8 * 1024 * 1024
_FIELDS = frozenset(('test_id', 'status', 'availability', 'name', 'test_point'))


def hash_file(path: str | Path) -> str:
    """Hash the exact original bytes, streaming without a total-size limit."""
    digest = sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _text(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise XPathMasterError('XPath-master har ugyldig tekstfelt: ' + field)
    if len(value.encode('utf-8')) > MAX_SCALAR_BYTES:
        raise XPathMasterError('XPath-master har uventet stort enkeltfelt: ' + field)
    return value


def project_xpath_master(path: str | Path) -> dict:
    """Parse *all* JSON events and retain only saved test identities/states.

    The ijson dependency is already declared in requirements-core.txt. If it
    is unavailable, fail visibly; never fall back to an unbounded json.load.
    """
    try:
        import ijson
    except ImportError as exc:
        raise XPathMasterError('Strømlesing av XPath-master krever ijson (requirements-core.txt)') from exc

    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise XPathMasterError('Manglende eller utrygg XPath-master')
    result = {'format_version': None, 'source': {'execution_profile': ''}, 'tests': []}
    in_tests = False
    in_test = False
    test: dict[str, Any] = {}
    seen_fields: set[str] = set()
    ids: set[str] = set()
    root_started = root_finished = tests_started = tests_finished = False
    try:
        with path.open('rb') as stream:
            for prefix, event, value in ijson.parse(stream):
                if prefix == '' and event == 'start_map':
                    if root_started:
                        raise XPathMasterError('XPath-master har flere rotobjekter')
                    root_started = True
                elif prefix == '' and event == 'end_map':
                    root_finished = True
                elif prefix == 'format_version' and event in ('number', 'integer'):
                    if type(value) is not int or result['format_version'] is not None:
                        raise XPathMasterError('XPath-master har ugyldig formatversjon')
                    result['format_version'] = value
                elif prefix == 'source.execution_profile' and event == 'string':
                    if result['source']['execution_profile']:
                        raise XPathMasterError('XPath-master har gjentatt kjøreprofil')
                    result['source']['execution_profile'] = _text(value, field='execution_profile')
                elif prefix == 'tests' and event == 'start_array':
                    if tests_started:
                        raise XPathMasterError('XPath-master har gjentatt testliste')
                    tests_started = in_tests = True
                elif prefix == 'tests' and event == 'end_array':
                    tests_finished = True
                    in_tests = False
                elif prefix == 'tests.item' and event == 'start_map':
                    if not in_tests or in_test:
                        raise XPathMasterError('XPath-master har feil i testlisten')
                    in_test = True
                    test = {}
                    seen_fields = set()
                elif prefix == 'tests.item' and event == 'end_map':
                    if not in_test:
                        raise XPathMasterError('XPath-master har ugyldig testpost')
                    ident = test.get('test_id', '')
                    if not ident or ident in ids:
                        raise XPathMasterError('XPath-master har tom eller duplisert test-ID')
                    ids.add(ident)
                    result['tests'].append(test)
                    in_test = False
                    test = {}
                elif event == 'string' and len(value.encode('utf-8')) > MAX_SCALAR_BYTES:
                    # Also guard unprojected detail fields: the stream reader
                    # must not accept arbitrarily large individual JSON tokens.
                    raise XPathMasterError('XPath-master har uventet stort enkeltfelt')
                elif in_test and prefix.startswith('tests.item.'):
                    field = prefix.removeprefix('tests.item.')
                    if field in _FIELDS and event in ('string', 'null', 'number', 'integer', 'boolean'):
                        if field in seen_fields:
                            raise XPathMasterError('XPath-master har gjentatt testfelt: ' + field)
                        seen_fields.add(field)
                        test[field] = _text(value, field=field)
            if (not root_started or not root_finished or not tests_started
                    or not tests_finished or in_test or in_tests
                    or result['format_version'] != 1
                    or result['source']['execution_profile'] != 'normal'
                    or not result['tests']):
                raise XPathMasterError('Ufullstendig XPath-master eller feil kjøreprofil')
    except (OSError, UnicodeError, ValueError, getattr(ijson, 'JSONError', ValueError)) as exc:
        if isinstance(exc, XPathMasterError):
            raise
        raise XPathMasterError('Uleselig eller ufullstendig XPath-master: ' + str(path)) from exc
    return result
