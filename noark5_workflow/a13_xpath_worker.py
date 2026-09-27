from __future__ import annotations

"""Headless subprocess worker for the a13 Noark 5 XPath catalogue."""

import argparse
import json
import os
from pathlib import Path
import sys
import traceback

EVENT_PREFIX = "DWM_A13_EVENT\t"


def _force_utf8_stdio() -> None:
    """Use one encoding across worker pipes, logs and the Windows GUI parent."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _emit(payload: dict) -> None:
    sys.stdout.write(EVENT_PREFIX + json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _redirect_native_stderr(path: Path) -> int:
    """Redirect OS-level fd 2 so libxml2 diagnostics never leak to console."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    fd = os.open(str(path), flags, 0o666)
    os.dup2(fd, 2)

    # On Windows, native libraries may write through the process standard
    # handle instead of Python/CRT fd 2.  Point that handle at the same file
    # as well; os.dup2 alone is not sufficient for all libxml2 builds.
    if os.name == "nt":
        try:
            import ctypes
            import msvcrt

            stderr_handle = msvcrt.get_osfhandle(2)
            STD_ERROR_HANDLE = -12
            ctypes.windll.kernel32.SetStdHandle(
                STD_ERROR_HANDLE, ctypes.c_void_p(stderr_handle)
            )
        except Exception:
            pass

    if fd != 2:
        os.close(fd)
    return 2




def _install_large_xml_runtime() -> None:
    """Install a13's scalable XPath evaluator inside the worker process.

    The parent process installs the subprocess wrapper, but the worker starts a
    fresh Python interpreter.  Without this explicit install the child would
    execute the original libxml2 XPath engine and could still hit the
    ``growing nodeset hit limit`` on large Noark 5 XML files.
    """
    from noark5_workflow.analysis import a13_large_xml

    a13_large_xml.install()

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("request")
    parser.add_argument("result")
    args = parser.parse_args(argv)

    request_path = Path(args.request)
    result_path = Path(args.result)
    os.environ["DWM_A13_XPATH_WORKER"] = "1"
    _force_utf8_stdio()

    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
        stderr_path = Path(
            request.get("stderr_path")
            or (Path(request["output_dir"]) / "xpath-worker-stderr.log")
        )
        # lxml/libxml2 can write directly to the native stderr descriptor,
        # bypassing Python's sys.stderr and subprocess text wrappers. Redirect
        # fd 2 before importing the XPath engine so these diagnostics are kept
        # with the run instead of appearing in the user's console.
        os.environ["DWM_A13_NATIVE_STDERR_PATH"] = str(stderr_path)
        _redirect_native_stderr(stderr_path)
        _force_utf8_stdio()

        # The worker is a fresh interpreter. Install the scalable evaluator
        # here before importing/running xpath_diagnostics; otherwise the child
        # falls back to the original libxml2 XPath implementation.
        _install_large_xml_runtime()
        from noark5_workflow.analysis.xpath_diagnostics import run_catalog_profiled

        def progress_callback(phase, current, total, test, status, duration):
            _emit({
                "kind": "test_progress",
                "phase": phase,
                "current": current,
                "total": total,
                "test": test,
                "status": status,
                "duration": duration,
            })

        index = run_catalog_profiled(
            request["catalog_path"],
            request["extraction_root"],
            request["output_dir"],
            include_disabled=bool(request.get("include_disabled", True)),
            execution_profile=str(request.get("execution_profile", "normal")),
            progress_callback=progress_callback,
        )
        result_path.write_text(
            json.dumps({"ok": True, "index": index}, ensure_ascii=False),
            encoding="utf-8",
        )
        _emit({"kind": "worker_finished", "ok": True})
        return 0
    except BaseException as exc:
        result_path.write_text(
            json.dumps({
                "ok": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        _emit({
            "kind": "worker_finished",
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        })
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
