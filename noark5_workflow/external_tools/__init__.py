"""Adapters and generic runner for external command-line tools."""

from .arkade5 import Arkade5CliStatus, configured_arkade5_cli, inspect_arkade5_cli
from .cli_runner import ExternalCliRequest, ExternalCliRunResult, run_external_cli

__all__ = [
    "Arkade5CliStatus",
    "ExternalCliRequest",
    "ExternalCliRunResult",
    "configured_arkade5_cli",
    "inspect_arkade5_cli",
    "run_external_cli",
]
