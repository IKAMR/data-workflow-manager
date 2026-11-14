"""Historical milestone assertions against the *real* version.py declaration.

Newer releases satisfy older feature milestones. For the same release,
prerelease increments must still meet the original alpha/subversion floor.
No synthetic version markers or monkeypatching are used.
"""
from __future__ import annotations

import re


_VERSION_DECLARATION = re.compile(
    r'(?m)^VERSION\s*=\s*"(\d+)\.(\d+)\.(\d+)(?:-a(\d+)(?:\.(\d+)(?:\.\d+)*)?)?"\s*$'
)
_RELEASE = re.compile(r'^(\d+)\.(\d+)\.(\d+)$')
_FINAL_ALPHA = 10**9


def _first_version(version_text: str):
    """Return (release, alpha, sub, has_sub) or None; reject unrelated text."""
    matches = list(_VERSION_DECLARATION.finditer(version_text))
    if len(matches) != 1:
        return None
    match = matches[0]
    release = tuple(int(match.group(i)) for i in (1, 2, 3))
    alpha = int(match.group(4)) if match.group(4) is not None else None
    sub = int(match.group(5)) if match.group(5) is not None else 0
    return release, alpha, sub, match.group(5) is not None


def _release_tuple(release: str):
    match = _RELEASE.fullmatch(release)
    return tuple(int(match.group(i)) for i in (1, 2, 3)) if match else None


def parse_release_or_alpha(version_text: str, release: str, *, consolidated_alpha=False):
    """Comparable (alpha, sub) for a release, or sentinel for a newer release."""
    actual = _first_version(version_text)
    required = _release_tuple(release)
    if actual is None or required is None:
        return None
    actual_release, alpha, sub, has_sub = actual
    if actual_release < required:
        return None
    if actual_release > required or alpha is None:
        return (_FINAL_ALPHA, _FINAL_ALPHA)
    if consolidated_alpha and not has_sub:
        sub = _FINAL_ALPHA
    return (alpha, sub)


def assert_release_at_least(testcase, version_text: str, release: str,
                            alpha: int, sub: int = 0, *, consolidated_alpha=False) -> None:
    actual = parse_release_or_alpha(
        version_text, release, consolidated_alpha=consolidated_alpha
    )
    testcase.assertIsNotNone(actual, version_text)
    testcase.assertGreaterEqual(actual, (alpha, sub))


def assert_v016_at_least(testcase, version_text: str, alpha: int,
                         sub: int = 0, *, consolidated_alpha=False) -> None:
    assert_release_at_least(
        testcase, version_text, '0.1.6', alpha, sub,
        consolidated_alpha=consolidated_alpha,
    )
