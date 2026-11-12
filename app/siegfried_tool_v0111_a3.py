"""Siegfried interoperability for DWM, adapted from SIARD Workflow Manager.

The external ``sf`` executable and its PRONOM signatures are shared, NOT copied.
This module has no import dependency on SIARD Workflow Manager and never
installs, updates, edits Source, or writes to Work. The scan primitives are
available for a later explicit workflow operation; Setup only calls inspect().

Source reference: smult/SIARD-Workflow-Manager,
siard_workflow/core/identifiers/{installer,siegfried}.py.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from collections import Counter
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable, Iterable, Mapping

from app.siegfried_shared_v0111_a2 import find_siegfried_executable


@dataclass(frozen=True)
class SiegfriedCheck:
    ok: bool
    executable: str
    version: str = ""
    signature: str = ""
    message: str = ""


def _windows_hidden() -> dict:
    if sys.platform == "win32":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


def _sf_path(configured: str = "", *, auto_discover: bool = True) -> Path | None:
    """An explicit invalid value is NOT silently replaced during a check."""
    if configured.strip():
        p = Path(configured.strip().strip('"')).expanduser()
        return p.resolve(strict=False)
    if auto_discover:
        return find_siegfried_executable()
    return None


def inspect_siegfried(executable: str = "", *, timeout: float = 8.0,
                       runner: Callable[..., Any] = subprocess.run,
                       auto_discover: bool = True) -> SiegfriedCheck:
    """Test the selected sf binary with ``-version``; do not change anything.

    Runs a fixed argument vector (no shell) in the caller's process context.
    No network, installer or signature update is triggered by this test.
    """
    p = _sf_path(executable, auto_discover=auto_discover)
    if p is None:
        return SiegfriedCheck(False, "", message="Siegfried er ikke funnet. Installer via SIARD Workflow Manager eller velg sf.exe.")
    value = str(p)
    binary = "sf.exe" if sys.platform == "win32" else "sf"
    if p.name.casefold() != binary.casefold():
        return SiegfriedCheck(False, value, message=f"Velg Siegfried-programmet ({binary}), ikke en annen fil.")
    if not p.is_file():
        return SiegfriedCheck(False, value, message="Siegfried-programmet finnes ikke på valgt sti.")
    try:
        result = runner([value, "-version"], capture_output=True, text=True,
                        encoding="utf-8", errors="replace", timeout=timeout,
                        **_windows_hidden())
    except subprocess.TimeoutExpired:
        return SiegfriedCheck(False, value, message="Siegfried svarte ikke innen tidsgrensen.")
    except (OSError, ValueError) as exc:
        return SiegfriedCheck(False, value, message=f"Kunne ikke starte Siegfried: {exc}")
    except Exception as exc:
        return SiegfriedCheck(False, value, message=f"Kunne ikke teste Siegfried: {exc}")
    output = "\n".join(x for x in (result.stdout, result.stderr) if x).strip()
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if result.returncode != 0:
        reason = lines[0] if lines else f"exit-kode {result.returncode}"
        return SiegfriedCheck(False, value, message=f"Siegfried-test feilet: {reason[:220]}")
    if not lines or not re.search(r"\bsiegfried\b", output, flags=re.IGNORECASE):
        return SiegfriedCheck(False, value, message="Programmet svarte, men identifiseres ikke som Siegfried.")
    first = next((line for line in lines if "siegfried" in line.casefold()), lines[0])
    sig = next((line for line in lines if "pronom" in line.casefold() or "signature" in line.casefold()), "")
    return SiegfriedCheck(True, value, version=first[:250], signature=sig[:300],
                          message="Siegfried svarer. Ingen filer er skannet.")


def parse_siegfried_json(payload: str | bytes | Mapping[str, Any]) -> dict[str, Any]:
    """Normalize sf -json output to PUID counts without RAF assessments.

    Unknown and multi-match cases remain explicit. The original JSON must be
    retained as separate evidence by the eventual DWM workflow operation.
    """
    if isinstance(payload, (str, bytes)):
        document = json.loads(payload)
    else:
        document = payload
    if not isinstance(document, Mapping) or not isinstance(document.get("files"), list):
        raise ValueError("Ugyldig Siegfried JSON: forventer objekt med 'files'-liste.")
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    files: list[dict[str, Any]] = []
    for item in document["files"]:
        if not isinstance(item, Mapping):
            raise ValueError("Ugyldig filoppføring i Siegfried JSON.")
        matches = item.get("matches")
        if matches is None:
            matches = []
        if not isinstance(matches, list):
            raise ValueError("Ugyldig matches-felt i Siegfried JSON.")
        known = [m for m in matches if isinstance(m, Mapping) and
                 re.fullmatch(r"(?:fmt|x-fmt)/\d+", str(m.get("id") or ""), flags=re.IGNORECASE)]
        selected = known[0] if known else {}
        puid = str(selected.get("id") or "")
        name = str(selected.get("format") or "")
        version = str(selected.get("version") or "")
        filename = str(item.get("filename") or "")
        if not filename:
            raise ValueError("Siegfried JSON mangler filename.")
        errors = item.get("errors") or ""
        record = {
            "filename": filename,
            "puid": puid,
            "format": name,
            "version": version,
            "identified": bool(puid),
            "matches": len(matches),
            "ambiguous": len(known) > 1,
            "errors": errors,
        }
        files.append(record)
        key = (puid, name, version)
        group = groups.setdefault(key, {"puid": puid, "format": name,
                                         "version": version, "count": 0})
        group["count"] += 1
    ordered = sorted(groups.values(), key=lambda g: (not bool(g["puid"]), g["puid"], g["format"], g["version"]))
    return {
        "evidence_type": "dwm_siegfried_pronom_identification",
        "files_total": len(files),
        "identified": sum(int(f["identified"]) for f in files),
        "unidentified": sum(int(not f["identified"]) for f in files),
        "ambiguous": sum(int(f["ambiguous"]) for f in files),
        "format_groups": ordered,
        "files": files,
    }


def identify_siegfried_files(executable: str | Path, source_root: str | Path,
                              paths: Iterable[str | Path], *, timeout: int = 600,
                              runner: Callable[..., Any] = subprocess.run,
                              progress_cb: Callable[[int, int], None] | None = None,
                              file_progress_cb: Callable[[int, int], None] | None = None,
                              cancelled_cb: Callable[[], bool] | None = None,
                              raw_records=None) -> dict[str, Any]:
    """Explicit, read-only, bounded file-list identification from SIARD's pattern.

    This is a reusable backend, not automatically invoked by Setup or Basic.
    Batches contain at most 100 paths and have a Windows-safe command length.
    Paths must resolve inside Source; no recursive discovery or Source writes.
    """
    root = Path(source_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Source må være en mappe.")
    files = []
    for value in paths:
        path = Path(value).resolve(strict=True)
        if not path.is_file() or not path.is_relative_to(root):
            raise ValueError("Alle Siegfried-filer må være innenfor valgt Source.")
        files.append(str(path))
    if not files:
        return parse_siegfried_json({"files": []})
    status = inspect_siegfried(str(executable), runner=runner, auto_discover=False)
    if not status.ok:
        raise ValueError(status.message)
    batches: list[list[str]] = []
    current: list[str] = []
    chars = len(str(executable)) + 20
    for path in files:
        if current and (len(current) >= 100 or chars + len(path) + 3 > 20000):
            batches.append(current)
            current = []
            chars = len(str(executable)) + 20
        current.append(path)
        chars += len(path) + 3
    if current:
        batches.append(current)
    all_records: list[dict[str, Any]] = []
    done_files = 0
    for batch_index, batch in enumerate(batches):
        if cancelled_cb is not None and cancelled_cb():
            raise InterruptedError('Siegfried-skanningen ble avbrutt.')
        result = runner([str(executable), "-multi", "64", "-json", *batch],
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=timeout, **_windows_hidden())
        if result.returncode != 0:
            raise RuntimeError(f"Siegfried skanning feilet: {str(result.stderr)[:250]}")
        document = json.loads(result.stdout)
        if not isinstance(document, Mapping) or not isinstance(document.get("files"), list):
            raise ValueError("Siegfried returnerte ugyldig JSON.")
        actual_files = document["files"]
        expected = Counter(os.path.normcase(os.path.normpath(x)) for x in batch)
        returned = Counter(
            os.path.normcase(os.path.normpath(str(x.get("filename") or "")))
            for x in actual_files if isinstance(x, Mapping)
        )
        if returned != expected:
            raise RuntimeError("Siegfried returnerte ikke én identifikasjon per forespurt fil.")
        if raw_records is not None:
            for item in actual_files:
                raw_records.write(json.dumps(item, ensure_ascii=False) + "\n")
            raw_records.flush()
        all_records.extend(actual_files)
        if progress_cb is not None:
            progress_cb(batch_index + 1, len(batches))
        done_files += len(actual_files)
        if file_progress_cb is not None:
            file_progress_cb(done_files, len(files))
    if cancelled_cb is not None and cancelled_cb():
        raise InterruptedError('Siegfried-skanningen ble avbrutt.')
    parsed = parse_siegfried_json({"files": all_records})
    parsed["siegfried_version"] = status.version
    parsed["siegfried_signature"] = status.signature
    return parsed
