"""Stable execution ordering for newly composed Basic workflows only.

Never modifies operation order stored in an existing .n5jobs file.
"""
from __future__ import annotations

from app import basic_start_v0111_a1 as basic

_ORIGINAL = basic.basic_operation_ids


def ordered_basic_operation_ids(controls, *, sequence_loader=None):
    selected = basic.normalize_basic_controls(controls)
    original = _ORIGINAL(selected, sequence_loader=sequence_loader)
    stages = (
        ("metadata_inventory", "validate_xml_schema", "analyse_arkivstruktur",
         "run_noark5_xpath_tests_2026"),
        ("arkade5_noark5_test",),
        ("siegfried_pronom_identification",),
        ("arkade5_pronom_analysis",),
        ("import_arkade5_reports",),
        ("compose_noark5_views", "build_noark5_depot_report"),
    )
    stage_lookup = {name: index for index, stage in enumerate(stages)
                    for name in stage}
    # Stable ordering preserves the relative order of all operations within
    # their group and leaves unknown additions in their original positions.
    return tuple(sorted(original, key=lambda op: stage_lookup.get(op, 0)))


def install_basic_order() -> None:
    """Set the composition hook before any Basic job is prepared."""
    basic.basic_operation_ids = ordered_basic_operation_ids
