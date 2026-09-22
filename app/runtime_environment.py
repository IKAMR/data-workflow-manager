from __future__ import annotations

from datetime import datetime
import os
import platform
import sys
from typing import Any

try:
    import psutil
except ImportError:  # pragma: no cover - requirements-core includes psutil
    psutil = None


def capture_runtime_environment() -> dict[str, Any]:
    """Capture a format-neutral snapshot of the worker/client environment.

    The snapshot is deliberately generic and belongs to the run, not to a
    Noark 5 operation. It can therefore be reused by future profiles/workers.
    """
    logical = os.cpu_count()
    physical = None
    total_memory = None
    available_memory = None

    if psutil is not None:
        try:
            physical = psutil.cpu_count(logical=False)
        except Exception:
            physical = None
        try:
            vm = psutil.virtual_memory()
            total_memory = int(vm.total)
            available_memory = int(vm.available)
        except Exception:
            pass

    return {
        "schema_version": 1,
        "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "host": platform.node(),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable": sys.executable,
        "cpu_logical_count": logical,
        "cpu_physical_count": physical,
        "physical_memory_bytes": total_memory,
        "available_memory_bytes": available_memory,
    }
