"""Read-only release promotion gate for Data Workflow Manager.

Run from the repo root: py tools/release_gate.py
Requires no third-party packages. It never changes release files, tests,
Source, Work, Git history or user data.
"""
from __future__ import annotations

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
    """Find direct VERSION asserts which would fail after alpha removal.

    Static precheck complements, but never replaces, actually executing tests.
    Only examines assertions on VERSION or literal physical-file version
    statements; unrelated regex tests and deliberate negative fixtures remain.
    """
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
                    # Let the actual unit test report its invalid regex.
                    continue
                if not matches:
                    issues.append(f"{path.name}:{node.lineno}: assertRegex(VERSION, ...) utelukker {version}")
        elif method in ("assertEqual", "assertNotEqual") and len(node.args) >= 2:
            if method != "assertEqual":
                continue
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
    """Return blockers for release identity, changelog, and old alpha guards."""
    issues: list[str] = []
    root = Path(root)
    version_path = root / "version.py"
    try:
        version_text = version_path.read_text(encoding="utf-8")
        parsed = VERSION_RE.fullmatch(version_text)
    except OSError as exc:
        return [f"Kan ikke lese version.py: {exc}"]
    if not parsed:
        return ["version.py skal inneholde kun APP_NAME og en gyldig VERSION uten ekstra versjonsmarkører"]
    major, minor, patch, alpha = parsed.groups()
    release = f"{major}.{minor}.{patch}"
    version = release + (f"-a{alpha}" if alpha else "")
    if alpha:
        if require_final:
            issues.append(f"{version}: forventet ferdig {release}, ikke alpha")
        # Alpha builds are not required to have a *finished* release history.
        if not require_final:
            return []
        return issues
    try:
        with (root / "pyproject.toml").open("rb") as stream:
            project = tomllib.load(stream)["project"]
        if project.get("version") != release:
            issues.append(f"pyproject.toml: versjon {project.get('version')!r} er ulik {release!r}")
    except (OSError, KeyError, ValueError, tomllib.TOMLDecodeError) as exc:
        issues.append(f"pyproject.toml: kan ikke verifisere distribusjonsversjonen: {exc}")
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
    series = f"v{major}{minor}{patch}"
    for test_path in sorted((root / "tests").glob(f"test_{series}*.py")):
        try:
            issues.extend(_assertion_issues(test_path, version))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            issues.append(f"{test_path.name}: kan ikke skanne test: {exc}")
    return issues


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    issues = release_errors(root)
    if issues:
        print("[RELEASE SPERRET] Frigivelse avvist:")
        for item in issues:
            print("  - " + item)
        print("Rett filene i release-deltaen og kjør FULL test.bat på sluttversjonen.")
        return 1
    print("[OK] Release-preflight: versjoner, historikk og alpha-testvakter samsvarer.")
    print("[MERK] Denne statiske kontrollen erstatter aldri full test.bat.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
