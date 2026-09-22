from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.workspace import run_log_dir
from noark5_workflow.core.events import WorkflowEvent
from version import APP_NAME


def _iso_text(value: str) -> str:
    return str(value or "")


@dataclass
class TextJobRecord:
    job_id: str
    name: str
    source: str
    source_root: str
    source_extraction: str
    work_root: str
    work_operations: str
    archive_root: str
    output: str
    started: str
    owner_user_id: str = ""
    owner_username: str = ""
    owner_name: str = ""
    owner_email: str = ""
    finished: str = ""
    status: str = ""
    message: str = ""


class TextRunLogSink:
    """Human-readable run-log sink for neutral WorkflowEvent instances."""

    sink_id = "text_run_log"

    def __init__(
        self,
        settings: dict,
        *,
        run_type: str,
        app_version: str,
        job_list_path: Path | None = None,
        planned_jobs: int | None = None,
        definition=None,
    ) -> None:
        self.settings = dict(settings)
        self.definition = definition
        self.mirror_to_work_operations = bool(
            self.settings.get("copy_run_log_to_work_operations", True)
        )
        self.run_type = str(run_type).lower()
        self.app_version = str(app_version)
        self.job_list_path = Path(job_list_path) if job_list_path else None
        self.planned_jobs = planned_jobs

        now = datetime.now().astimezone()
        self.started = now.isoformat(timespec="seconds")
        self.finished = ""
        self.run_status = "STARTET"
        self.error_message = ""
        self.phase = "Oppretter kjøring"
        configured_run_id = str(self.settings.get("_current_run_id", "") or "").strip()
        self.run_id = configured_run_id or f"RUN-{now.strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"
        suffix = "BATCH" if self.run_type == "batch" else "SINGLE"
        filename = f"{now.strftime('%Y-%m-%d_%H%M%S')}_{suffix}_{self.run_id[-8:]}.log"
        self.path = run_log_dir(settings) / filename

        user = self.settings.get("_current_user_identity", {})
        user = user if isinstance(user, dict) else {}
        self.run_user_id = str(user.get("user_id", "") or "")
        self.run_username = str(user.get("username", "") or "")
        self.run_user_name = str(user.get("name", "") or "")
        self.run_user_email = str(user.get("email", "") or "")

        self.records: list[TextJobRecord] = []
        self._current: dict[str, TextJobRecord] = {}
        self._write()

    def handle(self, event: WorkflowEvent, **runtime) -> None:
        if self.definition is not None and not self.definition.accepts(event.kind):
            return
        kind = event.kind

        if kind == "run.phase":
            self.phase = str(event.data.get("phase", "") or "")
        elif kind == "run.failed":
            self.run_status = "FEIL"
            self.error_message = event.message
            self.finished = event.timestamp
        elif kind == "run.finished":
            if self.run_status != "FEIL":
                self.run_status = str(event.data.get("status", "FERDIG") or "FERDIG")
            self.finished = event.timestamp
        elif kind == "job.started":
            job_id = event.job_id
            if job_id not in self._current:
                data = event.data
                owner = data.get("owner", {})
                owner = owner if isinstance(owner, dict) else {}
                record = TextJobRecord(
                    job_id=job_id,
                    name=str(data.get("name", "") or ""),
                    source=str(data.get("source", "") or ""),
                    source_root=str(data.get("source_root", "") or ""),
                    source_extraction=str(data.get("source_extraction", "") or ""),
                    work_root=str(data.get("work_root", "") or ""),
                    work_operations=str(data.get("work_operations", "") or ""),
                    archive_root=str(data.get("archive_root", "") or ""),
                    output=str(data.get("output", "") or ""),
                    started=event.timestamp,
                    owner_user_id=str(owner.get("user_id", "") or ""),
                    owner_username=str(owner.get("username", "") or ""),
                    owner_name=str(owner.get("name", "") or ""),
                    owner_email=str(owner.get("email", "") or ""),
                )
                self.records.append(record)
                self._current[job_id] = record
        elif kind == "job.finished":
            record = self._current.get(event.job_id)
            if record is not None:
                data = event.data
                record.finished = event.timestamp
                record.status = str(data.get("status", "") or "")
                record.message = event.message
                record.work_root = str(data.get("work_root", record.work_root) or "")
                record.work_operations = str(data.get("work_operations", record.work_operations) or "")
                record.archive_root = str(data.get("archive_root", record.archive_root) or "")
                record.output = str(data.get("output", record.output) or "")

        self._write()

    def close(self, **runtime) -> None:
        return None

    def _render(self) -> str:
        lines = [
            f"{APP_NAME} - overordnet kjørelogg",
            "",
            f"Run ID: {self.run_id}",
            f"Kjøretype: {self.run_type}",
            f"Status: {self.run_status}",
            f"Fase: {self.phase}",
            f"App-versjon: {self.app_version}",
            f"Start: {_iso_text(self.started)}",
            f"Slutt: {_iso_text(self.finished)}",
            f"Jobbliste: {self.job_list_path or ''}",
            f"Planlagte jobber: {self.planned_jobs if self.planned_jobs is not None else ''}",
            f"Utførende bruker - brukernavn: {self.run_username}",
            f"Utførende bruker - user_id: {self.run_user_id}",
            f"Utførende bruker - navn: {self.run_user_name}",
            f"Utførende bruker - e-post: {self.run_user_email}",
        ]
        if self.error_message:
            lines.append(f"Feil: {self.error_message}")
        lines.append("")

        for index, record in enumerate(self.records, start=1):
            lines.extend([
                f"JOBB {index}",
                f"Jobb-ID: {record.job_id}",
                f"Navn: {record.name}",
                f"Jobbeier - brukernavn: {record.owner_username}",
                f"Jobbeier - user_id: {record.owner_user_id}",
                f"Jobbeier - navn: {record.owner_name}",
                f"Jobbeier - e-post: {record.owner_email}",
                f"Source: {record.source}",
                f"Source - hovedmappe: {record.source_root}",
                f"Source - uttrekksmappe: {record.source_extraction or record.source}",
                f"Arbeid - hovedmappe: {record.work_root}",
                f"Arbeid - operasjoner: {record.work_operations}",
                f"Arkiv - hovedmappe: {record.archive_root}",
                f"Output: {record.output}",
                f"Start: {record.started}",
                f"Slutt: {record.finished}",
                f"Status: {record.status}",
                f"Resultat: {record.message}",
                "",
            ])

        if self.finished:
            completed = sum(1 for r in self.records if r.finished)
            ok = sum(1 for r in self.records if r.status.lower() in {"ok", "completed", "success", "ferdig"})
            failed = sum(1 for r in self.records if "fail" in r.status.lower() or "feil" in r.status.lower())
            waiting = sum(1 for r in self.records if "wait" in r.status.lower() or "venter" in r.status.lower())
            skipped = sum(1 for r in self.records if "skip" in r.status.lower() or "hopp" in r.status.lower())
            lines.extend([
                "SAMMENDRAG",
                f"Planlagte jobber: {self.planned_jobs if self.planned_jobs is not None else len(self.records)}",
                f"Startede jobber: {len(self.records)}",
                f"Ferdigbehandlede jobber: {completed}",
                f"OK: {ok}",
                f"Feil: {failed}",
                f"Venter: {waiting}",
                f"Hoppet over: {skipped}",
                "",
            ])
        return "\n".join(lines)

    def _mirror(self, text: str) -> None:
        if not self.mirror_to_work_operations:
            return
        targets = {
            Path(record.work_operations)
            for record in self.records
            if record.work_operations
        }
        for work_operations in targets:
            try:
                mirror_dir = work_operations / "wf" / "logs"
                mirror_dir.mkdir(parents=True, exist_ok=True)
                (mirror_dir / self.path.name).write_text(text, encoding="utf-8")
            except OSError:
                continue

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = self._render()
        self.path.write_text(text, encoding="utf-8")
        self._mirror(text)
