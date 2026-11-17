"""v0.2.2-a6: pure per-job Noark 5 workflow ordering rules.

Only the order is changed: all operation IDs are preserved exactly once.
No files, Work evidence, checkpoints or UI state are written by this module.
"""
from __future__ import annotations

from collections import Counter
from typing import Iterable

ARKADE_NOARK5 = "arkade5_noark5_test"
ARKADE_PRONOM = "arkade5_pronom_analysis"
ARKADE_LAST = (ARKADE_NOARK5, ARKADE_PRONOM)


def checked_order(original: Iterable[str], proposed: Iterable[str]) -> tuple[str, ...]:
    """Reject addition, removal, duplication, or substitution of operations."""
    before = tuple(str(value) for value in original)
    after = tuple(str(value) for value in proposed)
    if not before or len(before) != len(set(before)) or not all(before):
        raise ValueError("Eksisterende deljobbliste er tom eller ugyldig.")
    if len(after) != len(set(after)) or Counter(before) != Counter(after):
        raise ValueError("Rekkefølgen kan endres, men ingen deljobber kan legges til eller fjernes her.")
    return after


def move_operation(operation_ids: Iterable[str], index: int, offset: int) -> tuple[str, ...]:
    """Move one operation a single step, preserving membership and all others."""
    ids = tuple(operation_ids)
    checked_order(ids, ids)
    if offset not in (-1, 1):
        raise ValueError("Bruk Opp eller Ned for å endre rekkefølge.")
    if index < 0 or index >= len(ids):
        raise ValueError("Velg en deljobb i listen.")
    target = index + offset
    if target < 0 or target >= len(ids):
        return ids
    reordered = list(ids)
    reordered[index], reordered[target] = reordered[target], reordered[index]
    return checked_order(ids, reordered)


def arkade_last_order(operation_ids: Iterable[str]) -> tuple[str, ...]:
    """Place Arkade Noark test second-last and Arkade PRONOM last when present.

    All non-Arkade operations stay in their existing relative order.
    This is an operator-invoked *preset*, never an automatic global migration.
    """
    ids = tuple(operation_ids)
    checked_order(ids, ids)
    tail = [item for item in ARKADE_LAST if item in ids]
    return checked_order(ids, [item for item in ids if item not in ARKADE_LAST] + tail)


def preserved_basic_order(current: Iterable[str], basic_generated: Iterable[str]) -> tuple[str, ...]:
    """Basic's checkboxes define membership, never overwrite manual ordering.

    If membership changes, Basic's existing composition order is appropriate.
    If the same operations are selected, keep the user's per-job order.
    """
    original = tuple(current)
    proposed = tuple(basic_generated)
    if len(original) == len(set(original)) and Counter(original) == Counter(proposed):
        return original
    return proposed


def ordering_warnings(operation_ids: Iterable[str]) -> tuple[str, ...]:
    """Warn about downstream evidence snapshots, without overriding user choice."""
    ids = tuple(operation_ids)
    checked_order(ids, ids)
    at = {value: pos for pos, value in enumerate(ids)}
    warnings = []
    arkade = tuple(item for item in ARKADE_LAST if item in at)
    if "import_arkade5_reports" in at and any(
        at["import_arkade5_reports"] < at[item] for item in arkade
    ):
        warnings.append(
            "Arkade-importen ligger før én eller begge Arkade-kontrollene. "
            "Nye Arkade-resultater blir ikke importert i samme passering."
        )
    if "build_noark5_depot_report" in at and any(
        at["build_noark5_depot_report"] < at[item] for item in arkade
    ):
        warnings.append(
            "Depotrapporten produseres før nye Arkade-resultater er klare. "
            "Importer resultatene og bygg rapporten på nytt etterpå dersom de skal inngå."
        )
    if ("run_noark5_xpath_tests_2026" in at and "compose_noark5_views" in at
            and at["compose_noark5_views"] < at["run_noark5_xpath_tests_2026"]):
        warnings.append("Resultatvisningene bygges før XPath-kontrollene.")
    if ("compose_noark5_views" in at and "build_noark5_depot_report" in at
            and at["build_noark5_depot_report"] < at["compose_noark5_views"]):
        warnings.append("Depotrapporten bygges før resultatvisningene.")
    return tuple(warnings)
