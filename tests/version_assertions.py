from __future__ import annotations

import re


def _first_version(version_text: str) -> tuple[tuple[int, int, int], int | None, int] | None:
    match = re.search(
        r'VERSION\s*=\s*"(\d+)\.(\d+)\.(\d+)(?:-a(\d+)(?:\.(\d+))*)?"',
        version_text,
    )
    if not match:
        return None
    release = tuple(int(match.group(index)) for index in (1, 2, 3))
    alpha = int(match.group(4)) if match.group(4) is not None else None
    sub_match = re.search(r'-a\d+(?:\.(\d+))?', match.group(0))
    sub = int(sub_match.group(1) or 0) if alpha is not None else 0
    return release, alpha, sub


def _release_tuple(release: str) -> tuple[int, int, int] | None:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", release)
    if not match:
        return None
    return tuple(int(match.group(index)) for index in (1, 2, 3))


def parse_release_or_alpha(version_text: str, release: str) -> tuple[int, int] | None:
    """Return a comparable milestone for ``release`` or any newer release.

    Historical tests ask whether the current application is at least a milestone
    from an older release series.  Once the application has moved to a newer
    release, that condition remains true and must not become a regression.
    """
    actual = _first_version(version_text)
    expected_release = _release_tuple(release)
    if actual is None or expected_release is None:
        return None

    actual_release, alpha, sub = actual
    if actual_release < expected_release:
        return None
    if actual_release > expected_release:
        return (1_000_000_001, 0)
    if alpha is None:
        return (1_000_000_000, 0)
    return (alpha, sub)


def assert_release_at_least(
    testcase,
    version_text: str,
    release: str,
    alpha: int,
    sub: int = 0,
) -> None:
    actual = parse_release_or_alpha(version_text, release)
    testcase.assertIsNotNone(actual)
    testcase.assertGreaterEqual(actual, (alpha, sub))


def assert_v016_at_least(testcase, version_text: str, alpha: int, sub: int = 0) -> None:
    assert_release_at_least(testcase, version_text, "0.1.6", alpha, sub)
