"""Apply exact, guarded release-only changes to historical alpha tests and history.

This is a one-time local delta patch, not a test bypass or Git operation.
It changes only five version-guard lines, plus release history. It never reads
or writes archive Source, Work, test results, or any external application data.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
OLD_TESTS = {
    "tests/test_v021_a8_requirement_review.py": 8,
    "tests/test_v021_a9_docx_requirement_registry.py": 9,
    "tests/test_v021_a10_requirement_coverage.py": 10,
    "tests/test_v021_a12_qa_decision.py": 12,
}

RELEASE_HISTORY = '''## v0.2.1

Kildebasert Noark 5-kontroll og faglig depotarbeid: XSD-/XPath- og KDRS Query-QA for v3.1/4.0/5.0; kildebundne KS- og depotrapportutkast med Full-rapport og vedlegg A–D; 49-punkts manuell sjekkliste; 47 Arkade-felt med ytre/indre DIAS/METS-referanser, SHA-256 og Work-historikk; direkte knapper for periode- og depotvurdering. Ingen automatisk depotgodkjenning. Fullt omfang og avgrensninger: `docs/RELEASE-v0.2.1.md`.

## v0.2.0

Qt-basert GUI-rammeverk for depotets produksjonslinje, med Startside, arbeidsprofiler, Work, resultater, rapportering og faglig vurdering. Se `docs/RELEASE-v0.2.0.md`.

## v0.1.15

Kanoniske Noark 5-resultater, integrerte Arkade-kilder og kildesporbare KS-/depotutkast. Se `docs/RELEASE-v0.1.15.md`.

'''


def _replace_old_guard(path: Path, alpha: int) -> str:
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    # An already-patched test is accepted on a repeat run.
    if f'"0.2.1", {alpha})' in source and 'assert_release_at_least' in source:
        return source
    matches = [i for i, line in enumerate(lines) if 'self.assertRegex(VERSION' in line]
    if len(matches) != 1 or '0\\.2\\.1-a' not in lines[matches[0]]:
        raise RuntimeError(f"Ukjent versjonsvakt i {path.relative_to(ROOT)}; ingen fil endret.")
    i = matches[0]
    indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
    lines[i] = (
        indent + "from tests.version_assertions import assert_release_at_least\n"
        + indent + f'assert_release_at_least(self, f\'VERSION = "{{VERSION}}"\', "0.2.1", {alpha})\n'
    )
    return ''.join(lines)


def _replace_a16_guard(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    if 'assert_release_at_least(self, physical_version, "0.2.1", 16)' in source:
        return source
    old = '''        self.assertIn('VERSION = "0.2.1-a16"', (root / "version.py").read_text())
        self.assertIn('version = "0.2.1a16"', (root / "pyproject.toml").read_text())'''
    new = '''        # Final release satisfies the historical a16 feature milestone.
        from tests.version_assertions import assert_release_at_least
        from version import VERSION
        import tomllib
        physical_version = (root / "version.py").read_text(encoding="utf-8")
        assert_release_at_least(self, physical_version, "0.2.1", 16)
        with (root / "pyproject.toml").open("rb") as handle:
            distribution_version = tomllib.load(handle)["project"]["version"]
        self.assertEqual(distribution_version, VERSION.replace("-a", "a"))'''
    if source.count(old) != 1:
        raise RuntimeError(f"Ukjent a16-versjonsvakt i {path.relative_to(ROOT)}; ingen fil endret.")
    return source.replace(old, new)


def _release_history(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    if '## v0.2.1\n' in source:
        return source
    marker = '## v0.1.14\n'
    if source.count(marker) != 1:
        raise RuntimeError(f"Kan ikke finne entydig historikk-anker i {path.relative_to(ROOT)}.")
    # Avoid duplicate historical entries if an earlier release already added them.
    sections = RELEASE_HISTORY
    if '## v0.2.0\n' in source:
        sections = sections[:sections.index('## v0.2.0\n')] + sections[sections.index('## v0.1.15\n'):]
    if '## v0.1.15\n' in source:
        sections = sections[:sections.index('## v0.1.15\n')]
    return source.replace(marker, sections + marker, 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ferdigstill lokale v0.2.1 release-vakter og versjonshistorikk")
    parser.add_argument('--check', action='store_true', help='Forhåndskontroll uten skriving')
    args = parser.parse_args(argv)
    version = (ROOT / 'version.py').read_text(encoding='utf-8')
    if version != 'APP_NAME = "Data Workflow Manager"\nVERSION = "0.2.1"\n':
        raise RuntimeError('Forventet ren v0.2.1 i version.py; stoppet.')
    updates: dict[Path, str] = {}
    for relative, alpha in OLD_TESTS.items():
        path = ROOT / relative
        updates[path] = _replace_old_guard(path, alpha)
    path = ROOT / 'tests/test_v021_a16_complete_dias_metadata.py'
    updates[path] = _replace_a16_guard(path)
    path = ROOT / 'docs/RELEASES.md'
    updates[path] = _release_history(path)
    for path, result in updates.items():
        if not args.check and path.read_text(encoding='utf-8') != result:
            path.write_text(result, encoding='utf-8')
        print(('Kontrollert: ' if args.check else 'OK: ') + str(path.relative_to(ROOT)))
    print('Ingen Git-operasjoner eller endringer i Source/Work.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'[FEIL] {exc}', file=sys.stderr)
        raise SystemExit(1)
