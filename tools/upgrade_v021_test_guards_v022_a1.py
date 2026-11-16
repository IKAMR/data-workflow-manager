"""One-time, fail-closed migration of five historical 0.2.1 alpha-only tests.

Does not change program code, Source, Work, the test runner or test results.
Tests keep all functional assertions. See docs/DEPOTPROFIL-V022-A1.md.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MILESTONES = (
    ("tests/test_v021_a1_xpath_audit.py", 1),
    ("tests/test_v021_a2_xpath_regression.py", 2),
    ("tests/test_v021_a3_xpath_version_qa.py", 3),
    ("tests/test_v021_a4_xpath_metadata_qa.py", 4),
    ("tests/test_v021_a7_requirement_matrix.py", 7),
)


def upgrade(source: str, alpha: int) -> str:
    """Replace only the isolated, obsolete release-series test assertion."""
    new_marker = f'assert_release_at_least(self, f\'VERSION = "{{VERSION}}"\', "0.2.1", {alpha})'
    if new_marker in source:
        if source.count(new_marker) != 1:
            raise ValueError("Duplisert, allerede korrigert versjonsvakt.")
        return source
    lines = source.splitlines(keepends=True)
    candidates = [i for i, line in enumerate(lines)
                  if 'self.assertRegex(VERSION' in line and "0\\.2\\.1" in line]
    if len(candidates) != 1:
        raise ValueError(f"Forventet én gammel v0.2.1-versjonsvakt for a{alpha}; fant {len(candidates)}.")
    i = candidates[0]
    line = lines[i]
    if not re.fullmatch(r"\s*self\.assertRegex\(VERSION,\s*r['\"]\^0\\\.2\\\.1.*\$['\"]\)\s*", line):
        raise ValueError("Ukjent versjonsvakt; nekter å skrive om funksjonstester.")
    indent = line[:len(line) - len(line.lstrip())]
    lines[i] = (indent + "from tests.version_assertions import assert_release_at_least\n"
                + indent + new_marker + "\n")
    return ''.join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Les/kontroller uten skriving')
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    version = (root / 'version.py').read_text(encoding='utf8')
    if version != 'APP_NAME = "Data Workflow Manager"\nVERSION = "0.2.2-a1"\n':
        raise ValueError("Forventet fysisk DWM-versjon 0.2.2-a1 – ingen filer endret.")
    updates = {}
    for relative, alpha in MILESTONES:
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError("Krever vanlig lokal testfil: " + relative)
        original = path.read_text(encoding='utf8')
        updated = upgrade(original, alpha)
        updates[path] = updated
    print("Kildekontroll OK: 5 historiske versjonsvakter.")
    if not args.check:
        for path, text in updates.items():
            if path.read_text(encoding='utf8') != text:
                path.write_text(text, encoding='utf8')
                print("Versjonsvakt: " + str(path.relative_to(root)))
    print("Ingen tekniske testkrav, kildedata eller vurderingsresultater endret.")
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print("[FEIL] " + str(exc), file=sys.stderr)
        raise SystemExit(1)
