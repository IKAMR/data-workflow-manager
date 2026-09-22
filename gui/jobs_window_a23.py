from __future__ import annotations

from pathlib import Path

from app.work_output_layout import (
    AppWorkSubfolderError,
    effective_work_operations,
)
from noark5_workflow.core.output_subfolder import OutputSubfolderRuleError
from .jobs_window_a22 import A22JobsWindow


class A23JobsWindow(A22JobsWindow):
    """a6: preview Work/app-root/job-rule as one complete path."""

    def __init__(
        self,
        *args,
        get_app_work_subfolder=None,
        **kwargs,
    ) -> None:
        self.get_app_work_subfolder = (
            get_app_work_subfolder or (lambda: "dwm")
        )
        super().__init__(*args, **kwargs)

    def _discover_jobs(self) -> None:
        """Run inherited discovery, then fill missing stable owner identity.

        Discovery may reuse an existing draft or create jobs inside the Jobs
        window, bypassing WorkflowApp._create_job(). Job.set_owner_identity()
        is write-once, so applying the current user here only fills previously
        empty ownership and never rewrites an existing owner.
        """
        before = {job.job_id for job in self.batch.jobs()}
        super()._discover_jobs()

        identity_cb = getattr(self.master, "current_user_identity", None)
        identity = identity_cb() if callable(identity_cb) else None
        if not identity:
            return

        changed = False
        for job in self.batch.jobs():
            if job.owner_identity:
                continue
            job.set_owner_identity(identity)
            if job.owner_identity:
                changed = True

        if not changed:
            return

        persist = getattr(self, "_persist_list_change", None)
        if callable(persist):
            persist()
        self.refresh()

    def _refresh_output_rule_preview(self) -> None:
        rule = self.output_rule_var.get().strip()
        app_subfolder = self.get_app_work_subfolder()
        rows = []

        for position, job in enumerate(self.batch.jobs()[:6], start=1):
            try:
                effective = effective_work_operations(
                    job.work_operations,
                    app_subfolder,
                    rule,
                    job,
                    position,
                )
            except (AppWorkSubfolderError, OutputSubfolderRuleError) as exc:
                self.output_rule_preview.configure(
                    text=f"Ugyldig output-oppsett: {exc}"
                )
                return

            if effective is None:
                shown = "(Work - operations ikke valgt)"
            elif job.work_operations is not None:
                try:
                    shown = str(
                        Path(effective).relative_to(Path(job.work_operations))
                    )
                except ValueError:
                    shown = str(effective)
                shown = shown or "."
            else:
                shown = str(effective)

            rows.append(f"{job.job_id} -> {shown}")

        if len(self.batch.jobs()) > 6:
            rows.append(
                f"... og {len(self.batch.jobs()) - 6} jobb(er) til"
            )

        self.output_rule_preview.configure(
            text=" | ".join(rows) if rows else "(ingen jobber)"
        )
