from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

FORMAT_VERSION = 1


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_text(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace"), "latin-1"


def _parse_statistics(path: Path) -> dict[str, Any]:
    text, encoding = _read_text(path)
    sample = text[:65536]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";" if ";" in sample else ","

    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    fieldnames = [str(value or "") for value in (reader.fieldnames or [])]
    rows: list[dict[str, str]] = []
    for raw_row in reader:
        if raw_row is None:
            continue
        row = {
            str(key or ""): "" if value is None else str(value)
            for key, value in raw_row.items()
        }
        if any(value.strip() for value in row.values()):
            rows.append(row)

    return {
        "format_version": FORMAT_VERSION,
        "evidence_type": "arkade5_pronom_format_statistics",
        "source_system": "Arkade 5",
        "identification_engine": "Siegfried / PRONOM",
        "source": {
            "original_name": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        },
        "csv": {
            "encoding": encoding,
            "delimiter": delimiter,
            "fieldnames": fieldnames,
            "row_count": len(rows),
            "rows": rows,
        },
    }


def _find_pronom_files(report_path: Path) -> tuple[Path | None, Path | None]:
    """Find Arkade/Siegfried format outputs next to one Arkade JSON report.

    Statistics are imported. The detailed one-row-per-file inventory is only
    registered as existing evidence in this increment; it is not copied or
    parsed because it can be very large and documents may exist in several
    generations/representations.
    """
    folder = report_path.parent
    statistics: list[Path] = []
    detailed: list[Path] = []
    try:
        entries = list(folder.iterdir())
    except OSError:
        return None, None
    for path in entries:
        if not path.is_file() or path.suffix.casefold() != ".csv":
            continue
        name = path.name.casefold()
        if "filformatinfo-statistikk" in name:
            statistics.append(path)
        elif "filformatinfo" in name:
            detailed.append(path)
    statistics.sort(key=lambda p: p.name.casefold())
    detailed.sort(key=lambda p: p.name.casefold())
    return (statistics[0] if statistics else None, detailed[0] if detailed else None)


def _relative_in_root(work: Path, root: Path, value: str) -> Path | None:
    """Validate a Work-relative reference from a manifest on Windows or POSIX."""
    value = str(value or "").replace("\\", "/")
    if not value or value.startswith("/") or ":" in value:
        return None
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return None
    candidate = work.joinpath(*parts)
    try:
        if candidate.resolve(strict=False).is_relative_to(root.resolve(strict=False)):
            return candidate
    except (OSError, ValueError):
        pass
    return None


def _verified_preserved_statistics(work: Path, root: Path) -> dict[str, Any] | None:
    """Recover PRONOM only from intact, preserved evidence within THIS import.

    In a9/a10, re-discovery of a Noark5 JSON report could overwrite a valid
    PRONOM manifest with `found=false` despite preserved normalized/source
    files.  Recover only after verifying the original preserved CSV against
    the SHA-256 recorded inside normalized PRONOM evidence.  Never search
    Source or another job's Work directory and never invent counts.
    """
    normalized_path = root / "normalized" / "pronom_statistics.json"
    if not normalized_path.is_file():
        return None
    try:
        model = json.loads(normalized_path.read_text(encoding="utf-8"))
        if not isinstance(model, dict) or model.get("evidence_type") != "arkade5_pronom_format_statistics":
            return None
        if model.get("format_version") != FORMAT_VERSION:
            return None
        source = model.get("source") or {}
        digest = str(source.get("sha256") or "").strip().casefold()
        candidate = _relative_in_root(work, root, str(source.get("preserved_file") or ""))
        if candidate is None or not candidate.is_file() or len(digest) != 64:
            return None
        if _sha256(candidate).casefold() != digest:
            return None
        csv_data = model.get("csv") or {}
        if not isinstance(csv_data.get("rows"), list):
            return None
        return model
    except (OSError, ValueError, UnicodeError, TypeError, json.JSONDecodeError):
        return None


def _statistics_metadata(normalized: dict[str, Any], *, work: Path, root: Path) -> dict[str, Any]:
    source = normalized.get("source") or {}
    path = root / "normalized" / "pronom_statistics.json"
    data = normalized.get("csv") or {}
    return {
        "found": True,
        "imported": True,
        "original_name": source.get("original_name"),
        "original_path": source.get("original_path"),
        "size_bytes": source.get("size_bytes"),
        "sha256": source.get("sha256"),
        "preserved_file": source.get("preserved_file"),
        "normalized_file": str(path.relative_to(work)),
        "row_count": int(data.get("row_count") or len(data.get("rows") or [])),
        "fieldnames": list(data.get("fieldnames") or []),
    }


def _atomic_manifest(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_name("." + path.name + "." + uuid4().hex + ".tmp")
    try:
        with tmp.open("x", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def attach_arkade5_pronom_evidence(
    report_path: str | Path,
    *,
    work_operations: str | Path,
    import_id: str,
) -> dict[str, Any]:
    """Attach lightweight PRONOM/Siegfried evidence to an Arkade import.

    Only the statistics CSV is copied and normalized. A detailed per-file CSV
    is documented by path/name/size, but deliberately not imported yet.
    Re-discovering a JSON report without PRONOM files may NEVER erase already
    verified statistics linked to the same import.
    """
    report = Path(report_path)
    work = Path(work_operations)
    root = work / "external_evidence" / "arkade5" / str(import_id)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return {"status": "manifest_missing", "statistics_found": False,
                "statistics_imported": False, "detailed_inventory_found": False}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("Not a manifest object")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return {"status": "manifest_unreadable", "statistics_found": False,
                "statistics_imported": False, "detailed_inventory_found": False}

    statistics, detailed = _find_pronom_files(report)
    old = manifest.get("pronom_evidence") or {}
    old_detailed = old.get("detailed_file_inventory") or {}
    evidence: dict[str, Any] = {
        "format_version": FORMAT_VERSION,
        "source_system": "Arkade 5",
        "identification_engine": "Siegfried / PRONOM",
        "statistics": {"found": False, "imported": False},
        "detailed_file_inventory": {
            "found": bool(old_detailed.get("found")),
            "imported": False,
            "policy": old_detailed.get("policy") or (
                "Dokumenteres som eksisterende kilde, men importeres ikke i dette "
                "inkrementet. Filnivådata håndteres senere fordi dokumentfiler kan "
                "forekomme i flere generasjoner/representasjoner."
            ),
        },
    }
    evidence["detailed_file_inventory"].update({
        key: old_detailed[key]
        for key in ("original_name", "original_path", "size_bytes")
        if key in old_detailed
    })
    if statistics is not None:
        source_dir = root / "source"
        normalized_dir = root / "normalized"
        source_dir.mkdir(parents=True, exist_ok=True)
        normalized_dir.mkdir(parents=True, exist_ok=True)

        copied = source_dir / statistics.name
        source_digest = _sha256(statistics)
        if not copied.exists() or _sha256(copied) != source_digest:
            shutil.copy2(statistics, copied)

        normalized = _parse_statistics(statistics)
        normalized["source"]["preserved_file"] = str(copied.relative_to(work))
        normalized["source"]["original_path"] = str(statistics)
        normalized_path = normalized_dir / "pronom_statistics.json"
        _atomic_manifest(normalized_path, normalized)
        evidence["statistics"].update(
            _statistics_metadata(normalized, work=work, root=root)
        )
    else:
        # Recover old imports affected by the a9/a10 discovery overwrite.
        # The normalised evidence alone is insufficient; verify preserved CSV.
        normalized = _verified_preserved_statistics(work, root)
        if normalized is not None:
            evidence["statistics"].update(
                _statistics_metadata(normalized, work=work, root=root)
            )

    if detailed is not None:
        evidence["detailed_file_inventory"].update({
            "found": True,
            "original_name": detailed.name,
            "original_path": str(detailed),
            "size_bytes": detailed.stat().st_size,
        })

    manifest["pronom_evidence"] = evidence
    _atomic_manifest(manifest_path, manifest)
    return {
        "status": "ok",
        "statistics_found": bool(evidence["statistics"].get("found")),
        "statistics_imported": bool(evidence["statistics"].get("imported")),
        "statistics_row_count": int(evidence["statistics"].get("row_count") or 0),
        "detailed_inventory_found": bool(evidence["detailed_file_inventory"].get("found")),
        "detailed_inventory_imported": False,
        "evidence": evidence,
    }


def load_arkade5_pronom_statistics(
    work_operations: str | Path,
    manifest: dict[str, Any],
) -> dict[str, Any] | None:
    """Load normalized PRONOM evidence belonging to this Arkade import.

    Preserve old manifests and recover valid orphaned normalized statistics
    without mutating Work on a read-only report query.
    """
    work = Path(work_operations)
    evidence = manifest.get("pronom_evidence") or {}
    statistics = evidence.get("statistics") or {}
    import_id = str(manifest.get("import_id") or "")
    if "/" in import_id or "\\" in import_id or import_id in {".", ".."}:
        return None
    if not import_id:
        # Historical callers sometimes provide the PRONOM sub-manifest alone.
        # Keep their explicit, Work-relative reference readable without
        # allowing it to escape Work or cross into a different import.
        relative = str(statistics.get("normalized_file") or "").replace("\\", "/")
        components = relative.split("/")
        if len(components) < 5 or components[:2] != ["external_evidence", "arkade5"]:
            return None
        import_id = components[2]
        if not import_id or import_id in {".", ".."}:
            return None
    root = work / "external_evidence" / "arkade5" / import_id
    path = _relative_in_root(work, root, str(statistics.get("normalized_file") or ""))
    verified = _verified_preserved_statistics(work, root)
    if verified is not None:
        return verified
    if path is not None and path.is_file():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                source = value.get("source") or {}
                # Never report unverifiable counts as authentic when a
                # digest/preserved-source reference explicitly exists.
                if source.get("sha256") or source.get("preserved_file"):
                    return None
                return value  # legacy imports without source checksums
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass
    return None


def _as_int(value: Any) -> int:
    text = str(value or "").strip().replace("\u00a0", " ").replace(" ", "")
    if not text:
        return 0
    try:
        return int(text)
    except ValueError:
        try:
            return int(float(text.replace(",", ".")))
        except ValueError:
            return 0


def summarize_arkade5_pronom_statistics(
    normalized: dict[str, Any] | None,
    *,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build report-safe summary without discarding the imported statistics rows.

    The statistics CSV is small and is retained losslessly in normalized JSON. The
    detailed one-row-per-document inventory is intentionally not loaded here.
    """
    normalized = normalized or {}
    manifest = manifest or {}
    csv_model = normalized.get("csv") or {}
    rows = [row for row in (csv_model.get("rows") or []) if isinstance(row, dict)]

    total_files = 0
    unidentified_files = 0
    format_ids: set[str] = set()
    raf_counts: dict[str, int] = {}
    presentation_rows: list[dict[str, Any]] = []
    unknown_tokens = {"", "-", "ukjent", "unknown", "unknown format", "fmt/unknown"}

    for raw in rows:
        format_id = str(raw.get("Format-ID") or "").strip()
        file_type = str(raw.get("Filtype") or "").strip()
        format_version = str(raw.get("Formatversjon") or "").strip()
        raf = str(raw.get("RAF-220301") or "").strip()
        count = _as_int(raw.get("Antall"))
        total_files += count
        if format_id:
            format_ids.add(format_id)
        if format_id.casefold() in unknown_tokens:
            unidentified_files += count
        raf_key = raf or "(tom)"
        raf_counts[raf_key] = raf_counts.get(raf_key, 0) + count
        presentation_rows.append({
            "format_id": format_id or None,
            "file_type": file_type or None,
            "format_version": format_version or None,
            "raf_220301": raf or None,
            "count": count,
            "source_row": dict(raw),
        })

    detailed = (manifest.get("pronom_evidence") or {}).get("detailed_file_inventory") or {}
    source = normalized.get("source") or {}
    return {
        "available": bool(normalized),
        "identification_engine": normalized.get("identification_engine") or "Siegfried / PRONOM",
        "statistics": {
            "row_count": len(rows),
            "total_files": total_files,
            "unique_format_ids": len(format_ids),
            "format_ids": sorted(format_ids, key=str.casefold),
            "unidentified_files": unidentified_files,
            "raf_220301_counts": raf_counts,
            "fieldnames": list(csv_model.get("fieldnames") or []),
            "rows": presentation_rows,
            "source": {
                "original_name": source.get("original_name"),
                "original_path": source.get("original_path"),
                "preserved_file": source.get("preserved_file"),
                "sha256": source.get("sha256"),
                "size_bytes": source.get("size_bytes"),
            },
        },
        "detailed_file_inventory": {
            "found": bool(detailed.get("found")),
            "imported": bool(detailed.get("imported")),
            "original_name": detailed.get("original_name"),
            "original_path": detailed.get("original_path"),
            "size_bytes": detailed.get("size_bytes"),
            "policy": detailed.get("policy"),
        },
    }
