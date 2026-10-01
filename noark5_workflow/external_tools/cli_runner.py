from __future__ import annotations

import hashlib
import json
import locale
import os
import queue
import shlex
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True)
class ExternalCliRequest:
    """Description of one external CLI invocation.

    The command is always executed as an argv sequence with ``shell=False``.
    This keeps quoting rules out of the runner and makes adapters responsible
    for providing one argument per item.
    """

    executable: str | Path
    args: Sequence[str | Path] = field(default_factory=tuple)
    cwd: str | Path | None = None
    env: Mapping[str, str] | None = None
    timeout_seconds: float | None = None
    encoding: str | None = None
    stdout_path: str | Path | None = None
    stderr_path: str | Path | None = None
    manifest_path: str | Path | None = None
    tool_id: str = ""
    operation_id: str = ""
    job_id: str = ""
    run_id: str = ""
    metadata: Mapping[str, Any] | None = None

    def argv(self) -> tuple[str, ...]:
        return (str(self.executable), *(str(value) for value in self.args))


@dataclass(frozen=True)
class ExternalCliRunResult:
    ok: bool
    argv: tuple[str, ...]
    started_at: str
    finished_at: str
    duration_seconds: float
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    launch_error: str = ""
    cwd: str | None = None
    encoding: str = ""
    stdout_path: str | None = None
    stderr_path: str | None = None
    manifest_path: str | None = None
    tool_id: str = ""
    operation_id: str = ""
    job_id: str = ""
    run_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def command_display(self) -> str:
        """Human-readable command for diagnostics only."""
        return shlex.join(self.argv)

    def manifest(self) -> dict[str, Any]:
        """Return a structured, non-secret execution manifest."""
        return {
            "schema_version": 1,
            "runner": "dwm.external_cli",
            "tool_id": self.tool_id,
            "operation_id": self.operation_id,
            "job_id": self.job_id,
            "run_id": self.run_id,
            "ok": self.ok,
            "argv": list(self.argv),
            "cwd": self.cwd,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "launch_error": self.launch_error or None,
            "encoding": self.encoding,
            "stdout": _stream_manifest(self.stdout, self.stdout_path),
            "stderr": _stream_manifest(self.stderr, self.stderr_path),
            "metadata": dict(self.metadata),
        }


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def _effective_encoding(requested: str | None) -> str:
    return requested or locale.getpreferredencoding(False) or "utf-8"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stream_manifest(value: str, path: str | None) -> dict[str, Any]:
    return {
        "path": path,
        "characters": len(value),
        "sha256_utf8": _sha256_text(value),
    }


def _write_text(path_value: str | Path | None, value: str) -> str | None:
    if path_value is None:
        return None
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="")
    return str(path)


def _write_manifest(path_value: str | Path | None, payload: dict[str, Any]) -> str | None:
    if path_value is None:
        return None
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)
    return str(path)


def _reader_thread(stream, stream_name: str, event_queue: queue.Queue) -> None:
    """Read one text pipe line-by-line without blocking the other pipe."""
    try:
        for line in iter(stream.readline, ""):
            event_queue.put((stream_name, line))
    finally:
        try:
            stream.close()
        except Exception:
            pass
        event_queue.put((stream_name, None))


def run_external_cli(
    request: ExternalCliRequest,
    *,
    on_output: Callable[[str, str], None] | None = None,
) -> ExternalCliRunResult:
    """Run one external command and capture reproducible execution evidence.

    ``on_output`` receives ``("stdout"|"stderr", line)`` while the child
    process is running. The callback is observational only: complete stdout
    and stderr are still captured and written to their normal evidence files.
    """

    argv = request.argv()
    cwd = str(Path(request.cwd)) if request.cwd is not None else None
    encoding = _effective_encoding(request.encoding)

    env = os.environ.copy()
    if request.env:
        env.update({str(key): str(value) for key, value in request.env.items()})

    started_at = _now_iso()
    started_monotonic = time.monotonic()
    exit_code: int | None = None
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    timed_out = False
    launch_error = ""

    try:
        process = subprocess.Popen(
            list(argv),
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=encoding,
            errors="replace",
            shell=False,
            bufsize=1,
        )

        events: queue.Queue = queue.Queue()
        readers = (
            threading.Thread(target=_reader_thread, args=(process.stdout, "stdout", events), daemon=True),
            threading.Thread(target=_reader_thread, args=(process.stderr, "stderr", events), daemon=True),
        )
        for reader in readers:
            reader.start()

        closed_streams: set[str] = set()
        while len(closed_streams) < 2 or process.poll() is None:
            if (
                request.timeout_seconds is not None
                and time.monotonic() - started_monotonic >= request.timeout_seconds
                and process.poll() is None
            ):
                timed_out = True
                process.kill()

            try:
                stream_name, line = events.get(timeout=0.1)
            except queue.Empty:
                continue

            if line is None:
                closed_streams.add(stream_name)
                continue

            if stream_name == "stdout":
                stdout_parts.append(line)
            else:
                stderr_parts.append(line)

            if on_output is not None:
                try:
                    on_output(stream_name, line)
                except Exception:
                    # A GUI/status callback must never make the external process fail.
                    pass

        process_return_code = int(process.wait())
        exit_code = None if timed_out else process_return_code
        for reader in readers:
            reader.join(timeout=1.0)

        # Drain any lines queued between process termination and reader exit.
        while True:
            try:
                stream_name, line = events.get_nowait()
            except queue.Empty:
                break
            if line is None:
                continue
            if stream_name == "stdout":
                stdout_parts.append(line)
            else:
                stderr_parts.append(line)
            if on_output is not None:
                try:
                    on_output(stream_name, line)
                except Exception:
                    pass

        if timed_out:
            timeout_line = f"DWM external CLI timeout after {request.timeout_seconds} seconds.\n"
            stderr_parts.append(timeout_line)
            if on_output is not None:
                try:
                    on_output("stderr", timeout_line)
                except Exception:
                    pass
    except OSError as exc:
        launch_error = f"{type(exc).__name__}: {argv[0]}: {exc}"
        error_line = launch_error + "\n"
        stderr_parts.append(error_line)
        if on_output is not None:
            try:
                on_output("stderr", error_line)
            except Exception:
                pass

    stdout = "".join(stdout_parts)
    stderr = "".join(stderr_parts)
    finished_at = _now_iso()
    duration_seconds = max(0.0, time.monotonic() - started_monotonic)

    stdout_path = _write_text(request.stdout_path, stdout)
    stderr_path = _write_text(request.stderr_path, stderr)

    result = ExternalCliRunResult(
        ok=(not timed_out and not launch_error and exit_code == 0),
        argv=argv,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=duration_seconds,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        launch_error=launch_error,
        cwd=cwd,
        encoding=encoding,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        manifest_path=None,
        tool_id=request.tool_id,
        operation_id=request.operation_id,
        job_id=request.job_id,
        run_id=request.run_id,
        metadata=dict(request.metadata or {}),
    )

    manifest_path = _write_manifest(request.manifest_path, result.manifest())
    if manifest_path is None:
        return result

    values = asdict(result)
    values["manifest_path"] = manifest_path
    return ExternalCliRunResult(**values)
