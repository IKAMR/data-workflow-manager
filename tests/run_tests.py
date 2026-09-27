from __future__ import annotations

import io
import re
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from version import VERSION


def _iter_tests(suite: unittest.TestSuite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_tests(item)
        else:
            yield item


def _current_version_test_token() -> str | None:
    """Return e.g. ``v016_a13`` for VERSION ``0.1.6-a13``.

    Current-version tests are deliberately run first. This catches exactly the
    regression class introduced by the active alpha before the full historical
    suite scrolls past hundreds of older tests.
    """
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)-a(\d+)", VERSION)
    if not match:
        return None
    major, minor, patch, alpha = match.groups()
    return f"v{int(major)}{int(minor)}{int(patch)}_a{int(alpha)}"


def _test_sort_key(test) -> tuple[int, str]:
    try:
        test_id = test.id()
    except Exception:
        test_id = str(test)
    token = _current_version_test_token()
    is_current = bool(token and token in test_id)
    return (0 if is_current else 1, test_id)


class CompactTextTestResult(unittest.TextTestResult):
    def getDescription(self, test):
        method = getattr(test, "_testMethodName", None)
        return method or str(test)


def main() -> int:
    discovered = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    tests = sorted(list(_iter_tests(discovered)), key=_test_sort_key)
    suite = unittest.TestSuite(tests)

    test_ids = []
    for test in tests:
        try:
            test_ids.append(test.id())
        except Exception:
            test_ids.append(str(test))

    stream = io.StringIO()
    runner = unittest.TextTestRunner(
        stream=stream,
        verbosity=2,
        resultclass=CompactTextTestResult,
    )
    result = runner.run(suite)
    output = stream.getvalue()
    print(output, end="")

    status = "PASS" if result.wasSuccessful() else "FAIL"
    now = datetime.now().astimezone()
    out_dir = ROOT / "docs" / "test-results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"v{VERSION}.md"

    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped)
    passed = result.testsRun - failures - errors - skipped

    lines = [
        f"# Testresultat v{VERSION}",
        "",
        f"**Dato/tid:** {now.isoformat(timespec='seconds')}",
        f"**Resultat:** {status}",
        "",
        "## Oppsummering",
        "",
        f"- Tester kjørt: {result.testsRun}",
        f"- Bestått: {passed}",
        f"- Feilet: {failures}",
        f"- Feil under kjøring: {errors}",
        f"- Hoppet over: {skipped}",
        "",
        "## Tester",
        "",
    ]
    lines.extend(f"- `{test_id}`" for test_id in test_ids)
    lines.extend([
        "",
        "## Full testutskrift",
        "",
        "```text",
        output.rstrip(),
        "```",
        "",
    ])
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Testresultat skrevet til: {out_path.relative_to(ROOT)}")

    summary_path = out_dir / ".last-test-summary.txt"
    summary_path.write_text(
        "\n".join([
            f"TOTAL={result.testsRun}",
            f"PASSED={passed}",
            f"FAILED={failures}",
            f"ERRORS={errors}",
            f"SKIPPED={skipped}",
        ]) + "\n",
        encoding="ascii",
    )

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
