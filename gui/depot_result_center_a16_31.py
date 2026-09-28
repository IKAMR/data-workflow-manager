from __future__ import annotations

from .depot_result_center_a16_30 import DepotResultCenterDialogA16_30


class DepotResultCenterDialogA16_31(DepotResultCenterDialogA16_30):
    """a16.31: avoid legacy controls renderer after structured controls replaced it."""

    def _render_a169_controls(self, index: int) -> None:
        # a16.25 replaced the old _a168_controls_table with the structured
        # controls surface. Older renderers still call this hook while archive
        # selection changes; never touch the destroyed legacy widget here.
        render = getattr(self, "_render_structured_controls", None)
        if callable(render):
            render(index)
