from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

_INVALID = re.compile(r'[^A-Za-z0-9._-]+')


def _safe(value: str) -> str:
    cleaned = _INVALID.sub("_", str(value or "").strip()).strip("._")
    return cleaned or "unknown"


def artifact_run_token(ctx, operation_id: str) -> str:
    """Stable, human-readable unique folder token for one job/run/operation."""
    job_id = str(ctx.metadata.get("job_id", "") or "").strip()
    run_id = str(
        ctx.metadata.get("run_id", "")
        or ctx.settings.get("_current_run_id", "")
        or ""
    ).strip()
    if not run_id:
        run_id = "RUN-" + datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f") + "-" + uuid4().hex[:8]
    parts = []
    if job_id:
        parts.append(_safe(job_id))
    parts.append(_safe(run_id))
    return "__".join(parts)


def artifact_run_dir(ctx, *parts: str, operation_id: str) -> Path:
    if ctx.work_operations is None:
        raise ValueError("Jobben mangler Work - operations.")
    out = Path(ctx.work_operations).joinpath(*parts, artifact_run_token(ctx, operation_id))
    out.mkdir(parents=True, exist_ok=True)
    return out


def write_artifact_manifest(
    ctx,
    output_dir: Path,
    *,
    operation_id: str,
    definition_id: str = "",
    definition_version: str = "",
) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = str(
        ctx.metadata.get("run_id", "")
        or ctx.settings.get("_current_run_id", "")
        or ""
    )
    document = {
        "schema_version": 1,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "run_id": run_id,
        "job_id": str(ctx.metadata.get("job_id", "") or ""),
        "operation_id": str(operation_id),
        "definition_id": str(definition_id or ""),
        "definition_version": str(definition_version or ""),
        "source_extraction": str(ctx.extraction_root),
        "work_operations_effective": str(ctx.work_operations or ""),
        "artifact_root": str(output_dir),
    }
    path = output_dir / "artifact_manifest.json"
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def artifact_belongs_to_context(output_dir: Path, ctx) -> bool:
    """Filter new artifacts by job/source while accepting legacy folders."""
    manifest = Path(output_dir) / "artifact_manifest.json"
    if not manifest.is_file():
        return True
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    expected_job = str(ctx.metadata.get("job_id", "") or "")
    actual_job = str(data.get("job_id", "") or "")
    if expected_job and actual_job and expected_job != actual_job:
        return False

    expected_source = str(Path(ctx.extraction_root))
    actual_source = str(data.get("source_extraction", "") or "")
    return not actual_source or Path(actual_source) == Path(expected_source)
