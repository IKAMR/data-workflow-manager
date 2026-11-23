"""Reorganize DWM technical documentation without discarding source history.

Usage from a local checkout:
    py tools/docs_layout.py --plan
    py tools/docs_layout.py --apply
    py tools/docs_layout.py --check

The --check command is a permanent development guard. It rejects new files in
docs/ and current-version per-alpha notes; old pinned paths are grandfathered.

The --apply operation uses git mv, updates resolvable Markdown links, and is
idempotent. Files referenced by executable files outside docs/ are left in
place to avoid changing runtime/test path contracts inadvertently.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import os
import posixpath
import re
import subprocess
import sys
from urllib.parse import unquote


ROOT_DOCUMENTS = frozenset({
    "README.md",
    "ARCHITECTURE.md", "CLI.md", "CODE-MAP.md", "DATA-WORKFLOW-MANAGER.md",
    "DEFINITIONS.md", "DEVELOPMENT.md", "IDENTITY-MIGRATION.md",
    "INTERFACE.md", "METHOD-OBSERVATIONS.md", "NOARK-SOURCE-LIBRARY.md",
    "NOARK-XSD-VERSION-DETECTION.md",
    "NOARK5-CANONICAL-RESULTS-AND-KNOWLEDGE-ROADMAP.md",
    "NOARK5-DEPOT-PRESENTATION-AND-ASSESSMENT.md",
    "NOARK5-XPATH-TEST-CATALOG.md", "RELEASE-VERSION-TEST-RULE.md",
    "RELEASES.md", "REPOSITORY-STRUCTURE.md", "RUNTIME-ENVIRONMENTS.md",
    "SHARED-DEVELOPMENT.md", "SHARED-ROADMAP.md", "TESTING.md",
})


# Filenames left at the root after the 0.2.5 cleanup because tests or runtime
# still refer to the historical path. This is a FROZEN compatibility list;
# never add new development documents to it as a convenience.
LEGACY_ROOT_DOCUMENTS = frozenset({
    "APP-WORKSPACE-AND-RUN-LOGS.md",
    "ARKADE5-COMBINED-COVERAGE.md", "ARKADE5-COVERAGE-POLICY.md",
    "ARKADE5-DEPOT-REPORT.md", "ARKADE5-DWM-GAP-OVERLAP-GUI.md",
    "ARKADE5-DWM-GAP-OVERLAP.md", "ARKADE5-DWM-MAPPING.md",
    "ARKADE5-GUI-COVERAGE.md", "ARKADE5-GUI-DRILLDOWN.md",
    "ARKADE5-IMPORT-MODEL.md", "ARKADE5-INTEGRATION-CONTRACT.md",
    "ARKADE5-NOARK5-TESTS.md", "ARKADE5-PORTABLE-EVIDENCE.md",
    "ARKADE5-PRACTICAL-ACCEPTANCE.md", "ARKADE5-RELEASE-READINESS.md",
    "ARKADE5-V2.13.1-CHANGE-IMPACT.md",
    "DELTA-PREFLIGHT.md", "DEPOTPROFIL-V022-A1.md",
    "JOBS-AND-BATCHES.md", "LOGGING-PROVENANCE.md",
    "NOARK5-ANALYSIS-MODEL.md", "NOARK5-LOCAL-EXPERIENCE.md",
    "NOARK5-MASTER-RESULTS.md", "NOARK5-PROFILE-ARCHITECTURE.md",
    "NOARK5-STANDARD-VALUES.md", "NOARK5-TERMINOLOGY-NOTE.md",
    "NOARK5-U1-U2-COVERAGE-MAPPING.md", "PROFILE-ARCHITECTURE.md",
    "ROADMAP-ETTER-v0.2.0.md", "SOURCE-WORK-STORAGE.md",
    "TODO-ROADMAP.md", "WORKFLOW_STATUS_AND_INFO_PANEL.md",
})

RELEASE_NOTES_RE = re.compile(r"^RELEASE-v\d+\.\d+\.\d+\.md$", re.I)
OLD_VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+.*\.md$", re.I)
ALPHA_TOKEN_RE = re.compile(r"(?:^|[-_])A\d+(?:[-_.]|$)", re.I)
VERSION_ALPHA_RE = re.compile(r"V0\d+-A\d+", re.I)
LINK_RE = re.compile(r"(?<=\]\()(?P<url><[^>]+>|[^\s)]+)")
CODE_EXTENSIONS = {".py", ".bat", ".cmd", ".ps1", ".sh", ".toml", ".ini", ".cfg", ".yml", ".yaml", ".json"}


@dataclass(frozen=True)
class Move:
    old: str
    new: str


def alpha_category(filename: str) -> str:
    """Partition development history by known version, without guessing ages."""
    v = re.search(r"v(\d+\.\d+\.\d+)-a\d+", filename, re.I)
    if v:
        return f"history/alpha/v{v.group(1)}"
    v = re.search(r"V0(\d)(\d)-A\d+|v0(\d)(\d)-a\d+", filename, re.I)
    if v:
        major = v.group(1) or v.group(3)
        patch = v.group(2) or v.group(4)
        return f"history/alpha/v0.{int(major)}.{int(patch)}"
    if filename.upper().startswith("NOARK5-CANONICAL-A"):
        return "history/alpha/canonical"
    return "history/alpha/misc"


def destination_category(filename: str) -> str | None:
    """Classify only files directly inside docs/, preserving published anchors."""
    if filename in ROOT_DOCUMENTS or RELEASE_NOTES_RE.fullmatch(filename):
        return None
    n = filename.upper()
    if "DELTA-MANIFEST" in n:
        return "history/deltas"
    if n.startswith("TESTRESULTAT") or "TESTREGRESJON" in n or n.startswith("A9-TESTFIX"):
        return "history/test-notes"
    if OLD_VERSION_RE.fullmatch(filename):
        return alpha_category(filename) if re.search(r"-a\d+", filename, re.I) else "history/legacy"
    if (VERSION_ALPHA_RE.search(filename) or ALPHA_TOKEN_RE.search(filename)
            or n.startswith(("RETTELSE-", "OPPSTART-", "DWM-A"))):
        return alpha_category(filename)
    if n.startswith(("ARKADE5-", "ARKADE-")):
        return "integrations/arkade5"
    if n.startswith("SIEGFRIED-"):
        return "integrations/siegfried"
    if n.startswith(("DIAS-", "SIARD-")):
        return "integrations/dias"
    if n.startswith(("NOARK5-", "NOARK5_")):
        return "reference/noark5"
    if n.startswith(("GUI-", "ENKEL-", "WINDOW_STATE")):
        return "gui"
    if n.startswith(("DEPOT", "AVVIK", "RESULTAT", "KS-")) or "QUALITY" in n:
        return "quality"
    if n.startswith(("REPORT", "CSV-LOG", "JSON-LOG", "LOG-", "LOGGING-", "GENERIC-LOG")):
        return "reporting"
    if n.startswith(("STORAGE", "SOURCE-WORK", "WORK-", "CUSTOM-WORK", "APP-WORKSPACE", "INTELLIGENT_STORAGE")):
        return "storage"
    if n.startswith(("JOB", "WORKFLOW", "PARALLEL", "START_READY", "FIRST_SOURCE_JOB", "ADAPTIVE-PARALLEL")):
        return "workflow"
    if n.startswith(("PROFILE", "OPERATIONS", "EXTERNAL-CLI", "RESOURCE-STRATEGY")):
        return "architecture"
    if n.startswith(("SETUP", "PROJECT-SETTINGS", "GITHUB-SETUP", "WINDOWS-PATH", "DELIVERY-METHOD", "DELTA-PREFLIGHT")):
        return "development"
    if any(k in n for k in ("ROADMAP", "BACKLOG", "TODO")):
        return "plans"
    if n.startswith("RUNTIME-"):
        return "architecture"
    return "reference/general"


def raw_moves(root: Path) -> list[Move]:
    docs = root / "docs"
    if not docs.is_dir():
        raise ValueError(f"Fant ikke docs-mappen: {docs}")
    moves = []
    for path in sorted(docs.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        category = destination_category(path.name)
        if category:
            moves.append(Move(path.relative_to(root).as_posix(), f"docs/{category}/{path.name}"))
    # Existing architecture/development folders also contain legacy per-alpha notes.
    for folder in ("architecture", "development"):
        for path in sorted((docs / folder).glob("*.md")):
            name = path.name
            if (OLD_VERSION_RE.fullmatch(name) and re.search(r"-a\d+", name, re.I)) or VERSION_ALPHA_RE.search(name):
                moves.append(Move(path.relative_to(root).as_posix(), f"docs/{alpha_category(name)}/{folder}/{name}"))
    return moves


def git_files(root: Path) -> list[str]:
    completed = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                               capture_output=True, check=True)
    return [os.fsdecode(v) for v in completed.stdout.split(b"\0") if v]


def executable_references(root: Path, names: set[str]) -> dict[str, str]:
    """Pin documents named by executable source to avoid breaking path contracts."""
    refs: dict[str, str] = {}
    for rel in git_files(root):
        path = root / rel
        if not path.is_file() or path.suffix.lower() not in CODE_EXTENSIONS:
            continue
        if rel.startswith("docs/") or rel in {"tools/docs_layout.py", "tests/test_docs_layout.py"}:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # A filename token used by a test, CLI, or setup script may be a path contract.
        for n in names:
            if n not in refs and n in content:
                refs[n] = rel
        if len(refs) == len(names):
            break
    return refs


def planned_moves(root: Path) -> tuple[list[Move], dict[str, str]]:
    tracked = set(git_files(root))
    candidates = [m for m in raw_moves(root) if m.old in tracked]
    pins = executable_references(root, {PurePosixPath(m.old).name for m in candidates})
    return [m for m in candidates if PurePosixPath(m.old).name not in pins], pins


def original_target(link: str, old_file: str, known: set[str]) -> str | None:
    """Resolve relative Markdown links using the *old* document location."""
    if not link or link.startswith(("#", "/", "mailto:", "data:", "//")) or ":" in link.split("/", 1)[0]:
        return None
    no_fragment = link.split("#", 1)[0].split("?", 1)[0]
    if not no_fragment:
        return None
    no_fragment = unquote(no_fragment)
    old_dir = posixpath.dirname(old_file)
    rel_target = posixpath.normpath(posixpath.join(old_dir, no_fragment))
    if rel_target in known:
        return rel_target
    # Some docs use repository-root-relative 'docs/foo.md' in links.
    if no_fragment.startswith("docs/") and no_fragment in known:
        return no_fragment
    return None


def rewrite_document(text: str, old_file: str, new_file: str,
                     moves: dict[str, str], known: set[str]) -> str:
    """Rebase resolvable Markdown links and explicit repo-root paths.

    Preserve external URLs, anchor-only links, and unknown existing links.
    """
    def replace_link(match: re.Match[str]) -> str:
        original = match.group("url")
        enclosed = original.startswith("<") and original.endswith(">")
        link = original[1:-1] if enclosed else original
        target = original_target(link, old_file, known)
        if target is None:
            return original
        new_target = moves.get(target, target)
        suffix = link[len(link.split("#", 1)[0].split("?", 1)[0]):]
        rebased = posixpath.relpath(new_target, posixpath.dirname(new_file) or ".")
        # Keep ./ for an existing explicit ./ link.
        if link.startswith("./") and not rebased.startswith((".", "/")):
            rebased = "./" + rebased
        rewritten = rebased + suffix
        return f"<{rewritten}>" if enclosed else rewritten

    result = LINK_RE.sub(replace_link, text)
    # Root-qualified paths in inline code, prose and GitHub /blob/main URLs.
    for before, after in sorted(moves.items(), key=lambda entry: len(entry[0]), reverse=True):
        result = result.replace(before, after)
    return result


def protected_changes(root: Path, touched: set[str]) -> list[str]:
    status = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no", "-z"],
                            capture_output=True, check=True)
    bad = []
    for part in status.stdout.split(b"\0"):
        if not part:
            continue
        line = os.fsdecode(part)
        if len(line) < 4:
            continue
        rel = line[3:]
        if rel in touched:
            bad.append(rel)
    return sorted(set(bad))


def apply_moves(root: Path, moves: list[Move]) -> int:
    mapping = {m.old: m.new for m in moves}
    targets = [root / m.new for m in moves]
    if len(set(targets)) != len(targets):
        raise ValueError("To filer har samme målsti. Ingen filer er flyttet.")
    duplicates = [m.new for m in moves if (root / m.new).exists()]
    if duplicates:
        raise ValueError("Målsti finnes fra før: " + ", ".join(duplicates[:6]))

    # Scan everything before moving so links resolve against the old tree.
    old_known = {Path(p).as_posix() for p in git_files(root)}
    old_known.update(m.old for m in moves)
    # Directories are valid Markdown targets too, e.g. [Images](images/).
    for rel in list(old_known):
        parent = posixpath.dirname(rel)
        while parent and parent not in old_known:
            old_known.add(parent)
            parent = posixpath.dirname(parent)
    markdown = []
    for rel in sorted(old_known | {"docs/README.md"}):
        if rel.startswith(("docs/test-results/", "docs/manual-test-results/", "docs/reference-material/")):
            continue  # Generated or preserved evidence is not edited by documentation cleanup.
        if rel.lower().endswith(".md") and (root / rel).is_file():
            markdown.append(rel)
    rewritten: dict[str, str] = {}
    for rel in markdown:
        source = root / rel
        try:
            content = source.read_text(encoding="utf-8")
        except (UnicodeError, OSError):
            continue
        target = mapping.get(rel, rel)
        updated = rewrite_document(content, rel, target, mapping, old_known)
        if content != updated:
            rewritten[target] = updated

    # Do not overwrite unstaged changes in files affected by the migration.
    touched = {m.old for m in moves}
    for rel in rewritten:
        if rel not in mapping.values():
            touched.add(rel)
    dirty = protected_changes(root, touched)
    if dirty:
        raise ValueError("Lagre/commit lokale endringer før opprydding i: " + ", ".join(dirty[:12]))

    for move in moves:
        (root / move.new).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "-C", str(root), "mv", "--", move.old, move.new], check=True)
    for rel, updated in rewritten.items():
        (root / rel).write_text(updated, encoding="utf-8")
    return len(rewritten)


def show_plan(moves: list[Move], pins: dict[str, str]) -> None:
    grouped = Counter(posixpath.dirname(m.new) for m in moves)
    print(f"Filer som flyttes: {len(moves)}")
    for folder, count in sorted(grouped.items()):
        print(f"  {folder}/: {count}")
    if pins:
        print(f"Beholdt på opprinnelig sti pga. referanser i kjørbar kode: {len(pins)}")
        for name, referencing in sorted(pins.items()):
            print(f"  {name}  (brukt i {referencing})")
    print("Ingen Source/Work-, testresultat- eller release-kontrollfiler flyttes.")



def root_layout_issues(root: Path) -> list[str]:
    """Persistent hygiene guard: new docs must not clutter the docs root.

    The frozen legacy exceptions retain compatibility with existing tests.
    Current-series per-alpha notes are forbidden ANYWHERE under docs, except
    generated test results; record increment changes in canonical documents.
    """
    root = Path(root)
    docs = root / "docs"
    problems: list[str] = []
    if not docs.is_dir():
        return ["Mangler docs/."]
    for item in sorted(docs.iterdir()):
        if not item.is_file() or item.name.startswith("."):
            continue
        if (item.name not in ROOT_DOCUMENTS
                and item.name not in LEGACY_ROOT_DOCUMENTS
                and not RELEASE_NOTES_RE.fullmatch(item.name)):
            problems.append(f"Ny eller feilplassert fil i docs/-roten: {item.name}")

    version_file = root / "version.py"
    try:
        version = re.search(
            r'(?m)^VERSION = "(\d+)\.(\d+)\.(\d+)(?:-a\d+)?"$',
            version_file.read_text(encoding="utf-8"),
        )
    except OSError:
        version = None
    if version:
        a, b, c = [int(part) for part in version.groups()]
        # New alpha documents for the CURRENT series should be integrated into
        # permanent docs; historical alpha records from older series remain.
        patterns = (
            re.compile(rf"(?:^|[-_])v{a}\.{b}\.{c}-a\d+", re.I),
            re.compile(rf"(?:^|[-_])v{a}{b}{c}-a\d+", re.I),
            re.compile(rf"(?:^|[-_])v0?{a}{b}{c}-a\d+", re.I),
        )
        for file in docs.rglob("*"):
            if not file.is_file() or file.suffix.lower() not in {".md", ".json"}:
                continue
            path = file.relative_to(docs).as_posix()
            if path.startswith(("test-results/", "manual-test-results/")):
                continue
            if any(pattern.search(file.name) for pattern in patterns):
                problems.append(f"Alpha-notat for gjeldende versjon skal ikke lagres i docs/: {path}")
    return problems


def main(argv: list[str] | None = None, *, root: Path | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--plan", action="store_true", help="Vis oversikt uten endringer")
    group.add_argument("--apply", action="store_true", help="Flytt med git mv og oppdater interne lenker")
    group.add_argument("--check", action="store_true", help="Kontroller at oppryddingen er utført")
    args = parser.parse_args(argv)
    repo = Path(root) if root else Path(__file__).resolve().parents[1]
    try:
        if not (repo / ".git").exists() or not (repo / "docs" / "RELEASES.md").exists():
            raise ValueError("Kommandoen må kjøres i det lokale DWM Git-repositoriet.")
        moves, pins = planned_moves(repo)
        if args.check:
            issues = root_layout_issues(repo)
            if moves:
                issues.append(f"{len(moves)} eldre filer gjenstår å flytte; kjør --apply.")
            if not (repo / "docs" / "README.md").is_file():
                issues.append("Mangler docs/README.md")
            if issues:
                for issue in issues:
                    print("[DOKUMENTASJON] " + issue)
                return 1
            print("[OK] docs-layout: ingen nye rotfiler eller alpha-notater; historikk bevart.")
            return 0
        show_plan(moves, pins)
        if args.plan:
            return 0
        if not moves:
            print("[OK] Ingen flyttinger gjenstår.")
            return 0
        updated = apply_moves(repo, moves)
        remaining = sum(1 for p in (repo / "docs").iterdir() if p.is_file())
        print(f"[OK] Flyttet {len(moves)} dokumenter og oppdatert {updated} Markdown-filer.")
        print(f"Filer igjen direkte i docs/: {remaining}")
        print("Kontroller med: py tools/docs_layout.py --check")
        print("Deretter: test.bat og git status -sb. Commit/push utføres manuelt.")
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"[FEIL] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
