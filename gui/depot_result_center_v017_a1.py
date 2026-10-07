from __future__ import annotations

from .depot_result_center_a16_16 import DepotResultCenterDialogA16_16
from .depot_result_center_a19_5 import DepotResultCenterDialogA19_5
from .work_window_state_v017_a1 import install_work_window_state, job_window_state_key


class V017A1DepotResultCenterDialog(DepotResultCenterDialogA19_5):
    """v0.1.7-a1 result window with later period charts and safe initialization.

    a19.5 restores the readable per-year bar profiles for folder/case,
    journalpost and document-description activity.  The historical a16.16
    layer inside that inheritance chain still creates its reviewed-period
    StringVars after the inherited UI starts building.  During that single
    initialization phase we therefore bypass a16.16 and all later overrides;
    once the vars exist the normal a19.5 chain is used in full.
    """

    def __init__(self, master, *, display_name: str = "", **kwargs) -> None:
        self._v017_display_name = str(display_name or "").strip() or "Ukjent uttrekk"
        super().__init__(master, **kwargs)
        # Historical result views default to a tall geometry. Use a practical
        # comparison-friendly first size; persisted user geometry can override it.
        try:
            self.geometry("1180x720")
        except Exception:
            pass
        self._apply_v017_identity_title()
        self.bind("<Map>", lambda _event: self._apply_v017_identity_title(), add="+")
        self.after_idle(self._apply_v017_identity_title)
        self.after(250, self._apply_v017_identity_title)
        install_work_window_state(
            self,
            job_window_state_key("resultatvisninger", self._v017_display_name),
            max_width_fraction=0.92,
            max_height_fraction=0.82,
        )
        # Make the job/extraction identity visible inside the window as well as
        # in the native title bar.  The inherited row-0 label is informational.
        for widget in self.grid_slaves(row=0, column=0):
            try:
                current = str(widget.cget("text") or "")
            except Exception:
                continue
            if "allerede genererte depotrapporten" in current:
                widget.configure(
                    text=(
                        f"UTTREKK: {self._v017_display_name}\n"
                        "Visningene leser den allerede genererte depotrapporten og kjører ingen ny analyse."
                    )
                )
                break


    def _apply_v017_identity_title(self) -> None:
        try:
            self.title(f"Resultatvisninger – Noark 5 – {self._v017_display_name}")
        except Exception:
            pass

    def _show_archive_part(self, index: int) -> None:
        if getattr(self, "_a1616_start_var", None) is None or getattr(
            self, "_a1616_end_var", None
        ) is None:
            return super(DepotResultCenterDialogA16_16, self)._show_archive_part(index)
        return super()._show_archive_part(index)
