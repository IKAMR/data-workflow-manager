"""Pure layout decisions for the canonical Work dialog (Qt independent)."""
from __future__ import annotations

from math import ceil


def content_split(total: int, tree_need: int, report_need: int,
                  *, tree_min: int = 100, report_min: int = 100) -> tuple[int, int]:
    """Allocate height by actual content need, with scrollable minima.

    Content uses only the minimum height it needs; surplus goes to the view
    with more remaining content. If both fit, split surplus evenly.
    """
    total = max(2, int(total))
    tree_min = max(1, min(int(tree_min), total // 2))
    report_min = max(1, min(int(report_min), total - tree_min))
    tree = max(tree_min, int(tree_need))
    report = max(report_min, int(report_need))
    if tree + report <= total:
        remaining = total - tree - report
        tree += remaining // 2
        report += remaining - remaining // 2
    else:
        available = total - tree_min - report_min
        tree_excess = max(0, tree - tree_min)
        report_excess = max(0, report - report_min)
        demand = tree_excess + report_excess
        portion = round(available * tree_excess / demand) if demand else available // 2
        tree = tree_min + portion
        report = total - tree
    return tree, report


def button_columns(available_width: int, button_widths: list[int],
                   *, spacing: int = 8, margin: int = 0) -> int:
    """Choose a uniform column count that cannot clip a button row."""
    widths = [max(1, int(w)) for w in button_widths]
    if not widths:
        return 1
    room = max(1, int(available_width) - 2 * margin)
    for count in range(len(widths), 0, -1):
        # Qt grid columns use the maximum width of the buttons in each column.
        columns = [max(widths[i::count]) for i in range(count)]
        if sum(columns) + spacing * (count - 1) <= room:
            return count
    return 1


def text_visual_lines(lines: list[str], available_width: int, char_width: float) -> int:
    """Bounded approximation of wrapped plain-text line count."""
    columns = max(1, int(available_width / max(1.0, char_width)))
    return sum(max(1, ceil(len(line) / columns)) for line in lines)
