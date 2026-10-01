from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Any

from .cli_runner import ExternalCliRequest, ExternalCliRunResult, run_external_cli

_VERSION_RE = re.compile(r"(?<!\d)(\d+\.\d+(?:\.\d+)?)(?!\d)")
_PROBES: tuple[tuple[str, ...], ...] = (("--version",), ("version",), ("-v",))


@dataclass(frozen=True)
class Arkade5CliStatus:
    configured_path: str
    exists: bool
    is_file: bool
    ok: bool
    version: str = ""
    version_source: str = ""
    probe_args: tuple[str, ...] = ()
    message: str = ""
    probe_result: ExternalCliRunResult | None = None


def configured_arkade5_cli(settings: Mapping[str, Any] | None) -> Path | None:
    if not settings:
        return None
    value = str(settings.get("arkade5_cli_path", "") or "").strip().strip('"')
    return Path(value) if value else None


def _version_from_text(*values: str) -> str:
    for value in values:
        match = _VERSION_RE.search(str(value or ""))
        if match:
            return match.group(1)
    return ""


def _version_from_path(path: Path) -> str:
    for part in reversed(path.parts):
        version = _version_from_text(part)
        if version:
            return version
    return ""


def inspect_arkade5_cli(
    value: Mapping[str, Any] | str | Path | None,
    *,
    timeout_seconds: float = 10.0,
) -> Arkade5CliStatus:
    """Validate configured Arkade 5 CLI and detect its version when possible.

    Detection deliberately uses the generic external CLI runner. The adapter
    tries common read-only version switches and falls back to a version token
    in the configured installation path (for example Arkade5CLI-2.12.3).
    No archive data is read or modified by this probe.
    """
    if isinstance(value, Mapping):
        path = configured_arkade5_cli(value)
    elif value is None:
        path = None
    else:
        raw = str(value).strip().strip('"')
        path = Path(raw) if raw else None

    if path is None:
        return Arkade5CliStatus(
            configured_path="",
            exists=False,
            is_file=False,
            ok=False,
            message="Arkade 5 CLI er ikke konfigurert.",
        )

    exists = path.exists()
    is_file = path.is_file() if exists else False
    if not exists:
        return Arkade5CliStatus(
            configured_path=str(path),
            exists=False,
            is_file=False,
            ok=False,
            message=f"Arkade 5 CLI finnes ikke: {path}",
        )
    if not is_file:
        return Arkade5CliStatus(
            configured_path=str(path),
            exists=True,
            is_file=False,
            ok=False,
            message=f"Arkade 5 CLI-stien peker ikke på en fil: {path}",
        )

    last_result: ExternalCliRunResult | None = None
    for probe in _PROBES:
        result = run_external_cli(
            ExternalCliRequest(
                executable=path,
                args=probe,
                timeout_seconds=timeout_seconds,
                tool_id="arkade5",
                operation_id="detect_version",
                metadata={"probe": list(probe)},
            )
        )
        last_result = result
        version = "" if result.launch_error else _version_from_text(result.stdout, result.stderr)
        if version:
            return Arkade5CliStatus(
                configured_path=str(path),
                exists=True,
                is_file=True,
                ok=True,
                version=version,
                version_source="cli",
                probe_args=probe,
                message=f"Arkade 5 CLI {version} funnet.",
                probe_result=result,
            )

    path_version = _version_from_path(path)
    if path_version:
        return Arkade5CliStatus(
            configured_path=str(path),
            exists=True,
            is_file=True,
            ok=True,
            version=path_version,
            version_source="path",
            message=(
                f"Arkade 5 CLI funnet. Versjon {path_version} er utledet fra stien; "
                "CLI-en svarte ikke med en gjenkjennelig versjon."
            ),
            probe_result=last_result,
        )

    return Arkade5CliStatus(
        configured_path=str(path),
        exists=True,
        is_file=True,
        ok=True,
        version="",
        version_source="unknown",
        message="Arkade 5 CLI funnet, men versjonen kunne ikke identifiseres.",
        probe_result=last_result,
    )
