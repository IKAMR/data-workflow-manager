from __future__ import annotations

from pathlib import Path

from . import theme
from .depot_assessment_dialog import latest_depot_report
from .depot_assessment_dialog_a30 import DepotAssessmentDialogA30
from .direct_depot_assessment_dialog_a30 import DirectDepotAssessmentDialogA30
from .noark5_control_overview_dialog_a30 import Noark5ControlOverviewDialogA30
from .persistent_app_a69 import WorkflowApp as A69WorkflowApp


class WorkflowApp(A69WorkflowApp):
    """v0.1.6-a10: target GUI with explicit unavailable-storage handling."""

    def _open_job(self, job) -> None:
        super()._open_job(job)
        if self.job_list_path is not None:
            try:
                self._write_job_list(self.job_list_path)
            except Exception:
                pass

    @staticmethod
    def _path_exists(path) -> bool:
        if not path:
            return False
        try:
            return Path(path).exists()
        except OSError:
            return False

    def _expected_work_operations(self, job) -> Path | None:
        """Return the configured/effective Work path even when storage is offline."""
        if job is None:
            return None

        # Recalculate when possible, but never require the directory to exist.
        try:
            self._apply_effective_work_operations(job)
        except Exception:
            pass

        effective = getattr(job, "_effective_work_operations", None)
        if effective:
            return Path(effective)

        configured = getattr(job, "work_operations", None)
        if configured:
            return Path(configured)

        # work_root is the AIC/package root in the standard storage model.
        work_root = getattr(job, "work_root", None)
        if work_root:
            return Path(work_root) / "repository_operations"

        return None

    def _depot_report_for_job(self, job):
        """Return (report, work_operations, unavailable_storage_path)."""
        if job is None:
            return None, None, None

        expected = self._expected_work_operations(job)

        # Important semantic distinction:
        # a configured Work path that is not reachable means storage is
        # unavailable. Do not misreport that as a missing depot report.
        if expected is not None and not self._path_exists(expected):
            return None, expected, expected

        # Normal direct lookup first.
        if expected is not None:
            report = latest_depot_report(expected)
            if report is not None:
                return report, expected, None

        # Bounded discovery below known, available job/AIC roots. This is only
        # used when storage itself is reachable.
        roots: list[Path] = []

        def add(value) -> None:
            if not value:
                return
            candidate = Path(value)
            if not self._path_exists(candidate):
                return
            key = str(candidate).casefold()
            if all(str(item).casefold() != key for item in roots):
                roots.append(candidate)

        add(expected)
        add(getattr(job, "work_root", None))
        add(getattr(job, "archive_root", None))
        add(getattr(job, "output_root", None))
        add(getattr(job, "source_root", None))
        add(getattr(job, "source_extraction", None))

        patterns = (
            "noark5_reports/depot_validation/*/depot_validation_report.json",
            "dwm/*/noark5_reports/depot_validation/*/depot_validation_report.json",
            "repository_operations/dwm/*/noark5_reports/depot_validation/*/depot_validation_report.json",
            "repository_operations/noark5_reports/depot_validation/*/depot_validation_report.json",
        )

        reports: list[Path] = []
        for root in roots:
            for pattern in patterns:
                try:
                    reports.extend(
                        candidate
                        for candidate in root.glob(pattern)
                        if candidate.is_file()
                    )
                except OSError:
                    pass

        if reports:
            def rank(path: Path):
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    mtime = 0
                return (path.parent.name, mtime)

            report = max(reports, key=rank)

            work_operations = expected
            if work_operations is None:
                parts = list(report.parts)
                try:
                    idx = next(
                        i for i, part in enumerate(parts)
                        if part.casefold() == "noark5_reports"
                    )
                    work_operations = Path(*parts[:idx])
                except Exception:
                    pass

            return report, work_operations, None

        return None, expected, None

    def _open_validation_overview(self) -> None:
        html_path = self._latest_validation_overview_path()
        json_path = self._latest_validation_overview_json_path()

        if html_path is None or json_path is None:
            self.status_bar.set_status(
                "Ingen komplett Noark 5 kontrolloversikt er generert ennå"
            )
            return

        existing = self._control_overview_dialog
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.destroy()
            except Exception:
                pass

        parent = self
        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    parent = self.jobs_window
            except Exception:
                pass

        dialog = Noark5ControlOverviewDialogA30(
            parent,
            overview_json=json_path,
            overview_html=html_path,
            user_identity=self.current_user_identity(),
        )
        self._control_overview_dialog = dialog
        dialog.bind(
            "<Destroy>",
            lambda event, d=dialog: self._control_overview_closed(event, d),
            add="+",
        )

    def _open_depot_assessment(self) -> None:
        self._hide_workflow_tooltips()

        existing = self._depot_assessment_dialog
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.focus()
                    existing.lift()
                    return
            except Exception:
                pass

        job = self.current_job
        report_path, work_operations, unavailable_path = (
            self._depot_report_for_job(job)
        )

        if report_path is None:
            dialog = DepotAssessmentDialogA30(
                self,
                user_identity=self.current_user_identity(),
                work_operations=work_operations,
                storage_unavailable_path=unavailable_path,
            )
        else:
            dialog = DirectDepotAssessmentDialogA30(
                self,
                report_path=report_path,
                user_identity=self.current_user_identity(),
            )

        self._depot_assessment_dialog = dialog
        dialog.bind(
            "<Destroy>",
            lambda event, d=dialog: self._depot_assessment_closed(event, d),
            add="+",
        )


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
