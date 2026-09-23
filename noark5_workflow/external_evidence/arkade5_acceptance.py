from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .arkade5 import list_arkade5_imports, load_arkade5_import
from .arkade5_integration_health import build_arkade5_integration_health


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_arkade5_practical_acceptance(*, work_operations: str | Path, repo_root: str | Path | None = None) -> dict[str, Any]:
    work = Path(work_operations)
    root = Path(repo_root) if repo_root is not None else _repo_root()
    integration = build_arkade5_integration_health(repo_root=root)
    catalog = _read_json(root / "config/noark5/external/arkade5_test_catalog.json")
    known_ids = {str(row.get("arkade_test_id") or "").upper() for row in catalog.get("tests") or []}
    imports = list_arkade5_imports(work)
    rows = []
    blocking = []
    observations = []

    if integration.get("status") != "OK":
        blocking.append({"check_id": "repository_integration_health", "detail": "Arkade-integrasjonens repository health check er ikke OK."})
    if not imports:
        blocking.append({"check_id": "minimum_imports", "detail": "Ingen importerte Arkade 5-rapporter finnes i work_operations."})

    for manifest in imports:
        import_id = str(manifest.get("import_id") or "").strip()
        source = manifest.get("source") or {}
        source_rel = str(source.get("preserved_file") or "").strip()
        normalized_rel = str(manifest.get("normalized_file") or "").strip()
        source_path = work / source_rel if source_rel else None
        normalized_path = work / normalized_rel if normalized_rel else None
        issues = []
        notes = []
        actual_sha = None

        if not import_id:
            issues.append("manifest mangler import_id")
        if source_path is None or not source_path.is_file():
            issues.append("bevart kildefil mangler")
        else:
            actual_sha = _sha256(source_path)
            expected_sha = str(source.get("sha256") or "").strip()
            if not expected_sha or actual_sha != expected_sha:
                issues.append("SHA-256 for bevart kildefil samsvarer ikke med manifest")

        normalized = {}
        if normalized_path is None or not normalized_path.is_file():
            issues.append("normalisert resultatfil mangler")
        else:
            try:
                normalized = _read_json(normalized_path)
            except (OSError, UnicodeError, json.JSONDecodeError):
                issues.append("normalisert resultatfil kan ikke leses som JSON")

        test_ids = []
        error_tests = 0
        warning_tests = 0
        if normalized:
            if normalized.get("format_version") != 2:
                issues.append(f"normalisert formatversjon er {normalized.get('format_version')!r}, forventet 2")
            tests = normalized.get("tests") or []
            test_ids = [str(row.get("test_id") or "").upper() for row in tests if str(row.get("test_id") or "").strip()]
            unknown = sorted(set(test_ids) - known_ids)
            if unknown:
                issues.append("ukjente Arkade-test-ID-er: " + ", ".join(unknown))
            if len(test_ids) != len(set(test_ids)):
                issues.append("dupliserte Arkade-test-ID-er i normalisert rapport")
            source_version = normalized.get("source_version")
            if not source_version:
                notes.append("Arkade source_version kunne ikke utledes fra kildefilsti")
            elif str(source_version) != "2.13.0":
                notes.append(f"rapporten utleder Arkade-versjon {source_version}; kunnskapskatalogen er pinnet til 2.13.0")
            error_tests = sum(1 for row in tests if row.get("source_status") == "error")
            warning_tests = sum(1 for row in tests if row.get("source_status") == "warning")
            if error_tests:
                notes.append(f"Arkade rapporterer feil i {error_tests} kontrollområder; dette er arkivevidens, ikke integrasjonsfeil")
            if warning_tests:
                notes.append(f"Arkade rapporterer advarsler i {warning_tests} kontrollområder")

        reconciliation = None
        if import_id:
            try:
                reconciliation = load_arkade5_import(work, import_id).get("reconciliation")
            except Exception as exc:
                issues.append(f"importen kan ikke lastes komplett: {exc}")
        if reconciliation is None:
            notes.append("ingen DWM reconciliation er materialisert for denne importen")

        row = {
            "import_id": import_id or None,
            "source_file": source.get("original_name"),
            "source_sha256_manifest": source.get("sha256"),
            "source_sha256_actual": actual_sha,
            "normalized_file": normalized_rel or None,
            "normalized_test_count": len(test_ids),
            "arkade_error_test_count": error_tests,
            "arkade_warning_test_count": warning_tests,
            "issues": issues,
            "observations": notes,
            "status": "OK" if not issues else "ERROR"
        }
        rows.append(row)
        blocking.extend({"check_id": "import_integrity", "import_id": import_id or None, "detail": issue} for issue in issues)
        observations.extend({"import_id": import_id or None, "detail": note} for note in notes)

    return {
        "format_version": 1,
        "acceptance_model_id": "dwm.arkade5.practical-acceptance.v1",
        "scope": "one_work_operations_tree",
        "work_operations": str(work),
        "repository_integration_health": integration,
        "status": "READY" if not blocking else "NOT_READY",
        "summary": {
            "imports": len(rows),
            "imports_ok": sum(1 for row in rows if row["status"] == "OK"),
            "blocking_issues": len(blocking),
            "observations": len(observations)
        },
        "blocking_issues": blocking,
        "observations": observations,
        "imports": rows
    }


def write_arkade5_practical_acceptance(output_path: str | Path, *, work_operations: str | Path, repo_root: str | Path | None = None) -> Path:
    result = build_arkade5_practical_acceptance(work_operations=work_operations, repo_root=repo_root)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
