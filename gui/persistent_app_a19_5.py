from __future__ import annotations

import json
import threading

from . import theme
from .depot_result_center_a19_5 import DepotResultCenterDialogA19_5
from .persistent_app_a19_1 import _materialized_correspondence_counts
from .persistent_app_a19_4 import WorkflowApp as A19_4WorkflowApp
from .window_placement import present_child_over_parent, release_parent_work_window


class WorkflowApp(A19_4WorkflowApp):
    """v0.1.6-a19.5: richer archive-part facts and corrected period profiles."""

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
                        return super(A19_4WorkflowApp, self)._open_depot_assessment()
                    finally:
                        self._a192_end_open_indicator()
                try:
                    dialog = DepotResultCenterDialogA19_5(
                        self, model=model, report_path=report_path,
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
