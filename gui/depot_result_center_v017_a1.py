from __future__ import annotations

from tkinter import messagebox
import customtkinter as ctk
from .kdrs_query_results_a4 import KdrsQueryResultsDialog
from noark5_workflow.external_evidence.arkade5 import infer_work_operations_from_depot_report

from .depot_result_center_a16_16 import DepotResultCenterDialogA16_16
from .depot_result_center_a19_5 import DepotResultCenterDialogA19_5
from .work_window_state_v017_a1 import install_work_window_state, job_window_state_key


class V017A1DepotResultCenterDialog(DepotResultCenterDialogA19_5):
    """Result window, including explicit KDRS report-value selections."""

    def __init__(self, master, *, display_name: str = "", **kwargs) -> None:
        self._v017_display_name = str(display_name or "").strip() or "Ukjent uttrekk"
        super().__init__(master, **kwargs)
        try:
            self.geometry("1180x720")
        except Exception:
            pass
        self._install_kdrs_query_tab()
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

    def _install_kdrs_query_tab(self) -> None:
        """Show external result sources without making KDRS the tab identity."""
        tabs = self._root_tabview()
        if tabs is None:
            return
        tabs.add("Eksterne kilder")
        tab = tabs.tab("Eksterne kilder")
        tab.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            tab, text="Eksterne kilder – importert analysegrunnlag",
            anchor="w", font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 9))
        ctk.CTkLabel(
            tab, text="Resultater fra eksterne analyseverktøy vises med kildehenvisninger. "
                      "Ingen ny import eller analyse utføres her.",
            anchor="w", justify="left",
        ).grid(row=1, column=0, sticky="ew", padx=20, pady=8)
        source = ctk.CTkFrame(tab)
        source.grid(row=2, column=0, sticky="ew", padx=20, pady=10)
        source.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            source, text="KDRS Query – Standard, U1 og U2",
            anchor="w", font=ctk.CTkFont(weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        ctk.CTkLabel(
            source, text="Importerte resultater og valg av rapportgrunnlag.",
            anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 12))
        ctk.CTkButton(
            source, text="Vis KDRS Query-resultater",
            width=235, command=self._open_v017_kdrs_query,
        ).grid(row=0, column=1, rowspan=2, sticky="e", padx=12, pady=12)

    def _open_v017_kdrs_query(self) -> None:
        try:
            work = infer_work_operations_from_depot_report(self.report_path)
            KdrsQueryResultsDialog(self, work_operations=work)
        except Exception as exc:
            messagebox.showerror("KDRS Query", str(exc), parent=self)

    def _kdrs_selected_count(self, key: str):
        try:
            from noark5_workflow.external_evidence.arkade5 import infer_work_operations_from_depot_report
            from noark5_workflow.external_evidence.kdrs_query_selection import selected_count
            path = getattr(self, 'report_path', None)
            if path is None:
                return None
            return selected_count(infer_work_operations_from_depot_report(path), key)
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def _summary_value(self, *keys):
        # A source selected by the operator can override the display value;
        # the original DWM master result and report JSON remain unchanged.
        for key in keys:
            selected = self._kdrs_selected_count(key)
            if selected is not None:
                return selected
        return super()._summary_value(*keys)

    def _case_count_whole(self):
        selected = self._kdrs_selected_count('case_count')
        if selected is not None:
            return selected
        return super()._case_count_whole()

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
