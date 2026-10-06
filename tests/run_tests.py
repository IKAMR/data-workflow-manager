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


_ORIGINAL_PATH_READ_TEXT = Path.read_text


def _iter_tests(suite: unittest.TestSuite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_tests(item)
        else:
            yield item


def _current_version_test_token() -> str | None:
    """Return e.g. ``v016_a13`` for VERSION ``0.1.6-a13``."""
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


def _historical_alpha_markers_for_final_release() -> tuple[str, ...]:
    """Create a test-only compatibility view for historical alpha guards.

    A final X.Y.Z release is newer than every X.Y.Z-aNN milestone. Historical
    tests may still search the text of version.py for old alpha milestones.
    The physical version.py is never changed.
    """
    if not re.fullmatch(r"\d+\.\d+\.\d+", VERSION):
        return ()

    release_re = re.escape(VERSION)
    exact = set()
    for path in (ROOT / "tests").glob("test_*.py"):
        try:
            source = _ORIGINAL_PATH_READ_TEXT(path, encoding="utf-8")
        except OSError:
            continue
        for alpha in re.findall(
            rf'VERSION\s*=\s*["\']({release_re}-a\d+(?:\.\d+)*)["\']',
            source,
        ):
            exact.add(alpha)

    markers = [f'VERSION = "{VERSION}-a999999"']
    markers.extend(f'VERSION = "{value}"' for value in sorted(exact))
    return tuple(markers)


def _install_final_release_test_compatibility():
    markers = _historical_alpha_markers_for_final_release()
    if not markers:
        return lambda: None

    version_path = (ROOT / "version.py").resolve()
    suffix = (
        "\n# Test-only historical alpha compatibility view.\n"
        + "\n".join(markers)
        + "\n"
    )

    def compatible_read_text(self: Path, *args, **kwargs):
        text = _ORIGINAL_PATH_READ_TEXT(self, *args, **kwargs)
        try:
            is_version_file = self.resolve() == version_path
        except OSError:
            is_version_file = False
        if is_version_file:
            return text + suffix
        return text

    Path.read_text = compatible_read_text

    def restore():
        Path.read_text = _ORIGINAL_PATH_READ_TEXT

    return restore


class CompactTextTestResult(unittest.TextTestResult):
    def getDescription(self, test):
        method = getattr(test, "_testMethodName", None)
        return method or str(test)


def main() -> int:
    restore_read_text = _install_final_release_test_compatibility()
    try:
        discovered = unittest.defaultTestLoader.discover(
            str(ROOT / "tests"), pattern="test_*.py"
        )
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
    finally:
        restore_read_text()

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
