from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RUNTIME_IMPORT_RE = re.compile(
    r"from\s+gui\.(persistent_app_a[\w.]+)\s+import\s+run_gui(?:\s+as\s+\w+)?"
)


def _git_lines(*args: str) -> list[str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git command failed")
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def changed_paths(base: str) -> list[Path]:
    names = set(_git_lines("diff", "--name-only", base, "--"))
    names.update(_git_lines("ls-files", "--others", "--exclude-standard"))
    return sorted(ROOT / name for name in names)


def active_runtime_module(main_text: str) -> str | None:
    matches = RUNTIME_IMPORT_RE.findall(main_text)
    return matches[-1] if matches else None


def stale_runtime_expectations(main_text: str, test_files: list[Path]) -> list[str]:
    active = active_runtime_module(main_text)
    if not active:
        return ["main.py: fant ingen aktiv 'import run_gui'"]

    problems: list[str] = []
    for test in test_files:
        text = test.read_text(encoding="utf-8")
        for match in RUNTIME_IMPORT_RE.finditer(text):
            expected = match.group(1)
            # Aliased historical imports are allowed. Only literal expectations
            # of the active, unaliased run_gui contract are blockers.
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.end())
            line = text[line_start: line_end if line_end >= 0 else len(text)]
            if " as " in line:
                continue
            if expected != active and "assertIn" in text[max(0, match.start()-200):match.start()+200]:
                try:
                    display_path = test.relative_to(ROOT)
                except ValueError:
                    display_path = test
                problems.append(
                    f"{display_path} forventer aktiv runtime {expected}, "
                    f"men main.py bruker {active}"
                )
    return problems


def _direct_read_targets(test_text: str) -> set[str]:
    targets = set()
    for match in re.finditer(
        r'ROOT\s*/\s*"([^"]+)"(?:\s*/\s*"([^"]+)")?(?:\s*/\s*"([^"]+)")?',
        test_text,
    ):
        parts = [p for p in match.groups() if p]
        if parts:
            targets.add("/".join(parts))
    return targets


def _assertin_literals(test_text: str) -> list[str]:
    try:
        tree = ast.parse(test_text)
    except SyntaxError:
        return []
    result: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "assertIn":
            continue
        if not node.args:
            continue
        value = node.args[0]
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            result.append(value.value)
    return result


def broken_literal_contracts(changed: list[Path], test_files: list[Path]) -> list[str]:
    changed_by_rel = {
        path.relative_to(ROOT).as_posix(): path
        for path in changed
        if path.exists() and path.is_file()
    }
    problems: list[str] = []

    for test in test_files:
        text = test.read_text(encoding="utf-8")
        targets = _direct_read_targets(text)
        for target in targets:
            target_path = changed_by_rel.get(target)
            if target_path is None:
                continue
            source = target_path.read_text(encoding="utf-8")
            for literal in _assertin_literals(text):
                # Only treat substantial code-like literals as compatibility
                # contracts. Short labels and documentation phrases are excluded.
                if len(literal) < 18:
                    continue
                code_like = any(
                    marker in literal
                    for marker in (
                        "self.", "from ", "def ", "for ", "if ", "return ",
                        "WorkflowApp", "run_gui", "_tooltips", "status_",
                    )
                )
                if code_like and literal not in source:
                    problems.append(
                        f"{test.relative_to(ROOT)} låser streng mot {target} "
                        f"som ikke lenger finnes: {literal!r}"
                    )
    return problems


def impacted_tests(changed: list[Path], test_files: list[Path]) -> list[Path]:
    rel_changed = [p.relative_to(ROOT).as_posix() for p in changed]
    tokens = set()
    for rel in rel_changed:
        p = Path(rel)
        tokens.add(p.name)
        tokens.add(p.stem)
        if p.name == "main.py":
            tokens.update({"run_gui", "persistent_app_", "runtime"})
        if p.name == "workflow_panel.py":
            tokens.update({"WorkflowPanel", "_tooltips", "status_provider", "workflow_panel"})

    impacted = []
    for test in test_files:
        text = test.read_text(encoding="utf-8")
        if any(token and token in text for token in tokens):
            impacted.append(test)
    return impacted


def run_test_files(files: list[Path]) -> int:
    if not files:
        return 0
    modules = [
        "tests." + file.relative_to(ROOT / "tests").with_suffix("").as_posix().replace("/", ".")
        for file in files
    ]
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "-v", *modules],
        cwd=ROOT,
    )
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mandatory regression preflight before an AI delta is delivered."
    )
    parser.add_argument("--base", default="HEAD", help="Git base/ref for the delta (default: HEAD)")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run the complete test suite after targeted checks.",
    )
    parser.add_argument(
        "--scan-only",
        action="store_true",
        help="Only scan contracts; do not run tests.",
    )
    args = parser.parse_args()

    try:
        changed = changed_paths(args.base)
    except RuntimeError as exc:
        print(f"[BLOCK] Kan ikke lese git-delta: {exc}")
        return 2

    tests = sorted((ROOT / "tests").glob("test_*.py"))
    production_changed = [
        p for p in changed
        if p.exists()
        and p.suffix in {".py", ".json", ".bat", ".md"}
        and "tests" not in p.relative_to(ROOT).parts
        and "docs/test-results" not in p.relative_to(ROOT).as_posix()
    ]

    print("=== DELTA PREFLIGHT ===")
    print(f"Base: {args.base}")
    print(f"Endrede filer: {len(changed)}")
    for path in changed:
        print(f"  - {path.relative_to(ROOT)}")

    blockers: list[str] = []
    main_path = ROOT / "main.py"
    if main_path.exists():
        blockers.extend(
            stale_runtime_expectations(
                main_path.read_text(encoding="utf-8"),
                tests,
            )
        )
    blockers.extend(broken_literal_contracts(production_changed, tests))

    if blockers:
        print("\n[BLOCK] Foreldede/brekkede eksisterende testkontrakter:")
        for problem in blockers:
            print(f"  - {problem}")
        print("\nDelta skal IKKE leveres før disse er rettet.")
        return 1

    impacted = impacted_tests(production_changed, tests)
    print(f"\nBerørte eksisterende tester: {len(impacted)}")
    for test in impacted:
        print(f"  - {test.relative_to(ROOT)}")

    if not args.scan_only:
        if impacted:
            print("\nKjører berørte tester...")
            rc = run_test_files(impacted)
            if rc:
                print("\n[BLOCK] Berørte tester feilet. Delta skal IKKE leveres.")
                return rc

        if args.full:
            print("\nKjører full testsuite...")
            proc = subprocess.run(
                [sys.executable, "tests/run_tests.py"],
                cwd=ROOT,
            )
            if proc.returncode:
                print("\n[BLOCK] Full testsuite feilet. Delta skal IKKE leveres.")
                return proc.returncode

    print("\n[OK] Delta-preflight bestått.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
