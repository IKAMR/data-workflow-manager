from __future__ import annotations

from .depot_result_center_a17_3 import DepotResultCenterDialogA17_3


class DepotResultCenterDialogA17_4(DepotResultCenterDialogA17_3):
    """a17.4: keep virtual multi-selection out of legacy per-row health indexing."""

    def _a174_is_virtual_index(self, index: int | None = None) -> bool:
        parts = getattr(self, "_archive_parts", []) or []
        if index is None:
            index = getattr(self, "_archive_index", -1)
        return (
            isinstance(index, int)
            and 0 <= index < len(parts)
            and bool(parts[index].get("is_virtual_selection"))
        )

    def _update_health_strip(self) -> None:
        """Render a virtual-selection health text without indexing _archive_health.

        _archive_health is created only for the real/synthetic navigation rows that
        existed during construction.  The temporary multi-select aggregate is
        appended later and must therefore never be used as an index into that list.
        """
        if not self._a174_is_virtual_index():
            return super()._update_health_strip()

        selected = len(getattr(self, "_a171_selected", set()) or set())
        label = getattr(self, "_health_label", None)
        if label is not None:
            try:
                label.configure(
                    text=(
                        f"Virtuelt utvalg: {selected} valgte arkivdeler  |  "
                        "Datagrunnlaget summeres fra de valgte arkivdelene."
                    )
                )
            except Exception:
                pass

        for name in ("_prev_button", "_next_button"):
            button = getattr(self, name, None)
            if button is not None:
                try:
                    button.configure(state="disabled")
                except Exception:
                    pass

        queue = getattr(self, "_queue_position_label", None)
        if queue is not None:
            try:
                queue.configure(text=f"Virtuelt utvalg: {selected} valgte arkivdeler")
            except Exception:
                pass

    def _update_a8_queue_position(self) -> None:
        if self._a174_is_virtual_index():
            label = getattr(self, "_queue_position_label", None)
            if label is not None:
                try:
                    label.configure(
                        text=f"Virtuelt utvalg: {len(getattr(self, '_a171_selected', set()) or set())} valgte arkivdeler"
                    )
                except Exception:
                    pass
            return
        return super()._update_a8_queue_position()

    def _update_a7_queue_controls(self) -> None:
        if self._a174_is_virtual_index():
            button = getattr(self, "_next_missing_button", None)
            if button is not None:
                try:
                    button.configure(state="disabled")
                except Exception:
                    pass
            return
        return super()._update_a7_queue_controls()
