from __future__ import annotations

from pathlib import Path

from .depot_assessment_dialog import DepotAssessmentDialog


class DirectDepotAssessmentDialog(DepotAssessmentDialog):
    """Open DepotAssessmentDialog directly on one exact report instance."""

    def __init__(
        self,
        master,
        *,
        report_path: str | Path,
        user_identity: dict[str, str] | None = None,
    ) -> None:
        # Do not pass work_operations here. The control overview is RUN-scoped,
        # so we must load the exact report selected in that RUN rather than
        # "latest" from the work area.
        super().__init__(
            master,
            user_identity=user_identity,
            work_operations=None,
        )
        self._load_report(Path(report_path))
        try:
            self.update_idletasks()
            self.lift()
            self.focus_force()
            self.after_idle(self.lift)
        except Exception:
            pass
