"""DWM v0.2.2-a7: stable dependency numbers for Noark 5 operations.

The numbers identify *operations*, not their current position in a job. A
prerequisite applies when both operations are selected; required prerequisites
for the new a7 pipeline are checked separately. Existing completed job lists
are not rewritten on load.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Dependency:
    number: int
    operation_id: str
    phase: str
    follows: tuple[int, ...] = ()
    required: tuple[int, ...] = ()


SPECS = (
    Dependency(100, 'metadata_inventory', 'technical'),
    Dependency(110, 'validate_xml_schema', 'technical'),
    Dependency(120, 'analyse_arkivstruktur', 'technical'),
    Dependency(130, 'run_noark5_xpath_tests_2026', 'technical'),
    Dependency(140, 'siegfried_pronom_identification', 'technical'),
    Dependency(150, 'arkade5_noark5_test', 'technical'),
    Dependency(160, 'arkade5_pronom_analysis', 'technical'),
    Dependency(170, 'analyse_noark5_core', 'technical'),
    Dependency(180, 'analyse_noark5_u1', 'technical'),
    Dependency(190, 'run_noark5_xpath_regression', 'technical'),
    Dependency(200, 'import_arkade5_reports', 'processing', (150, 160)),
    Dependency(210, 'build_noark5_canonical_evidence', 'processing',
               (130, 140, 150, 160, 200), (130,)),
    Dependency(220, 'analyze_noark5_external_evidence', 'processing',
               (210,), (210,)),
    Dependency(230, 'audit_noark5_evidence', 'processing',
               (210, 220), (210, 220)),
    Dependency(240, 'compose_noark5_views', 'processing', (130, 230)),
    Dependency(250, 'build_noark5_depot_report', 'processing',
               (130, 200, 230, 240)),
    Dependency(260, 'build_noark5_qa_draft', 'processing',
               (230, 250), (230, 250)),
    Dependency(900, 'dias_package', 'packaging', (260,)),
)
BY_ID = {spec.operation_id: spec for spec in SPECS}
BY_NUMBER = {spec.number: spec for spec in SPECS}
assert len(BY_ID) == len(SPECS) == len(BY_NUMBER)

NEW_A7 = ('build_noark5_canonical_evidence',
          'analyze_noark5_external_evidence',
          'audit_noark5_evidence',
          'build_noark5_qa_draft')
AFTER_TESTS = ('import_arkade5_reports', *NEW_A7[:3],
               'compose_noark5_views', 'build_noark5_depot_report',
               NEW_A7[3])
ARKADE = ('arkade5_noark5_test', 'arkade5_pronom_analysis')


def dependency_number(operation_id: str) -> int | None:
    spec = BY_ID.get(str(operation_id))
    return spec.number if spec else None


def dependency_label(operation_id: str) -> str:
    no = dependency_number(operation_id)
    return f'A{no:03d}' if no is not None else 'A???'


def dependency_links(operation_id: str, selected: Iterable[str] = ()) -> tuple[str, ...]:
    spec = BY_ID.get(operation_id)
    if spec is None:
        return ()
    present = set(selected)
    return tuple(f'A{number:03d} ({BY_NUMBER[number].operation_id})'
                 for number in spec.follows
                 if BY_NUMBER[number].operation_id in present)


def validate_dependencies(operation_ids: Iterable[str], *,
                          strict_new: bool | None = None) -> tuple[str, ...]:
    ids = tuple(str(value) for value in operation_ids)
    if len(ids) != len(set(ids)):
        return ('Dupliserte deljobb-ID-er.',)
    order = {value: i for i, value in enumerate(ids)}
    if strict_new is None:
        strict_new = any(x in order for x in NEW_A7)
    failures: list[str] = []
    for op_id in ids:
        spec = BY_ID.get(op_id)
        if not spec:
            # Legacy/custom registries can have additional known operations.
            continue
        for number in spec.follows:
            prior = BY_NUMBER[number].operation_id
            if prior in order and order[prior] >= order[op_id]:
                failures.append(f'{dependency_label(op_id)} {op_id} maa komme etter '
                                f'A{number:03d} {prior}.')
        if strict_new:
            for number in spec.required:
                prior = BY_NUMBER[number].operation_id
                if prior not in order:
                    failures.append(f'{dependency_label(op_id)} {op_id} krever '
                                    f'A{number:03d} {prior}.')
    return tuple(failures)


def is_valid_order(ids: Iterable[str]) -> bool:
    return not validate_dependencies(ids)


def ensure_a7_processing(operation_ids: Iterable[str]) -> tuple[str, ...]:
    """Configure automatic processing for NEW Noark workflows only.

    No migration of previously completed jobs happens in this function.
    Used by Basic when composing a fresh plan, by configured new presets, and
    by explicit user-triggered migration of an existing workflow.
    """
    ids = tuple(operation_ids)
    if 'run_noark5_xpath_tests_2026' not in ids:
        return ids  # Arkade-only, selective or historical workflow.
    tech = [oid for oid in ids if oid not in AFTER_TESTS]
    if any(oid in tech for oid in ARKADE):
        tech.append('import_arkade5_reports')
    tech.extend(('build_noark5_canonical_evidence',
                 'analyze_noark5_external_evidence',
                 'audit_noark5_evidence', 'compose_noark5_views',
                 'build_noark5_depot_report', 'build_noark5_qa_draft'))
    # Keep any optional package creation after the analysis.
    if 'dias_package' in tech:
        tech.remove('dias_package')
        tech.append('dias_package')
    if len(tech) != len(set(tech)):
        raise ValueError('Arbeidsflyten inneholder dupliserte deljobber.')
    issues = validate_dependencies(tech)
    if issues:
        raise ValueError('Ugyldig a7-standardflyt: ' + '; '.join(issues))
    return tuple(tech)


def arkade_last_with_dependencies(operation_ids: Iterable[str]) -> tuple[str, ...]:
    """Last two technical tests are Arkade Noark/PRONOM, then processing."""
    from app.workflow_order_v022_a6 import checked_order
    ids = tuple(operation_ids)
    tech = [oid for oid in ids if oid not in AFTER_TESTS and oid != 'dias_package']
    tail = [oid for oid in ARKADE if oid in tech]
    tech = [oid for oid in tech if oid not in ARKADE] + tail
    post = [oid for oid in AFTER_TESTS if oid in ids]
    packages = [oid for oid in ids if oid == 'dias_package']
    proposed = checked_order(ids, [*tech, *post, *packages])
    failures = validate_dependencies(proposed)
    if failures:
        raise ValueError('Klarte ikke plassere avhengige deljobber: ' + '; '.join(failures))
    return proposed
