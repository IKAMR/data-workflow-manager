"""One-time a7 documentation cleanup; preserves the canonical document.

Run from a DWM checkout: py tools/apply_v027_a7_fix2.py
"""
from __future__ import annotations

from pathlib import Path


OLD = "NOARK5-PUID-OVERSIKT-KOPIHISTORIKK-v027-a7.md"
NEW = "NOARK5-PUID-OVERSIKT-KOPIHISTORIKK.md"


def apply(repo: Path) -> str:
    folder = repo / "docs" / "quality"
    old, new = folder / OLD, folder / NEW
    if old.is_symlink() or new.is_symlink():
        raise ValueError("Dokumentfilene kan ikke være symbolske lenker.")
    if not old.exists():
        if new.is_file():
            return "[OK] a7-dokumentasjonen er allerede ryddet."
        raise FileNotFoundError("Finner verken gammel eller ny a7-dokumentasjon.")
    if not old.is_file():
        raise ValueError("Den gamle dokumentstien er ikke en vanlig fil.")
    if not new.exists():
        old.rename(new)
        return "[OK] a7-dokumentet er flyttet til fast navn uten versjonsmarkør."
    if not new.is_file():
        raise ValueError("Målstien er ikke en vanlig fil.")
    # A git checkout may normalize CRLF; compare logical text before deletion.
    def normalized(path: Path) -> str:
        return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    if normalized(old) != normalized(new):
        raise ValueError("Begge a7-dokumenter finnes, men er forskjellige. Ingen fil er slettet.")
    old.unlink()
    return "[OK] Overflødig alpha-dokument fjernet; fast dokument beholdt."


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    if not (repo / "version.py").is_file() or not (repo / "docs").is_dir():
        print("[FEIL] Pakk ut deltaen i roten til Data Workflow Manager.")
        return 2
    try:
        print(apply(repo))
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        print("[FEIL] " + str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
