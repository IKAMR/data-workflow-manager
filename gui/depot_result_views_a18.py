
from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from noark5_workflow.external_evidence.arkade5 import (
    infer_work_operations_from_depot_report,
)
from noark5_workflow.external_evidence.arkade5_export import (
    write_arkade5_evidence_package,
)
from version import APP_NAME
from . import theme
from .arkade5_analysis_dialog_a15 import choose_report_output_dir
from .depot_result_views_a17 import DepotResultViewsDialogA17


class DepotResultViewsDialogA18(DepotResultViewsDialogA17):
    """v0.1.5-a8: portable Arkade evidence export."""

    def _build_external_evidence_tab(self, tab) -> None:
        super()._build_external_evidence_tab(tab)

        export = ctk.CTkFrame(tab, fg_color="transparent")
        export.grid(row=8, column=0, sticky="ew", padx=8, pady=(0, 8))
        export.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            export,
            text=(
                "Eksporter komplett Arkade 5-evidens som portabel ZIP: original "
                "kilderapport, tapsfri normalisering, mapping, combined coverage "
                "og pinnet Arkade-testkatalog."
            ),
            anchor="w",
            justify="left",
            wraplength=720,
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        has_external = bool(
            ((self.model.get("external_validation") or {}).get("arkade5") or {}).get("imports")
        )
        ctk.CTkButton(
            export,
            text="Eksporter evidenspakke...",
            width=180,
            state="normal" if self.report_path and has_external else "disabled",
            command=self._export_arkade5_evidence_package,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=1)

    def _export_arkade5_evidence_package(self) -> None:
        if self.report_path is None:
            return
        output_dir = choose_report_output_dir(self)
        if output_dir is None:
            return
        try:
            work = infer_work_operations_from_depot_report(self.report_path)
            path = write_arkade5_evidence_package(
                work_operations=work,
                output_dir=output_dir,
                depot_model=self.model,
            )
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return

        messagebox.showinfo(
            APP_NAME,
            f"Arkade 5-evidenspakke eksportert:\n\n{path}",
            parent=self,
        )
