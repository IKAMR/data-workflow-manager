from __future__ import annotations

import re
from pathlib import Path
from tkinter import messagebox

from app.storage_layouts import materialize_storage_roles, suggested_job_name
from version import APP_NAME
from . import theme
from .persistent_app_a27 import WorkflowApp as A27WorkflowApp


_AUTO_NOARK_NAME_RE = re.compile(r"^\d{4}_.+")


class WorkflowApp(A27WorkflowApp):
    """a16.2.3: protect job/source identity and repair stale generated job names.

    Source/storage roles are authoritative for the actual package. A generated
    Noark 5 job name is presentation metadata and may be repaired when an older
    buggy runtime left it pointing at a different package.
    """

    def _layout_id(self) -> str:
        return str(
            self.settings.get("storage_layout_profile", "ikamr_standard")
            or "none"
        )

    def _package_root_for_extraction(self, extraction: Path | None) -> Path | None:
        if extraction is None:
            return None
        try:
            roles = materialize_storage_roles(
                Path(extraction),
                layout_id=self._layout_id(),
            )
        except Exception:
            return None
        root = roles.get("source_root")
        return Path(root) if root is not None else None

    def _job_package_root(self, job) -> Path | None:
        if job is None:
            return None
        if job.source_root is not None:
            return Path(job.source_root)
        return self._package_root_for_extraction(job.active_extraction_root)

    def _job_matches_source(self, job, path: Path) -> bool:
        current_extraction = job.active_extraction_root
        if current_extraction is not None and Path(current_extraction) == path:
            return True

        selected_root = self._package_root_for_extraction(path)
        job_root = self._job_package_root(job)
        return (
            selected_root is not None
            and job_root is not None
            and selected_root == job_root
        )

    def _existing_job_for_source(self, path: Path):
        for job in self.jobs.jobs():
            if self._job_matches_source(job, path):
                return job
        return None

    def _restore_source_panel_from_job(self, job) -> None:
        extraction = job.active_extraction_root if job is not None else None
        if extraction is not None:
            self.source_panel.set_path(str(extraction))
        else:
            self.source_panel.path_var.set("")
            self.source_panel.detect()

    @staticmethod
    def _looks_like_generated_noark_name(name: str, job_id: str) -> bool:
        value = str(name or "").strip()
        if not value or value == job_id or value.casefold() == "content":
            return True
        return bool(_AUTO_NOARK_NAME_RE.fullmatch(value))

    def _expected_noark_job_name(self, job) -> str | None:
        extraction = job.source_extraction or job.active_extraction_root
        if extraction is None:
            return None
        try:
            value = suggested_job_name(
                Path(extraction),
                layout_id=self._layout_id(),
            )
        except Exception:
            return None
        value = str(value or "").strip()
        return value or None

    def _repair_generated_job_names(self) -> list[tuple[str, str, str]]:
        """Repair only names that look auto-generated.

        User-defined descriptive names are deliberately preserved. This repairs
        the a16.2.1 corruption pattern where paths were moved to another package
        while the old generated package name remained.
        """
        repaired: list[tuple[str, str, str]] = []
        for job in self.jobs.jobs():
            if job.profile_id != "noark5":
                continue
            expected = self._expected_noark_job_name(job)
            if expected is None or job.name == expected:
                continue
            if not self._looks_like_generated_noark_name(job.name, job.job_id):
                continue

            old_name = job.name
            job.name = expected
            repaired.append((job.job_id, old_name, expected))
            try:
                self._job_log(
                    job,
                    f"JOBBNAVN REPARERT: {old_name} -> {expected} "
                    "(utledet fra Source; kjørestatus uendret)",
                )
            except Exception:
                pass
        return repaired

    def _load_job_list_file(self, path: Path, *, show_error: bool) -> bool:
        loaded = super()._load_job_list_file(path, show_error=show_error)
        if not loaded:
            return False

        repaired = self._repair_generated_job_names()
        if repaired:
            self._refresh_active_job_label()
            jobs_window = getattr(self, "jobs_window", None)
            if jobs_window is not None:
                try:
                    if jobs_window.winfo_exists():
                        jobs_window.refresh()
                except Exception:
                    pass

            self.status_bar.set_status(
                f"{len(repaired)} generert jobbnavn ble reparert fra Source. "
                "Bruk Lagre for å skrive rettingen til jobblisten."
            )
        return True

    def _ensure_job_for_current_source(self):
        root = self.source_panel.path_var.get().strip()
        if not root:
            return self.current_job

        path = Path(root)
        current = self.current_job

        if current is None:
            return super()._ensure_job_for_current_source()

        if current.active_extraction_root is None:
            current.source_extraction = path
            roles = materialize_storage_roles(path, layout_id=self._layout_id())
            if current.source_root is None and roles.get("source_root") is not None:
                current.source_root = Path(roles["source_root"])
            if (
                current.profile_id == "noark5"
                and self._looks_like_generated_noark_name(current.name, current.job_id)
            ):
                expected = self._expected_noark_job_name(current)
                if expected:
                    current.name = expected
            self._refresh_active_job_label()
            return current

        if self._job_matches_source(current, path):
            current.source_extraction = path
            if (
                current.profile_id == "noark5"
                and self._looks_like_generated_noark_name(current.name, current.job_id)
            ):
                expected = self._expected_noark_job_name(current)
                if expected:
                    current.name = expected
            self._refresh_active_job_label()
            return current

        existing = self._existing_job_for_source(path)
        if existing is not None and existing is not current:
            self._open_job(existing)
            self.status_bar.set_status(
                f"{existing.job_id} aktivert fordi valgt Source tilhører denne jobben"
            )
            return existing

        self._restore_source_panel_from_job(current)
        self.status_bar.set_status(
            f"{current.job_id}: Source ble ikke endret - valgt uttrekk tilhører en annen pakke"
        )
        return None

    def _source_browse_complete(self, path: Path) -> None:
        job = self._ensure_job_for_current_source()
        if job is None:
            current = self.current_job
            current_text = (
                f"{current.job_id} – {current.name}"
                if current is not None
                else "ingen aktiv jobb"
            )
            messagebox.showwarning(
                APP_NAME,
                "Valgt Source tilhører et annet uttrekk enn aktiv jobb.\n\n"
                f"Aktiv jobb: {current_text}\n"
                f"Valgt Source: {path}\n\n"
                "Eksisterende jobb blir ikke endret.\n"
                "Bruk «+ Ny jobb» for et nytt uttrekk, eller åpne jobben som "
                "allerede tilhører uttrekket.",
            )
            return

        self._show_storage_roles(job)


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
