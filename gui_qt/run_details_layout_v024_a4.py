"""Pure layout policy for the independent DWM run-details window.

No Qt imports, no job or filesystem access. User sizing always wins over
content-aware defaults when a complete valid preference has been saved.
"""
from __future__ import annotations

import json
from typing import Any

# The operation column uses all spare width by default, but unlike Qt Stretch
# mode it remains manually resizable afterwards.
_HISTORY_BASE = (165, 320, 110, 135, 110)
_HISTORY_MIN = (75, 75, 75, 75, 75)
_HISTORY_MAX = 5000


def saved_history_widths(value: Any) -> tuple[int, int, int, int, int] | None:
    """Decode a QSettings JSON string, rejecting incomplete/corrupt values."""
    if value is None or value == '':
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return None
    if not isinstance(value, (tuple, list)) or len(value) != 5:
        return None
    widths = []
    for item, minimum in zip(value, _HISTORY_MIN):
        if isinstance(item, bool) or not isinstance(item, int):
            return None
        if not minimum <= item <= _HISTORY_MAX:
            return None
        widths.append(item)
    return tuple(widths)


def history_column_widths(viewport_width: int, saved: Any = None) -> tuple[int, int, int, int, int]:
    """Readable default table; preserve valid manually saved widths verbatim."""
    previous = saved_history_widths(saved)
    if previous is not None:
        return previous
    fixed_width = sum(_HISTORY_BASE[i] for i in (0, 2, 3, 4))
    operation_width = max(_HISTORY_BASE[1], int(viewport_width) - fixed_width - 10)
    return (_HISTORY_BASE[0], operation_width, *_HISTORY_BASE[2:])


def content_split_height(
    available: int, rows: int, row_height: int, header_height: int,
    *, min_first: int = 80, min_second: int = 110, max_rows: int = 30,
) -> int:
    """Height for the table in a vertical splitter, leaving room below.

    When a window is too small to show all rows, keep both panels usable and
    let the QTreeWidget scroll. Never use a fixed percentage on tall monitors.
    """
    total = max(0, int(available))
    if not total:
        return 0
    # Even an empty history should show its header and a few rows.
    visible_rows = max(4, min(max(0, int(rows)), max_rows))
    row_size = max(18, int(row_height))
    heading = max(20, int(header_height))
    desired = heading + visible_rows * row_size + 12
    minimum = min(total, max(50, min_first))
    maximum = max(minimum, total - max(80, min_second))
    return min(max(desired, minimum), maximum)


def plan_table_height(available: int, rows: int, row_height: int, header_height: int) -> int:
    return content_split_height(
        available, rows, row_height, header_height,
        min_first=80, min_second=165, max_rows=30,
    )


def history_table_height(available: int, rows: int, row_height: int, header_height: int) -> int:
    return content_split_height(
        available, rows, row_height, header_height,
        min_first=90, min_second=130, max_rows=25,
    )
