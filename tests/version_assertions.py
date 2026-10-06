from __future__ import annotations

import re


def parse_release_or_alpha(version_text: str, release: str) -> tuple[int, int] | None:
    """Return a comparable alpha milestone for one release series.

    A finished release is newer than every alpha in the same release series.
    Example for release ``0.1.6``:
      0.1.6-a14.3 -> (14, 3)
      0.1.6       -> (1_000_000_000, 0)
    """
    release_re = re.escape(release)
    match = re.search(
        rf'VERSION\s*=\s*"{release_re}(?:-a(\d+)(?:\.(\d+))*)?"',
        version_text,
    )
    if not match:
        return None
    if match.group(1) is None:
        return (1_000_000_000, 0)
    sub = re.search(rf'{release_re}-a\d+(?:\.(\d+))?', match.group(0))
    return (int(match.group(1)), int(sub.group(1) or 0))


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
