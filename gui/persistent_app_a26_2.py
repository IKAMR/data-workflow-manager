from __future__ import annotations

import json
from pathlib import Path

from . import theme
from .persistent_app_a25_6 import WorkflowApp as A25_6WorkflowApp


class WorkflowApp(A25_6WorkflowApp):
    """v0.1.6-a26.2: only reuse depot reports proven to belong to active extraction."""

    @staticmethod
    def _a262_norm_path(value) -> str:
        if not value:
            return ""
        return str(value).replace("/", "\\").rstrip("\\").casefold()

    def _a262_report_matches_job(self, report: Path, job) -> bool:
        """Require an artifact manifest whose source_extraction matches the job.

        Shared Work - operations roots are valid, but a report from another
        extraction must never become the active job's result merely because it
        happens to be the newest report below that shared tree.
        """
        manifest = report.parent / "artifact_manifest.json"
        if not manifest.is_file():
            return False
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if not isinstance(data, dict):
            return False

        operation_id = str(data.get("operation_id", "") or "").strip()
        if operation_id and operation_id != "build_noark5_depot_report":
            return False

        expected_source = (
            getattr(job, "source_extraction", None)
            or getattr(job, "active_extraction_root", None)
        )
        actual_source = str(data.get("source_extraction", "") or "").strip()
        if not expected_source or not actual_source:
            return False
        return self._a262_norm_path(actual_source) == self._a262_norm_path(expected_source)

    def _depot_report_for_job(self, job):
        """Return only a depot report with explicit source identity for this job."""
        if job is None:
            return None, None, None

        expected = self._expected_work_operations(job)
        if expected is not None and not self._path_exists(expected):
            return None, expected, expected

        roots: list[Path] = []

        def add(value) -> None:
            if not value:
                return
            candidate = Path(value)
            if not self._path_exists(candidate):
                return
            key = self._a262_norm_path(candidate)
            if all(self._a262_norm_path(item) != key for item in roots):
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
        seen: set[str] = set()
        for root in roots:
            for pattern in patterns:
                try:
                    candidates = root.glob(pattern)
                    for candidate in candidates:
                        if not candidate.is_file():
                            continue
                        key = self._a262_norm_path(candidate)
                        if key in seen:
                            continue
                        seen.add(key)
                        if self._a262_report_matches_job(candidate, job):
                            reports.append(candidate)
                except OSError:
                    pass

        if not reports:
            return None, expected, None

        def rank(path: Path):
            manifest = path.parent / "artifact_manifest.json"
            created_at = ""
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                created_at = str(data.get("created_at", "") or "")
            except (OSError, json.JSONDecodeError):
                pass
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0
            return (created_at, path.parent.name, mtime)

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


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
