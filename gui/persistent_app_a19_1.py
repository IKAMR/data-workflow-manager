from __future__ import annotations

import json
import threading
from pathlib import Path

from . import theme
from .depot_result_center_a19_1 import DepotResultCenterDialogA19_1
from .persistent_app_a18_9 import WorkflowApp as A18_9WorkflowApp
from .window_placement import present_child_over_parent, release_parent_work_window


def _group_journalpost_types(counter) -> dict[str, int]:
    """Group observed journalpost types for presentation without changing source values."""
    grouped = {"incoming": 0, "outgoing": 0, "note": 0, "other": 0}
    if not isinstance(counter, dict):
        return grouped
    for raw_name, raw_count in counter.items():
        try:
            count = int(raw_count or 0)
        except (TypeError, ValueError):
            continue
        name = str(raw_name or "").strip().casefold()
        compact = " ".join(name.split())
        if compact in {"i", "inngående", "inngående dokument"} or "inngående" in compact:
            grouped["incoming"] += count
        elif compact in {"u", "utgående", "utgående dokument"} or "utgående" in compact:
            grouped["outgoing"] += count
        elif compact in {"n", "x"} or "organinternt" in compact or "notat" in compact:
            grouped["note"] += count
        else:
            grouped["other"] += count
    return grouped


def _materialized_correspondence_counts(model: dict) -> dict[str, int]:
    """Read existing kdrs.c15 evidence only; never run analysis from the GUI."""
    evidence = model.get("evidence") or {}
    xpath_run = str(evidence.get("source_xpath_run") or "").strip()
    if not xpath_run:
        return {}
    path = Path(xpath_run) / "results" / "kdrs_c15.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    values = payload.get("values") or {}
    grouped = _group_journalpost_types(values.get("journalpost_type_counts"))
    return grouped if sum(grouped.values()) else {}


class WorkflowApp(A18_9WorkflowApp):
    """v0.1.6-a19.1: period and correspondence profiles in result views."""

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
                    return super(WorkflowApp, self)._open_depot_assessment()

                dialog = DepotResultCenterDialogA19_1(
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

            try:
                self.after(0, finish)
            except Exception:
                self._depot_assessment_opening = False

        threading.Thread(target=load_report, name="depot-assessment-loader", daemon=True).start()


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
