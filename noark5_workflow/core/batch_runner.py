from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Iterable

from noark5_workflow.core.job import Job, JobBatch, JobStatus
from noark5_workflow.core.job_runner import JobRunner


_TERMINAL_STATUSES = {JobStatus.OK, JobStatus.FAILED, JobStatus.SKIPPED}


@dataclass(frozen=True)
class BatchRunOutcome:
    total: int
    finished: int
    waiting: int
    failed: int
    skipped: int
    cancelled: bool = False

    @property
    def ok(self) -> bool:
        return self.failed == 0


class BatchRunner:
    """GUI-independent execution of a collection of Jobs.

    ``run`` preserves the established sequential contract.

    ``run_parallel`` is the new a4 core capability for independent jobs. Each
    worker gets an isolated JobRunner/registry copy so mutable operation
    configuration cannot leak between jobs. GUI enablement is deliberately a
    separate step; callbacks passed to run_parallel may be called from worker
    threads.
    """

    def __init__(
        self,
        job_runner: JobRunner,
        *,
        parallel_runner_factory: Callable[[], JobRunner] | None = None,
    ) -> None:
        self.job_runner = job_runner
        self.parallel_runner_factory = parallel_runner_factory

    def _new_parallel_runner(self) -> JobRunner:
        if self.parallel_runner_factory is not None:
            return self.parallel_runner_factory()

        # Registry operation instances are mutable during configuration.
        # Deep-copying the registry gives each worker its own operation
        # instances while preserving the concrete JobRunner subclass (for
        # example RuleAwareJobRunner in the desktop runtime).
        runner_cls = type(self.job_runner)
        registry = copy.deepcopy(self.job_runner.registry)
        return runner_cls(
            registry,
            self.job_runner.executor,
            self.job_runner.settings,
            source_factory=self.job_runner.source_factory,
        )

    @staticmethod
    def _outcome(ordered: list[Job], *, cancelled: bool) -> BatchRunOutcome:
        counts = {
            status: sum(job.status == status for job in ordered)
            for status in JobStatus
        }
        return BatchRunOutcome(
            total=len(ordered),
            finished=counts[JobStatus.OK],
            waiting=counts[JobStatus.WAITING],
            failed=counts[JobStatus.FAILED],
            skipped=counts[JobStatus.SKIPPED],
            cancelled=cancelled,
        )

    def run(
        self,
        jobs: JobBatch | Iterable[Job],
        *,
        cancelled_cb: Callable[[], bool] | None = None,
        progress_cb: Callable[[Job, float, str], None] | None = None,
        log_cb: Callable[[Job, str], None] | None = None,
        state_cb: Callable[[Job], None] | None = None,
        preparing_cb: Callable[[Job, int, int], None] | None = None,
        registered_cb: Callable[[Job, int, int, bool], None] | None = None,
        finished_cb: Callable[[Job, int, int], None] | None = None,
    ) -> BatchRunOutcome:
        ordered = jobs.jobs() if isinstance(jobs, JobBatch) else list(jobs)
        total = len(ordered)
        cancelled_seen = False

        def cancelled() -> bool:
            return bool(cancelled_cb and cancelled_cb())

        for position, job in enumerate(ordered, start=1):
            if preparing_cb:
                preparing_cb(job, position, total)

            if cancelled():
                cancelled_seen = True
                if job.status == JobStatus.READY:
                    job.status = JobStatus.SKIPPED
                    job.message = "Ikke startet - batch avbrutt"
                    if state_cb:
                        state_cb(job)
                if registered_cb:
                    registered_cb(job, position, total, False)
                if finished_cb:
                    finished_cb(job, position, total)
                continue

            if job.status in _TERMINAL_STATUSES:
                job.reset_execution("Klar for ny batchkjøring")
                if state_cb:
                    state_cb(job)

            if registered_cb:
                registered_cb(job, position, total, True)

            self.job_runner.run(
                job,
                progress_cb=(
                    (lambda value, message, j=job: progress_cb(j, value, message))
                    if progress_cb else None
                ),
                log_cb=((lambda message, j=job: log_cb(j, message)) if log_cb else None),
                cancelled_cb=cancelled_cb,
                state_cb=state_cb,
            )

            if finished_cb:
                finished_cb(job, position, total)

            if cancelled():
                cancelled_seen = True

        return self._outcome(ordered, cancelled=cancelled_seen)

    def run_parallel(
        self,
        jobs: JobBatch | Iterable[Job],
        *,
        max_workers: int,
        cancelled_cb: Callable[[], bool] | None = None,
        progress_cb: Callable[[Job, float, str], None] | None = None,
        log_cb: Callable[[Job, str], None] | None = None,
        state_cb: Callable[[Job], None] | None = None,
        preparing_cb: Callable[[Job, int, int], None] | None = None,
        registered_cb: Callable[[Job, int, int, bool], None] | None = None,
        finished_cb: Callable[[Job, int, int], None] | None = None,
    ) -> BatchRunOutcome:
        """Run independent jobs concurrently with isolated operation instances.

        This method does not change workflow order *inside* a job. Each job
        remains sequential and checkpoint-aware.

        The caller must still ensure that jobs have non-conflicting source/
        output/work resources. Existing GUI preflight already performs output
        collision checks; GUI activation of parallel batch is intentionally
        deferred until callback/UI marshalling is completed.
        """
        workers = max(1, int(max_workers))
        if workers == 1:
            return self.run(
                jobs,
                cancelled_cb=cancelled_cb,
                progress_cb=progress_cb,
                log_cb=log_cb,
                state_cb=state_cb,
                preparing_cb=preparing_cb,
                registered_cb=registered_cb,
                finished_cb=finished_cb,
            )

        ordered = jobs.jobs() if isinstance(jobs, JobBatch) else list(jobs)
        total = len(ordered)
        if total == 0:
            return self._outcome(ordered, cancelled=False)

        cancelled_seen = False
        positions = {job.job_id: pos for pos, job in enumerate(ordered, start=1)}

        def cancelled() -> bool:
            return bool(cancelled_cb and cancelled_cb())

        def execute(job: Job):
            runner = self._new_parallel_runner()
            return runner.run(
                job,
                progress_cb=(
                    (lambda value, message, j=job: progress_cb(j, value, message))
                    if progress_cb else None
                ),
                log_cb=((lambda message, j=job: log_cb(j, message)) if log_cb else None),
                cancelled_cb=cancelled_cb,
                state_cb=state_cb,
            )

        futures = {}
        with ThreadPoolExecutor(
            max_workers=min(workers, total),
            thread_name_prefix="dwm-job",
        ) as pool:
            for position, job in enumerate(ordered, start=1):
                if preparing_cb:
                    preparing_cb(job, position, total)

                if cancelled():
                    cancelled_seen = True
                    if job.status == JobStatus.READY:
                        job.status = JobStatus.SKIPPED
                        job.message = "Ikke startet - batch avbrutt"
                        if state_cb:
                            state_cb(job)
                    if registered_cb:
                        registered_cb(job, position, total, False)
                    if finished_cb:
                        finished_cb(job, position, total)
                    continue

                if job.status in _TERMINAL_STATUSES:
                    job.reset_execution("Klar for ny batchkjøring")
                    if state_cb:
                        state_cb(job)

                if registered_cb:
                    registered_cb(job, position, total, True)

                futures[pool.submit(execute, job)] = job

            for future in as_completed(futures):
                job = futures[future]
                # JobRunner normally converts execution exceptions into FAILED.
                # Preserve a hard guard here so one worker cannot tear down the
                # entire batch coordinator.
                try:
                    future.result()
                except Exception as exc:
                    job.status = JobStatus.FAILED
                    job.message = f"Parallell jobb feilet: {exc}"
                    if state_cb:
                        state_cb(job)
                    if log_cb:
                        log_cb(job, job.message)

                if finished_cb:
                    finished_cb(job, positions[job.job_id], total)

                if cancelled():
                    cancelled_seen = True

        return self._outcome(ordered, cancelled=cancelled_seen)
