from __future__ import annotations

from version import APP_NAME
from .jobs_window_a23 import A23JobsWindow


class A24JobsWindow(A23JobsWindow):
    """a6 fix: safer action order and current application title."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.title(f"Jobber - {APP_NAME}")

    def _row(
        self,
        row,
        job,
        *,
        active=False,
        can_move_up=True,
        can_move_down=True,
    ) -> None:
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

        # Keep movement controls at columns 5-6.
        # Put ordinary/context actions first and destructive action last:
        # Åpne | Mapper | Standard | Nullstill | Slett
        view["open"].grid_configure(column=7, padx=(6, 2))
        view["mapper"].grid_configure(column=8, padx=2)
        view["standard"].grid_configure(column=9, padx=2)
        view["reset"].grid_configure(column=10, padx=2)
        view["delete"].grid_configure(column=11, padx=(10, 0))
