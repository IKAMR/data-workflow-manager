from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from noark5_workflow.core.job import Job
from noark5_workflow.reporting.depot_metadata import job_display_name, metadata_review_state
from settings import save_config
from version import APP_NAME, VERSION
from . import theme
from .job_batch_action_dialog_v017_a1 import V017A1JobBatchActionDialog
from .jobs_window_a38 import A38JobsWindow
from .work_window_state_v017_a1 import install_work_window_state, job_window_state_key


class V017A1JobsWindow(A38JobsWindow):
    """v0.1.7-a1: selected-job reporting plus depot metadata actions."""

    def __init__(
        self,
        *args,
        on_report_selected: Callable[[tuple[Job, ...]], None] | None = None,
        on_edit_metadata: Callable[[tuple[Job, ...]], None] | None = None,
        **kwargs,
    ) -> None:
        self.on_report_selected = on_report_selected or (lambda _jobs: None)
        self.on_edit_metadata = on_edit_metadata or (lambda _jobs: None)
        super().__init__(*args, **kwargs)
        self.title(f"Jobber - {APP_NAME} v{VERSION}")
        self._install_report_action()
        self._update_bulk_action_state()
        install_work_window_state(self, job_window_state_key("jobbliste"))
        self.protocol("WM_DELETE_WINDOW", self._v017_close_jobs_window)

    def _v017_close_jobs_window(self) -> None:
        """Only an explicit close means Jobbliste should stay closed next startup."""
        try:
            self.settings["job_list_window_open"] = False
            save_config({"job_list_window_open": False})
        except Exception:
            pass
        self.destroy()

    def _open(self, job: Job) -> None:
        """Activate a job without hiding or destroying the persistent Jobbliste."""
        self.on_open_job(job)
        try:
            self.refresh()
            self.deiconify()
            self.lift()
        except Exception:
            pass

    def _install_report_action(self) -> None:
        parent = self.start_all_button.master
        self.report_selected_button = ctk.CTkButton(
            parent,
            text="Rapport valgte",
            command=self._report_selected,
            width=112,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        )
        self.report_selected_button.pack(
            side="left",
            padx=(0, 6),
            before=self.start_all_button,
        )

    def _report_selected(self) -> None:
        selected = self._selected_for_action()
        if selected:
            self.on_report_selected(selected)

    def _update_bulk_action_state(self) -> None:
        super()._update_bulk_action_state()
        if not hasattr(self, "report_selected_button"):
            return
        selected = bool(self._selected_jobs_for_run())
        self.report_selected_button.configure(
            state="disabled" if self._batch_running or not selected else "normal"
        )

    def _open_job_actions(self) -> None:
        if self._batch_running:
            return
        existing = self._job_actions_dialog
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.focus()
                    existing.lift()
                    return
            except Exception:
                self._job_actions_dialog = None

        dialog = V017A1JobBatchActionDialog(
            self,
            self.batch.jobs(),
            on_fill_storage_suggestions=self._run_fill_storage_suggestions,
            on_discover_arkade5_results=self._run_discover_arkade5_results,
            on_run_arkade5=self._run_arkade5,
            on_edit_metadata=self.on_edit_metadata,
        )
        self._job_actions_dialog = dialog
        dialog.bind(
            "<Destroy>",
            lambda event, d=dialog: self._job_actions_closed(event, d),
            add="+",
        )

    def _row(self, row, job, *, active=False, can_move_up=True, can_move_down=True) -> None:
        super()._row(
            row,
            job,
            active=active,
            can_move_up=can_move_up,
            can_move_down=can_move_down,
        )
        view = self._row_views.get(job.job_id)
        if view is None:
            return
        if "name" in view:
            view["name"].configure(text=job_display_name(job))

        # Lock the row action contract regardless of historical inherited layers:
        # Åpne | Mapper | Standard | Nullstill | Slett.
        action_keys = ("open", "mapper", "standard", "reset", "delete")
        widgets = [view.get(key) for key in action_keys]
        columns = [
            int(widget.grid_info().get("column", 0))
            for widget in widgets
            if widget is not None and widget.grid_info()
        ]
        if columns:
            start = min(columns)
            for offset, (key, widget) in enumerate(zip(action_keys, widgets)):
                if widget is None:
                    continue
                widget.grid_configure(
                    column=start + offset,
                    padx=(6, 2) if key == "open" else ((10, 0) if key == "delete" else 2),
                )

        card = view.get("card")
        if card is None:
            return
        state = metadata_review_state(job)
        required = bool(state["required"])
        text = "⚠ Depotmetadata må avklares" if required else "✓ Depotmetadata avklart"
        label = ctk.CTkLabel(
            card,
            text=text,
            anchor="w",
            font=theme.font(theme.SMALL_SIZE, "bold"),
            text_color=theme.DANGER_TEXT if required else theme.TEXT_MUTED,
        )
        label.grid(row=2, column=0, columnspan=2, padx=16, pady=(0, 7), sticky="ew")
        view["metadata_review"] = label

    def _update_row_view(self, row, job, *, active, can_move_up, can_move_down) -> None:
        super()._update_row_view(
            row,
            job,
            active=active,
            can_move_up=can_move_up,
            can_move_down=can_move_down,
        )
        view = self._row_views.get(job.job_id)
        if view is None:
            return
        if "name" in view:
            view["name"].configure(text=job_display_name(job))
        if "metadata_review" not in view:
            return
        state = metadata_review_state(job)
        required = bool(state["required"])
        view["metadata_review"].configure(
            text="⚠ Depotmetadata må avklares" if required else "✓ Depotmetadata avklart",
            text_color=theme.DANGER_TEXT if required else theme.TEXT_MUTED,
        )
