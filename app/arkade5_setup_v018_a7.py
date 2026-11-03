"""Read-only Arkade 5 CLI discovery and capability checks (v0.1.8-a7).

A DWM workflow requires an external CLI only if it actually contains one of
Arkade's executable operations.  Importing existing Arkade reports is NOT such
an operation.  Discovery never changes settings or runs programs.  The CLI
probe uses DWM's existing external-tools adapter, not a second implementation.
"""
from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping


ARKADE5_EXECUTION_OPERATIONS = frozenset({
    "arkade5_noark5_test", "arkade5_pronom_analysis",
})

# Small, bounded set of names.  In particular we never recursively scan a
# user's extraction, network shares or DWM output directories.
_CLI_NAMES = (
    "Arkade5CLI.exe", "Arkade5.CLI.exe", "Arkade5.exe",
    "arkade5.exe", "arkade5-cli.exe", "arkade5",
    "arkade5.cmd", "arkade5.bat",
)


@dataclass(frozen=True)
class Arkade5Check:
    configured_path: str
    severity: str  # 'ok', 'warning', 'error'
    version: str
    version_source: str
    message: str

    @property
    def executable(self) -> bool:
        return self.severity != "error"


def requires_arkade_cli(operation_ids) -> bool:
    """Only the two operations that EXECUTE Arkade require its CLI."""
    return bool(ARKADE5_EXECUTION_OPERATIONS.intersection(operation_ids or ()))


def find_arkade5_candidates(*, search_roots=(), env=None) -> tuple[Path, ...]:
    """Read-only, bounded discovery in PATH and standard local install dirs.

    Caller must explicitly select and save a candidate.  No CLI is executed.
    Additional roots are useful for a user-selected directory or for testing.
    """
    env = os.environ if env is None else env
    found: dict[str, Path] = {}

    def add(candidate) -> None:
        if not candidate:
            return
        path = Path(candidate)
        if path.is_file():
            resolved = path.resolve(strict=False)
            found.setdefault(str(resolved).casefold(), resolved)

    # Don't search Windows PATH when the user supplied a mock environment.
    # 'which' is deliberately restricted to known executable names.
    for name in _CLI_NAMES:
        add(shutil.which(name, path=env.get("PATH", "")))

    roots = [Path(item) for item in search_roots]
    for key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        if env.get(key):
            roots.append(Path(env[key]))

    # Each root: exact names, immediate Arkade* subfolders, and a few known
    # one-level executable distribution directories.  No recursive walk.
    for root in roots:
        if not root.is_dir():
            continue
        for name in _CLI_NAMES:
            add(root / name)
        for pattern in ("Arkade*", "arkade*"):
            try:
                packages = sorted(root.glob(pattern))[:40]
            except OSError:
                continue
            for package in packages:
                if package.is_file():
                    add(package)
                elif package.is_dir():
                    for name in _CLI_NAMES:
                        add(package / name)
                        for child in ("bin", "publish", "win-x64"):
                            add(package / child / name)
        if len(found) >= 60:
            break
    return tuple(sorted(found.values(), key=lambda path: str(path).casefold()))


class Arkade5DependencyChecker:
    """Small per-API cache of existing Arkade adapter probes.

    The fingerprint includes mtime/size; a replaced CLI is rechecked. Results
    are short-lived so network-drive or removable-disk failures are not hidden.
    """

    def __init__(self, *, inspector: Callable | None = None, ttl_seconds: float = 45.0):
        self._inspector = inspector
        self._ttl = ttl_seconds
        self._cache: dict[tuple, tuple[float, Arkade5Check]] = {}

    def invalidate(self) -> None:
        self._cache.clear()

    def check(self, settings: Mapping, *, refresh: bool = False) -> Arkade5Check:
        path_string = str(settings.get("arkade5_cli_path", "") or "").strip().strip('"')
        if not path_string:
            return Arkade5Check("", "error", "", "", "Arkade 5 CLI er ikke konfigurert. Åpne Setup.")
        path = Path(path_string).expanduser()
        if not path.is_absolute():
            return Arkade5Check(path_string, "error", "", "", "Arkade 5 CLI må ha en absolutt sti. Åpne Setup.")
        if not path.is_file():
            return Arkade5Check(path_string, "error", "", "", f"Arkade 5 CLI-filen finnes ikke: {path}. Åpne Setup.")
        try:
            stat = path.stat()
        except OSError as exc:
            return Arkade5Check(path_string, "error", "", "", f"Kunne ikke lese Arkade 5 CLI: {exc}")
        key = (str(path).casefold(), stat.st_size, stat.st_mtime_ns)
        now = time.monotonic()
        cached = self._cache.get(key)
        if not refresh and cached and now - cached[0] < self._ttl:
            return cached[1]
        try:
            if self._inspector is None:
                from noark5_workflow.external_tools.arkade5 import inspect_arkade5_cli
                inspector = inspect_arkade5_cli
            else:
                inspector = self._inspector
            status = inspector({"arkade5_cli_path": str(path)}, timeout_seconds=2.5)
            result = getattr(status, "probe_result", None)
            launch_error = str(getattr(result, "launch_error", "") or "")
            timed_out = bool(getattr(result, "timed_out", False))
            if launch_error:
                check = Arkade5Check(str(path), "error", "", "", f"Arkade 5 CLI kan ikke startes: {launch_error}")
            elif timed_out:
                check = Arkade5Check(str(path), "error", "", "", "Arkade 5 CLI svarte ikke innen tidsgrensen.")
            elif not bool(status.ok):
                check = Arkade5Check(str(path), "error", "", "", str(status.message))
            else:
                source = str(status.version_source or "unknown")
                version = str(status.version or "")
                exit_code = getattr(result, "exit_code", None)
                cli_output = (str(getattr(result, "stdout", "") or "") + " "
                              + str(getattr(result, "stderr", "") or "")).casefold()
                identity_confirmed = "arkade" in str(path).casefold() or "arkade" in cli_output
                # The original adapter may infer a version from an EXE's folder
                # even if --version didn't produce any recognizable version.
                if source != "cli":
                    check = Arkade5Check(
                        str(path), "warning", version, source,
                        (f"Arkade 5 CLI finnes, men versjonen er ikke bekreftet av CLI-testen. "
                         f"{status.message} Kontroller programstien i Setup."),
                    )
                elif not identity_confirmed or exit_code not in (None, 0):
                    reason = (
                        "Programfilen kan ikke identifiseres sikkert som Arkade 5 CLI."
                        if not identity_confirmed else
                        f"Versjonskontrollen avsluttet med kode {exit_code}."
                    )
                    check = Arkade5Check(str(path), "warning", version, source,
                                         f"{reason} Bekreft programstien i Setup.")
                else:
                    check = Arkade5Check(str(path), "ok", version, source,
                                         f"Arkade 5 CLI svarer. Versjon: {version}.")
        except (OSError, ValueError, RuntimeError) as exc:
            check = Arkade5Check(str(path), "error", "", "", f"Arkade 5 CLI-testen feilet: {exc}")
        self._cache.clear()
        self._cache[key] = (now, check)
        return check
