"""One-time removal of an obsolete v0.2.7-a7 alpha note from docs/quality.

Run from the repo: py tools/apply_v027_a7_fix3.py
"""
from __future__ import annotations

from pathlib import Path
import sys


OLD = "NOARK5-PUID-OVERSIKT-KOPIHISTORIKK-v027-a7.md"
CURRENT = "NOARK5-PUID-OVERSIKT-KOPIHISTORIKK.md"


def apply(root: Path) -> None:
    if not (root / "version.py").is_file() or not (root / "tools" / "docs_layout.py").is_file():
        raise ValueError("Run from a Data Workflow Manager checkout")
    folder = root / "docs" / "quality"
    stale = folder / OLD
    canonical = folder / CURRENT
    if stale.is_symlink() or canonical.is_symlink():
        raise ValueError("Refusing to change a symlink")
    if stale.exists():
        if not stale.is_file():
            raise ValueError("Unexpected path type: " + str(stale))
        if canonical.exists():
            if not canonical.is_file():
                raise ValueError("Unexpected canonical path type")
            stale.unlink()  # Redundant alpha note; canonical document is retained.
        else:
            stale.rename(canonical)  # Keep the only copy, under permanent name.
    if stale.exists():
        raise RuntimeError("Obsolete alpha note still exists: " + str(stale))
    if not canonical.is_file():
        raise RuntimeError("Canonical quality document is missing")
    # Use the same guard that failed in test.bat to prove this exact issue is fixed.
    sys.path.insert(0, str(root / "tools"))
    from docs_layout import root_layout_issues
    issues = root_layout_issues(root)
    if issues:
        raise RuntimeError("docs-layout: " + "; ".join(issues))


def main() -> int:
    try:
        apply(Path(__file__).resolve().parents[1])
    except (OSError, RuntimeError, ValueError) as exc:
        print("[FEIL] " + str(exc), file=sys.stderr)
        return 1
    print("[OK] Overflodig a7-dokument fjernet, docs-layout-kontroll bestatt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
