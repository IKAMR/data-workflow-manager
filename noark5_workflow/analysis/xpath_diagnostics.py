from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
import os
from pathlib import Path
import platform
import sys
from time import perf_counter
from typing import Any, Callable

from . import xpath_test_engine as engine


def _physical_memory_bytes() -> int | None:
    # Standard-library only: keep diagnostics portable on Windows Server/Linux.
    if os.name == "nt":
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            state = MEMORYSTATUSEX()
            state.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
                return int(state.ullTotalPhys)
        except Exception:
            return None
    else:
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return int(pages) * int(page_size)
        except (AttributeError, OSError, ValueError):
            return None
    return None


def _environment() -> dict[str, Any]:
    return {
        "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "cpu_logical_count": os.cpu_count(),
        "physical_memory_bytes": _physical_memory_bytes(),
    }


def _path_info(path: Path) -> dict[str, Any]:
    text = str(path)
    anchor = path.anchor
    is_unc = text.startswith("\\\\") or text.startswith("//")
    info = {
        "path": text,
        "anchor": anchor,
        "is_unc": is_unc,
    }
    try:
        stat = path.stat()
        info["size_bytes"] = int(stat.st_size)
        info["mtime_ns"] = int(stat.st_mtime_ns)
    except OSError as exc:
        info["stat_error"] = f"{type(exc).__name__}: {exc}"
    return info


def _metric_descriptor(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "metric_id": spec.get("id"),
        "metric_type": spec.get("type", "xpath"),
        "expression": spec.get("expression"),
        "select": spec.get("select"),
        "value": spec.get("value"),
    }


def _aggregate_metric_timings(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], dict[str, Any]] = {}
    for item in items:
        key = (
            item.get("metric_id"),
            item.get("metric_type"),
            item.get("expression"),
            item.get("select"),
            item.get("value"),
        )
        current = groups.get(key)
        if current is None:
            current = {
                "metric_id": item.get("metric_id"),
                "metric_type": item.get("metric_type"),
                "expression": item.get("expression"),
                "select": item.get("select"),
                "value": item.get("value"),
                "calls": 0,
                "duration_seconds": 0.0,
            }
            groups[key] = current
        current["calls"] += 1
        current["duration_seconds"] += float(item.get("duration_seconds") or 0.0)

    rows = list(groups.values())
    for row in rows:
        row["duration_seconds"] = round(row["duration_seconds"], 6)
    return sorted(rows, key=lambda row: row["duration_seconds"], reverse=True)


