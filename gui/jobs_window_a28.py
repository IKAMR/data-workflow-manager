
from __future__ import annotations

from .jobs_window_a27 import A27JobsWindow


class A28JobsWindow(A27JobsWindow):
    """a18: rebuild row callbacks when a JOB-xxx identity is recycled."""

    def __init__(self, *args, **kwargs) -> None:
        self._rendered_job_objects: tuple[int, ...] = ()
        super().__init__(*args, **kwargs)
        self._rendered_job_objects = tuple(id(job) for job in self.batch.jobs())

    def refresh(self) -> None:
        jobs = self.batch.jobs()
        current_objects = tuple(id(job) for job in jobs)
        previous_objects = getattr(self, "_rendered_job_objects", ())

        # New job lists restart at JOB-001.  The inherited row cache keys on
        # job_id, so identical IDs can otherwise keep button callbacks bound
        # to the old Job object.  Object identity is therefore part of the
        # rendering boundary.
        if previous_objects and previous_objects != current_objects:
            self._rendered_job_ids = ()
            self._row_views.clear()

        super().refresh()
        self._rendered_job_objects = current_objects
