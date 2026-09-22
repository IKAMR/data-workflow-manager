from __future__ import annotations

from dataclasses import asdict, dataclass
import ctypes
import os
from pathlib import Path
from typing import Any

try:
    import psutil
except ImportError:  # pragma: no cover - requirements-core includes psutil
    psutil = None


VALID_STRATEGIES = {"auto", "memory", "streaming", "disk"}

# Conservative defaults for tree-oriented XML work. A DOM/tree can use several
# times the source file size in memory, depending on namespaces, strings and
# node count.
DEFAULT_XML_TREE_OVERHEAD = 6.0
AUTO_MEMORY_FRACTION = 0.25
AUTO_STREAMING_FILE_THRESHOLD = 2 * 1024**3
AUTO_NETWORK_MEMORY_FILE_THRESHOLD = 1024**3


@dataclass(frozen=True)
class ResourceDecision:
    requested: str
    selected: str
    reason: str
    storage_kind: str
    file_size_bytes: int | None
    available_memory_bytes: int | None
    estimated_memory_bytes: int | None
    recommended_workers: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def available_memory_bytes(environment: dict[str, Any] | None = None) -> int | None:
    if environment:
        value = environment.get("available_memory_bytes")
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                pass

    if psutil is not None:
        try:
            return int(psutil.virtual_memory().available)
        except Exception:
            return None
    return None


def _windows_drive_type(path: Path) -> str | None:
    if os.name != "nt":
        return None
    text = str(path)
    if text.startswith("\\\\") or text.startswith("//"):
        return "network"

    anchor = path.anchor
    if not anchor:
        return None

    try:
        # DRIVE_* values from WinBase.h
        drive_type = int(ctypes.windll.kernel32.GetDriveTypeW(str(anchor)))
    except Exception:
        return None

    return {
        2: "removable",
        3: "local",
        4: "network",
        5: "optical",
        6: "ramdisk",
    }.get(drive_type, "unknown")


def storage_kind(path: str | Path) -> str:
    path = Path(path)
    text = str(path)
    if text.startswith("\\\\") or text.startswith("//"):
        return "network"

    win_kind = _windows_drive_type(path)
    if win_kind:
        return win_kind

    # On non-Windows systems we do not guess mount semantics from the path
    # alone. "local" here means "not identified as remote".
    return "local"


def estimate_memory_bytes(
    file_size_bytes: int | None,
    *,
    workload: str = "generic",
) -> int | None:
    if file_size_bytes is None:
        return None

    factor = 1.25
    if workload in {"xml_tree", "xpath_tree", "xml_schema_tree"}:
        factor = DEFAULT_XML_TREE_OVERHEAD
    elif workload in {"binary_buffer", "text_buffer"}:
        factor = 1.15
    elif workload in {"stream"}:
        factor = 0.05

    return int(max(1, file_size_bytes) * factor)


def recommend_worker_count(
    *,
    environment: dict[str, Any] | None = None,
    per_worker_memory_bytes: int | None = None,
    max_workers: int | None = None,
) -> int:
    environment = environment or {}
    logical = environment.get("cpu_logical_count") or os.cpu_count() or 1
    try:
        logical = max(1, int(logical))
    except (TypeError, ValueError):
        logical = 1

    # Keep one logical CPU free for UI/OS and avoid an overly aggressive
    # default even on large servers.
    cpu_limit = max(1, logical - 1)
    cpu_limit = min(cpu_limit, 8)

    memory_limit = cpu_limit
    available = available_memory_bytes(environment)
    if per_worker_memory_bytes and available:
        # Keep at least half of currently available memory outside the worker
        # pool so concurrent parsers do not destabilize the client.
        safe_for_workers = int(available * 0.50)
        memory_limit = max(1, safe_for_workers // max(1, int(per_worker_memory_bytes)))

    result = max(1, min(cpu_limit, memory_limit))
    if max_workers is not None:
        result = max(1, min(result, int(max_workers)))
    return result


def choose_resource_strategy(
    path: str | Path,
    *,
    requested: str = "auto",
    workload: str = "generic",
    expected_reuse: int = 1,
    environment: dict[str, Any] | None = None,
) -> ResourceDecision:
    path = Path(path)
    requested = str(requested or "auto").strip().lower()
    if requested not in VALID_STRATEGIES:
        raise ValueError(
            f"Ugyldig ressursstrategi: {requested}. "
            f"Gyldige verdier: {', '.join(sorted(VALID_STRATEGIES))}"
        )

    try:
        file_size = int(path.stat().st_size)
    except OSError:
        file_size = None

    available = available_memory_bytes(environment)
    estimated = estimate_memory_bytes(file_size, workload=workload)
    kind = storage_kind(path)

    if requested != "auto":
        selected = requested
        reason = f"eksplisitt valgt strategi: {requested}"
    elif file_size is None:
        selected = "streaming"
        reason = "filstørrelse ukjent; streaming er sikrest"
    elif (
        file_size >= AUTO_STREAMING_FILE_THRESHOLD
        or (estimated is not None and available is not None and estimated > available * AUTO_MEMORY_FRACTION)
    ):
        selected = "streaming"
        if file_size >= AUTO_STREAMING_FILE_THRESHOLD:
            reason = (
                f"stor fil ({file_size} bytes) overstiger terskel "
                f"{AUTO_STREAMING_FILE_THRESHOLD} bytes"
            )
        else:
            reason = (
                "estimert minnebehov overstiger sikker andel av tilgjengelig RAM"
            )
    elif (
        kind == "network"
        and expected_reuse > 1
        and available is not None
        and file_size <= AUTO_NETWORK_MEMORY_FILE_THRESHOLD
        and file_size <= available * 0.15
    ):
        selected = "memory"
        reason = (
            "nettverkskilde med forventet gjenbruk og tilstrekkelig ledig RAM; "
            "unngår gjentatt nettverkslesing"
        )
    elif kind == "network":
        selected = "streaming"
        reason = "nettverkskilde uten trygg gevinst ved full RAM-buffer"
    else:
        selected = "disk"
        reason = "lokal kilde og moderat filstørrelse; direkte filbasert behandling"

    worker_memory = estimated if selected in {"memory", "disk"} else max(
        64 * 1024**2,
        int((file_size or 0) * 0.05),
    )
    workers = recommend_worker_count(
        environment=environment,
        per_worker_memory_bytes=worker_memory,
    )

    return ResourceDecision(
        requested=requested,
        selected=selected,
        reason=reason,
        storage_kind=kind,
        file_size_bytes=file_size,
        available_memory_bytes=available,
        estimated_memory_bytes=estimated,
        recommended_workers=workers,
    )
