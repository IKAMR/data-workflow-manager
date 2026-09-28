from __future__ import annotations

import json
import threading

from . import theme
from .depot_result_center_a19_2 import DepotResultCenterDialogA19_2
from .persistent_app_a19_1 import (
    WorkflowApp as A19_1WorkflowApp,
    _materialized_correspondence_counts,
)
from .window_placement import present_child_over_parent, release_parent_work_window


class WorkflowApp(A19_1WorkflowApp):
    """v0.1.6-a19.2: polished overview plus visible async-open feedback."""

    def _a192_begin_open_indicator(self) -> None:
        self._a192_open_indicator_active = True
        self._a192_open_indicator_step = 0
        try:
            self._a192_previous_status = getattr(self.status_bar, "_status_text", "Klar")
        except Exception:
            self._a192_previous_status = "Klar"
        try:
            self.configure(cursor="watch")
        except Exception:
            pass
        try:
            self.status_bar.status_label.configure(text_color=theme.BLUE)
        except Exception:
            pass
        self._a192_tick_open_indicator()

    def _a192_tick_open_indicator(self) -> None:
        if not getattr(self, "_a192_open_indicator_active", False):
            return
        step = int(getattr(self, "_a192_open_indicator_step", 0))
        dots = "." * ((step % 3) + 1)
        try:
            self.status_bar.set_status(f"Åpner Resultatvisninger{dots}")
        except Exception:
            pass
        self._a192_open_indicator_step = step + 1
        try:
            self.after(350, self._a192_tick_open_indicator)
        except Exception:
            pass

    def _a192_end_open_indicator(self) -> None:
        self._a192_open_indicator_active = False
        try:
            self.configure(cursor="")
        except Exception:
            pass
        try:
            self.status_bar.status_label.configure(text_color=theme.TEXT)
        except Exception:
            pass
        previous = getattr(self, "_a192_previous_status", "Klar") or "Klar"
        try:
            self.status_bar.set_status(previous)
        except Exception:
            pass

    def _open_depot_assessment(self) -> None:
        self._hide_workflow_tooltips()
        existing = getattr(self, "_depot_assessment_dialog", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    release_parent_work_window(self)
                    existing.deiconify()
                    present_child_over_parent(existing, self)
                    return
            except Exception:
                self._depot_assessment_dialog = None

        if getattr(self, "_depot_assessment_opening", False):
            return
        self._depot_assessment_opening = True
        self._a192_begin_open_indicator()
        job = self.current_job

        def load_report() -> None:
            try:
                report_path, _work_operations, _unavailable_path = self._depot_report_for_job(job)
                model = None
                if report_path is not None:
                    try:
                        model = json.loads(report_path.read_text(encoding="utf-8"))
                        model = dict(model)
                        model["_a19_correspondence_counts"] = _materialized_correspondence_counts(model)
                    except Exception:
                        model = None
            except Exception:
                report_path = None
                model = None

            def finish() -> None:
                self._depot_assessment_opening = False
                if report_path is None or model is None:
                    try:
                        # Skip the a19.1 presentation layer on fallback so the
                        # established older report-opening behaviour remains authoritative.
                        return super(A19_1WorkflowApp, self)._open_depot_assessment()
                    finally:
                        self._a192_end_open_indicator()

                try:
                    dialog = DepotResultCenterDialogA19_2(
                        self,
                        model=model,
                        report_path=report_path,
                        user_identity=self.current_user_identity(),
                    )
                    self._depot_assessment_dialog = dialog
                    dialog.bind(
                        "<Destroy>",
                        lambda event, d=dialog: self._depot_assessment_closed(event, d),
                        add="+",
                    )
                    release_parent_work_window(self)
                    present_child_over_parent(dialog, self)
                finally:
                    self._a192_end_open_indicator()

            try:
                self.after(0, finish)
            except Exception:
                self._depot_assessment_opening = False
                try:
                    self.after(0, self._a192_end_open_indicator)
                except Exception:
                    pass

        threading.Thread(target=load_report, name="depot-assessment-loader", daemon=True).start()


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
