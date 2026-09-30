from __future__ import annotations

from .depot_result_center_a23_13 import DepotResultCenterDialogA23_13


class DepotResultCenterDialogA23_14(DepotResultCenterDialogA23_13):
    """a23.14: reliably reset Resultat og evidens to top after control navigation."""

    @staticmethod
    def _a2314_scroll_evidence_top(frame) -> None:
        try:
            frame.update_idletasks()
        except Exception:
            pass

        # CTkScrollableFrame keeps its scrollable canvas internally.
        candidates = (
            getattr(frame, "_parent_canvas", None),
            getattr(frame, "_canvas", None),
        )
        for canvas in candidates:
            if canvas is None:
                continue
            try:
                canvas.yview_moveto(0.0)
                return
            except Exception:
                pass

        # Fallback for CustomTkinter variants where the canvas is nested.
        try:
            for child in frame.winfo_children():
                if hasattr(child, "yview_moveto"):
                    child.yview_moveto(0.0)
                    return
        except Exception:
            pass

    def _a232_render_evidence(self, parent, index: int, item: dict) -> None:
        # Render first, then move the viewport.  a23.13 reset during _a232_clear,
        # which happened before the new widgets changed the scrollregion.
        result = super()._a232_render_evidence(parent, index, item)

        def _reset():
            self._a2314_scroll_evidence_top(parent)

        try:
            parent.after_idle(_reset)
            parent.after(25, _reset)
        except Exception:
            _reset()

        return result