def run_catalog_profiled(
    catalog_path: str | Path,
    extraction_root: str | Path,
    output_dir: str | Path,
    *,
    include_disabled: bool = True,
    execution_profile: str = "normal",
    progress_callback=None,
) -> dict[str, Any]:
    """Run the existing catalogue unchanged, adding diagnostic instrumentation.

    a16.2 deliberately does not add caching, parallel workers or XPath
    precompilation. It establishes a reproducible baseline before performance
    behaviour changes.
    """
    output_dir = Path(output_dir)
    extraction_root = Path(extraction_root)

    original_run_test = engine.run_test
    original_normalise_tree = engine._normalise_tree
    original_eval_metrics = engine._eval_metrics

    current: dict[str, Any] | None = None

    def profiled_normalise_tree(path: Path):
        nonlocal current
        started = perf_counter()
        tree = original_normalise_tree(path)
        duration = perf_counter() - started
        if current is not None:
            current["tree_preparations"].append(
                {
                    **_path_info(Path(path)),
                    "duration_seconds": round(duration, 6),
                }
            )
        return tree

    def profiled_eval_metrics(node, metrics):
        nonlocal current
        result = {}
        for spec in metrics:
            started = perf_counter()
            try:
                # The production implementation already evaluates metrics in
                # sequence. Calling it with one specification preserves the
                # calculation while identifying the exact failing metric.
                partial = original_eval_metrics(node, [spec])
                result.update(partial)
            except Exception as exc:
                if current is not None:
                    current["metric_error"] = {
                        **_metric_descriptor(spec),
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                raise
            finally:
                if current is not None:
                    current["metric_timings"].append(
                        {
                            **_metric_descriptor(spec),
                            "duration_seconds": round(
                                perf_counter() - started,
                                6,
                            ),
                        }
                    )
        return result

    def profiled_run_test(
        test: dict[str, Any],
        root: str | Path,
        standard_registry: dict[str, Any] | None = None,
    ):
        nonlocal current
        profile = {
            "tree_preparations": [],
            "metric_timings": [],
            "metric_error": None,
        }
        current = profile
        wall_started = perf_counter()
        try:
            result = original_run_test(
                test,
                root,
                standard_registry=standard_registry,
            )
        finally:
            current = None

        total_seconds = float(
            result.get("timing", {}).get("duration_seconds")
            or (perf_counter() - wall_started)
        )
        tree_seconds = sum(
            float(item.get("duration_seconds") or 0.0)
            for item in profile["tree_preparations"]
        )
        metric_rows = _aggregate_metric_timings(profile["metric_timings"])
        metric_seconds = sum(
            float(item.get("duration_seconds") or 0.0)
            for item in metric_rows
        )

        source = Path(root) / test["source_xml"]
        diagnostics = {
            "source": _path_info(source),
            "tree_preparation": {
                "calls": len(profile["tree_preparations"]),
                "duration_seconds": round(tree_seconds, 6),
                "sources": profile["tree_preparations"],
            },
            "metrics": metric_rows,
            "metric_evaluation_seconds": round(metric_seconds, 6),
            "other_seconds": round(
                max(0.0, total_seconds - tree_seconds - metric_seconds),
                6,
            ),
        }
        if profile["metric_error"] is not None:
            diagnostics["error_context"] = profile["metric_error"]
        elif result.get("status") == "error":
            diagnostics["error_context"] = {
                "special_handler": test.get("execution", {}).get("kind"),
                "error": result.get("error"),
                "note": (
                    "Feilen oppstod utenfor den generiske metric-evalueringen; "
                    "se testdefinisjonen og special_handler."
                ),
            }

        result["diagnostics"] = diagnostics
        return result

    engine._normalise_tree = profiled_normalise_tree
    engine._eval_metrics = profiled_eval_metrics
    engine.run_test = profiled_run_test
    try:
        index = engine.run_catalog(
            catalog_path,
            extraction_root,
            output_dir,
            include_disabled=include_disabled,
            execution_profile=execution_profile,
            progress_callback=progress_callback,
        )
    finally:
        # Never leak instrumentation into another operation or future worker.
        engine.run_test = original_run_test
        engine._normalise_tree = original_normalise_tree
        engine._eval_metrics = original_eval_metrics

    rows = []
    errors = []
    results_dir = output_dir / "results"
    for row in index.get("tests", []):
        result_path = output_dir / row["file"]
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        diagnostics = result.get("diagnostics") or {}
        timing = result.get("timing") or {}
        perf_row = {
            "test_id": result.get("test_id"),
            "legacy_job_id": result.get("definition", {}).get("legacy", {}).get("job_id"),
            "status": result.get("status"),
            "source_xml": result.get("source_xml"),
            "duration_seconds": timing.get("duration_seconds"),
            "tree_preparation_seconds": (
                diagnostics.get("tree_preparation") or {}
            ).get("duration_seconds"),
            "metric_evaluation_seconds": diagnostics.get("metric_evaluation_seconds"),
            "other_seconds": diagnostics.get("other_seconds"),
        }
        rows.append(perf_row)

        if result.get("status") == "error":
            errors.append(
                {
                    **perf_row,
                    "error": result.get("error"),
                    "error_context": diagnostics.get("error_context"),
                }
            )

    rows.sort(
        key=lambda row: float(row.get("duration_seconds") or 0.0),
        reverse=True,
    )

    performance = {
        "diagnostics_format_version": 1,
        "environment": _environment(),
        "extraction_root": str(extraction_root),
        "catalog": str(Path(catalog_path)),
        "execution_profile": execution_profile,
        "summary": {
            "tests": len(rows),
            "errors": len(errors),
            "total_test_duration_seconds": round(
                sum(float(row.get("duration_seconds") or 0.0) for row in rows),
                6,
            ),
            "total_tree_preparation_seconds": round(
                sum(float(row.get("tree_preparation_seconds") or 0.0) for row in rows),
                6,
            ),
            "total_metric_evaluation_seconds": round(
                sum(float(row.get("metric_evaluation_seconds") or 0.0) for row in rows),
                6,
            ),
        },
        "slowest_tests": rows[:15],
        "errors": errors,
        "tests": rows,
    }

    performance_path = output_dir / "performance-diagnostics.json"
    performance_path.write_text(
        json.dumps(performance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    index["performance_diagnostics"] = {
        "file": performance_path.name,
        "format_version": performance["diagnostics_format_version"],
        "summary": performance["summary"],
    }
    (output_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return index
