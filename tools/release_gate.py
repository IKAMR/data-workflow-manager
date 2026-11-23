"""Read-only release promotion gate for Data Workflow Manager.

Run from repo root:
    py tools/release_gate.py --development    # during X.Y.Z-aN
    py tools/release_gate.py                  # before final release

The development check validates the *hypothetical final version* against
current-series tests. New tests must use milestone floors, not exact alpha IDs.
This script never modifies application files, tests, Source, Work or Git.
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path
import re
import sys
import tomllib

VERSION_RE = re.compile(r'^APP_NAME = "Data Workflow Manager"\nVERSION = "(\d+)\.(\d+)\.(\d+)(?:-a(\d+))?"\n$')


def _literal(node: ast.AST):
    return node.value if isinstance(node, ast.Constant) else None


def _is_version_name(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) and node.id == "VERSION"


def _assertion_issues(path: Path, version: str) -> list[str]:
    """Find direct version assertions incompatible with a future final build."""
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    issues = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        method = node.func.attr
        if method == "assertRegex" and len(node.args) >= 2 and _is_version_name(node.args[0]):
            pattern = _literal(node.args[1])
            if isinstance(pattern, str):
                try:
                    matches = re.search(pattern, version) is not None
                except re.error:
                    continue  # The actual unittest will flag invalid regexes.
                if not matches:
                    issues.append(f"{path.name}:{node.lineno}: assertRegex(VERSION, ...) utelukker {version}")
        elif method == "assertEqual" and len(node.args) >= 2:
            a, b = node.args[:2]
            value = _literal(b) if _is_version_name(a) else _literal(a) if _is_version_name(b) else None
            if isinstance(value, str) and value != version:
                issues.append(f"{path.name}:{node.lineno}: hardkodet VERSION == {value}")
        elif method == "assertIn" and len(node.args) >= 2:
            value = _literal(node.args[0])
            if not isinstance(value, str):
                continue
            quoted_release = re.escape(version)
            if value.startswith(("VERSION = ", "version = ")) and re.search(
                rf'{quoted_release}(?:-a|a)\d+', value
            ):
                issues.append(f"{path.name}:{node.lineno}: hardkodet alpha i fysisk versjonskontroll")
    return issues


def release_errors(root: Path, *, require_final: bool = True) -> list[str]:
    """Check metadata and current-series tests; require history only for final.

    During development, validate the prospective final before alpha-specific
    assertions have a chance to accumulate. Historical feature tests remain.
    """
    issues: list[str] = []
    root = Path(root)
    try:
        version_text = (root / "version.py").read_text(encoding="utf-8")
        parsed = VERSION_RE.fullmatch(version_text)
    except OSError as exc:
        return [f"Kan ikke lese version.py: {exc}"]
    if not parsed:
        return ["version.py skal inneholde kun APP_NAME og en gyldig VERSION uten ekstra versjonsmarkører"]
    major, minor, patch, alpha = parsed.groups()
    release = f"{major}.{minor}.{patch}"
    version = release + (f"-a{alpha}" if alpha else "")
    expected_distribution = release + (f"a{alpha}" if alpha else "")

    if alpha and require_final:
        issues.append(f"{version}: forventet ferdig {release}, ikke alpha")

    try:
        with (root / "pyproject.toml").open("rb") as stream:
            project = tomllib.load(stream)["project"]
        if project.get("version") != expected_distribution:
            issues.append(
                f"pyproject.toml: versjon {project.get('version')!r} er ulik {expected_distribution!r}"
            )
    except (OSError, KeyError, ValueError, tomllib.TOMLDecodeError) as exc:
        issues.append(f"pyproject.toml: kan ikke verifisere distribusjonsversjonen: {exc}")

    if not alpha:
        notes = root / "docs" / f"RELEASE-v{release}.md"
        if not notes.is_file():
            issues.append(f"Mangler {notes.relative_to(root)}")
        history_file = root / "docs" / "RELEASES.md"
        try:
            history = history_file.read_text(encoding="utf-8")
            count = history.count(f"## v{release}\n")
            if count != 1:
                issues.append(f"docs/RELEASES.md: forventet nøyaktig én '## v{release}' (fant {count})")
        except OSError as exc:
            issues.append(f"docs/RELEASES.md: kan ikke lese: {exc}")

    # Check the real current series against the future final. This prevents
    # creating new tests that require a specific -aN and later block promotion.
    series = f"v{major}{minor}{patch}"
    for test_path in sorted((root / "tests").glob("test_*.py")):
        try:
            test_text = test_path.read_text(encoding="utf-8")
            # Also cover generically named tests that hardcode THIS series.
            # Do not re-interpret historical milestone fixtures in older tests.
            if (test_path.name.startswith(f"test_{series}")
                    or f"{release}-a" in test_text
                    or f"{re.escape(release)}-a" in test_text
                    or re.search(rf'{re.escape(release)}a\d+', test_text)):
                issues.extend(_assertion_issues(test_path, release))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            issues.append(f"{test_path.name}: kan ikke skanne test: {exc}")
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--development", action="store_true",
        help="Kontroller alpha-metadata og framtidig release-beredskap",
    )
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    issues = release_errors(root, require_final=not args.development)
    if issues:
        print("[RELEASE-SPERRE] Følgende må rettes:")
        for item in issues:
            print("  - " + item)
        print("Rett funnene; kjør deretter full test.bat på faktisk versjon.")
        return 1
    print("[OK] Versjonsfiler og aktuelle testvakter er konsistente.")
    if args.development:
        print("[OK] Ingen oppdagede alpha-låser som sperrer en senere sluttversjon.")
    else:
        print("[OK] Release-notater og versjonshistorikk er til stede.")
    print("[MERK] Statisk kontroll erstatter aldri full test.bat.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
