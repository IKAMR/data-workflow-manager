"""Reusable, conservative alpha-to-final release preparation for DWM.

Run from a local repo checkout:
    py tools/release_prepare.py --check
    py tools/release_prepare.py --promote

--check is read-only. --promote is an optional DEVELOPER command, not a
post-install patch: it changes only version.py and pyproject.toml after final
release notes/history and future-version tests pass preflight. Full test.bat,
review, commit/push/tag remain separate user-controlled steps.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import tomllib

# Running as `py tools/release_prepare.py` sets sys.path[0] to tools/.
from release_gate import VERSION_RE, release_errors

PACKAGE_VERSION_RE = re.compile(r'(?m)^version = "([^"]+)"$')


def current_identity(root: Path) -> tuple[str, str | None]:
    """Return (release, alpha index) from the exact physical version.py."""
    raw = (root / "version.py").read_text(encoding="utf-8")
    match = VERSION_RE.fullmatch(raw)
    if not match:
        raise ValueError("version.py har uventet format; ingen filer er endret")
    a, b, c, alpha = match.groups()
    return f"{a}.{b}.{c}", alpha


def release_documents_ready(root: Path, release: str) -> list[str]:
    """Never auto-generate filler release notes or truncate release history."""
    problems = []
    if not (root / "docs" / f"RELEASE-v{release}.md").is_file():
        problems.append(f"Mangler faglig gjennomgåtte docs/RELEASE-v{release}.md")
    try:
        text = (root / "docs" / "RELEASES.md").read_text(encoding="utf-8")
    except OSError as exc:
        problems.append(f"Kan ikke lese docs/RELEASES.md: {exc}")
    else:
        if text.count(f"## v{release}\n") != 1:
            problems.append(f"docs/RELEASES.md trenger nøyaktig én '## v{release}'-oppføring")
    return problems


def promote(root: Path) -> tuple[bool, list[str]]:
    """Validate first, then replace two version declarations, rollback on error."""
    root = Path(root)
    try:
        release, alpha = current_identity(root)
    except (OSError, ValueError) as exc:
        return False, [str(exc)]
    if alpha is None:
        return False, [f"Allerede ferdig release v{release}; ingenting endret"]

    blockers = release_errors(root, require_final=False)
    blockers.extend(release_documents_ready(root, release))
    if blockers:
        return False, blockers

    app_file = root / "version.py"
    packaging_file = root / "pyproject.toml"
    before_app = app_file.read_text(encoding="utf-8")
    before_packaging = packaging_file.read_text(encoding="utf-8")
    matches = list(PACKAGE_VERSION_RE.finditer(before_packaging))
    if len(matches) != 1 or matches[0].group(1) != f"{release}a{alpha}":
        return False, ["Kan ikke bytte distribusjonsversjon sikkert; pyproject.toml er uventet"]

    final_app = f'APP_NAME = "Data Workflow Manager"\nVERSION = "{release}"\n'
    final_packaging = PACKAGE_VERSION_RE.sub(f'version = "{release}"', before_packaging, count=1)
    try:
        app_file.write_text(final_app, encoding="utf-8")
        packaging_file.write_text(final_packaging, encoding="utf-8")
        issues = release_errors(root, require_final=True)
        if issues:
            raise ValueError("; ".join(issues))
    except (OSError, ValueError) as exc:
        # Never leave mixed runtime/distribution versions on a failed promotion.
        app_file.write_text(before_app, encoding="utf-8")
        packaging_file.write_text(before_packaging, encoding="utf-8")
        return False, [f"Promotering avbrutt og versjonsfiler gjenopprettet: {exc}"]
    return True, []


def main(argv: list[str] | None = None, *, root: Path | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="Les kun; test alpha/release-beredskap")
    group.add_argument("--promote", action="store_true", help="Bytt til ferdig versjon når docs er klar")
    args = parser.parse_args(argv)
    repo = Path(root) if root else Path(__file__).resolve().parents[1]
    try:
        release, alpha = current_identity(repo)
    except (OSError, ValueError) as exc:
        print("[FEIL] " + str(exc))
        return 2

    if args.check:
        blockers = release_errors(repo, require_final=alpha is None)
        if blockers:
            for problem in blockers:
                print("[SPERRE] " + problem)
            return 1
        if alpha is None:
            print(f"[OK] Ferdig release v{release} har konsistente metadata, tester og release-notater.")
        else:
            print(f"[OK] v{release}-a{alpha} er kompatibel med en senere v{release}-release.")
            for problem in release_documents_ready(repo, release):
                print("[SENERE] " + problem)
        print("[MERK] Full test.bat og praktisk testing kreves fortsatt.")
        return 0

    ok, problems = promote(repo)
    if not ok:
        for problem in problems:
            print("[INGEN ENDRING] " + problem)
        return 1
    print(f"[OK] Versjonsfilene er klargjort for v{release}.")
    print("Kjør py tools/release_gate.py og full test.bat før commit, push eller tag.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
