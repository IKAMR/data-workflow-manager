"""v0.1.9-a4: explicit, portable storage-root rebasing for DWM jobs.

A job owns independent Source, Work and AIP roles. A root mapping is an
operator-approved translation of paths *inside one selected root*, never a
blind string replacement or an automatic archive relocation. All previews are
read-only, even if the old disk is disconnected. Runtime role paths remain
absolute for compatibility; the supplementary storage-roots.json records
root-relative role bindings for later relocation and audit.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from typing import Any
from uuid import uuid4

from app.application_api import DwmApiError
from app.job_connections_v019_a3 import WorkLinkPreview, preview_work_link, apply_work_link
from app.work_persistence_v018_a10 import _path_overlap
from noark5_workflow.core.work_job_store import WorkJobStore, WorkJobStoreError

ROLE_FIELDS = (
    "source_root", "source_tar", "source_unzipped", "source_extraction",
    "work_root", "work_content", "work_operations", "archive_root", "output_root",
)
INPUT_ROLES = frozenset({"source_tar", "source_unzipped", "source_extraction"})
PORTABLE_FILE = "storage-roots.json"
PORTABLE_FILE_TYPE = "dwm-storage-root-bindings"
PORTABLE_VERSION = 1
MAX_PORTABLE_BYTES = 1_000_000
MAX_INFO_BYTES = 32_000_000
_WINDOWS = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\[^\\]+\\[^\\]+(?:\\|$))")


@dataclass(frozen=True)
class RebasedRole:
    field: str
    before: str
    after: str
    relative: str
    exists: bool
    note: str


@dataclass(frozen=True)
class JobRootRebase:
    job_id: str
    job_uid: str
    name: str
    work_manifest_before: str
    work_manifest_after: str
    work_preview: WorkLinkPreview | None
    roles: tuple[RebasedRole, ...]
    source_info_sha256: str
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class RootRebasePlan:
    old_root: str
    new_root: str
    jobs: tuple[JobRootRebase, ...]

    @property
    def errors(self) -> tuple[str, ...]:
        return tuple(f"{job.job_id}: {error}" for job in self.jobs for error in job.errors)

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(f"{job.job_id}: {warning}" for job in self.jobs for warning in job.warnings)

    @property
    def role_count(self) -> int:
        return sum(len(job.roles) for job in self.jobs)


def _pure(value: str | Path):
    value = str(value).strip()
    if not value:
        raise DwmApiError("Rotmappe eller lagringssti er tom.")
    if "\x00" in value:
        raise DwmApiError("Ugyldig tegn i lagringssti.")
    cls = PureWindowsPath if _WINDOWS.match(value) else PurePosixPath
    path = cls(value)
    if not path.is_absolute() or ".." in path.parts:
        raise DwmApiError("Velg en absolutt mappe uten '..'-segmenter: " + value)
    return path


def _windows_canonical(path: PureWindowsPath) -> PureWindowsPath | None:
    """Normalize Win32 8.3 aliases even when the final directory is offline.

    Resolving with strict=False expands a still-existing short-name ancestor
    (e.g. TORBJO~1.AAS -> torbjorn.aasen) and leaves the missing suffix intact.
    The source root is NOT scanned and a missing drive is NOT guessed.  On
    non-Windows hosts, Windows paths are kept purely lexical.
    """
    if os.name != "nt":
        return None
    try:
        return PureWindowsPath(Path(str(path)).resolve(strict=False))
    except (OSError, ValueError, RuntimeError):
        return None


def rebase_storage_path(value: str | Path | None, old_root: str | Path,
                        new_root: str | Path) -> tuple[str, str] | None:
    """Return target and portable relative suffix for a path inside old_root.

    Works with disconnected Windows drives on both Windows and Linux; it never
    accesses the old path and never treats D:\\foo as prefix of D:\\foobar.
    """
    if not value:
        return None
    old = _pure(old_root)
    new = _pure(new_root)
    current = _pure(value)
    if type(old) is not type(new) or type(old) is not type(current):
        raise DwmApiError("Begge røtter og tilhørende stier må bruke samme stitype.")
    try:
        suffix = current.relative_to(old)
    except ValueError:
        # After the first root move, a3 stores a canonical Work reference.
        # Windows may expand an 8.3 alias in that reference while the user's
        # old root (or tempfile root) still contains the short 8.3 spelling.
        # The old Work directory can already have been moved away, so only
        # its *existing ancestors* can be resolved. Keep the requested target
        # root spelling; canonicalization is for containment comparison only.
        if not isinstance(old, PureWindowsPath):
            return None
        canonical_old = _windows_canonical(old)
        canonical_current = _windows_canonical(current)
        if canonical_old is None or canonical_current is None:
            return None
        try:
            suffix = canonical_current.relative_to(canonical_old)
        except ValueError:
            return None
    target = new.joinpath(*suffix.parts)
    return str(target), suffix.as_posix() if suffix.parts else "."


def _roots(old_root: str | Path, new_root: str | Path) -> tuple[str, str]:
    old, new = _pure(old_root), _pure(new_root)
    if type(old) is not type(new):
        raise DwmApiError("Kan ikke bytte mellom Windows- og Unix-stier.")
    if old == new:
        raise DwmApiError("Gammel og ny rotmappe er den samme.")
    # Do not allow a broad old root to map into its own subtree.
    if new.is_relative_to(old) or old.is_relative_to(new):
        raise DwmApiError("Gammel og ny rot kan ikke ligge inne i hverandre.")
    if not Path(str(new)).is_dir():
        raise DwmApiError("Den nye rotmappen må finnes før omkobling: " + str(new))
    return str(old), str(new)


def _sha256_small(path: Path, limit: int = MAX_INFO_BYTES) -> str:
    try:
        if not path.is_file():
            return ""
        if path.stat().st_size > limit:
            raise DwmApiError("Filen er for stor for sikker metadatakontroll: " + str(path))
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError as exc:
        raise DwmApiError("Kunne ikke lese metadatafil: " + str(exc)) from exc


def _safe_target(path: Path, new_root: Path) -> bool:
    """Existing target path must remain inside selected physical root."""
    try:
        return path.resolve(strict=True).is_relative_to(new_root.resolve(strict=True))
    except (OSError, ValueError, RuntimeError):
        return False


def _manifest_owner(path: Path, uid: str) -> None:
    if not path.is_file():
        return
    try:
        # A planted symlink must not read metadata outside this Work area.
        if not path.resolve(strict=True).is_relative_to(path.parent.resolve(strict=True)):
            raise DwmApiError("Lagringsrot-oversikten peker utenfor Work.")
        if path.stat().st_size > MAX_PORTABLE_BYTES:
            raise DwmApiError("Lagringsrot-oversikten i Work er for stor.")
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        if (not isinstance(document, dict) or document.get("file_type") != PORTABLE_FILE_TYPE
                or document.get("format_version") != PORTABLE_VERSION
                or document.get("job_uid") != uid
                or not isinstance(document.get("roots"), list)
                or any(not isinstance(entry, dict) for entry in document["roots"])):
            raise DwmApiError("Lagringsrot-oversikten i Work har feil format eller jobb-ID.")
    except (OSError, UnicodeError, ValueError) as exc:
        raise DwmApiError("Kunne ikke lese lagringsrot-oversikt: " + str(exc)) from exc


def _job_record(api, job_id: str, old: str, new: str) -> JobRootRebase | None:
    cached = api._require_job(job_id)
    ref = api._work_references.get(job_id)
    work_preview = None
    errors: list[str] = []
    warnings: list[str] = []
    ref_after = str(ref or "")
    work_changed = None

    if ref:
        work_changed = rebase_storage_path(ref, old, new)
        if work_changed:
            ref_after = work_changed[0]
            try:
                work_preview = preview_work_link(api, job_id, Path(ref_after).parent)
            except (DwmApiError, OSError, WorkJobStoreError, ValueError) as exc:
                errors.append("Work-omkobling blokkert: " + str(exc))
                # The Work job may still be readable at new root, so retain
                # its complete roles for a meaningful read-only diagnosis.
        elif job_id in api._unavailable_work_ids or not Path(ref).is_file():
            errors.append("Autoritativ Work er frakoblet utenfor valgt rot. Koble til Work først.")
        if Path(ref_after).is_file():
            try:
                job = WorkJobStore(Path(ref_after).parent).load()
                if job.job_uid != cached.job_uid:
                    errors.append("Varig Work-ID stemmer ikke med jobblisten.")
                if str(job.profile_id or "") != str(cached.profile_id or ""):
                    errors.append("Profilen i Work avviker fra jobblisten.")
                job.job_id = job_id
                _manifest_owner(Path(ref_after).with_name(PORTABLE_FILE), cached.job_uid)
            except (OSError, WorkJobStoreError, DwmApiError) as exc:
                errors.append("Kan ikke lese Work-jobben: " + str(exc))
                job = cached
        else:
            job = cached
    else:
        job = cached  # Drafts remain authoritative in the .n5jobs index.

    roles: list[RebasedRole] = []
    for field in ROLE_FIELDS:
        value = getattr(job, field, None)
        if not value:
            continue
        try:
            changed = rebase_storage_path(value, old, new)
        except DwmApiError as exc:
            errors.append(field + ": " + str(exc))
            continue
        if not changed:
            continue
        target, rel = changed
        candidate = Path(target)
        exists = candidate.exists()
        note = "Finnes" if exists else "Mangler – opprettes ikke av a4"
        if exists and not _safe_target(candidate, Path(new)):
            errors.append(field + ": ny sti peker utenfor valgt rot via en lenke.")
        if field in ("source_extraction", "source_root") and not candidate.is_dir() and (
                field == "source_extraction" or not getattr(job, "source_extraction", None)):
            errors.append("Aktivt Source-uttrekk finnes ikke på ny plassering: " + target)
        elif field == "source_tar" and not exists:
            warnings.append("Kildearkivet (source_tar) finnes ikke på ny plassering.")
        elif not exists:
            warnings.append(field + " er ikke tilgjengelig på ny plassering; ingen mappe opprettes.")
        roles.append(RebasedRole(field, str(value), target, rel, exists, note))

    if ref and work_changed and not Path(ref_after).is_file():
        errors.append("Work-manifestet finnes ikke under den nye rotmappen.")

    # Check the actual extraction root (not the AIC/package root, which may
    # legitimately contain both Source and Work subdirectories).
    after_roles = {row.field: Path(row.after) for row in roles}
    effective_source = after_roles.get("source_extraction") or (
        Path(job.source_extraction) if job.source_extraction else None
    ) or after_roles.get("source_root") or (
        Path(job.source_root) if job.source_root else None
    )
    effective_work = Path(ref_after).parent if ref_after else (
        after_roles.get("work_operations") or
        (Path(job.work_operations) if job.work_operations else None)
    )
    effective_aip = after_roles.get("archive_root") or (
        Path(job.archive_root) if job.archive_root else None
    )
    if effective_work is not None:
        for label, candidate in (("Source extraction", effective_source),
                                 ("AIP", effective_aip)):
            if candidate is not None and _path_overlap(effective_work, candidate):
                errors.append(label + " overlapper Work etter omkoblingen.")

    # A matching top-level info.xml is evidence, never proof that an entire
    # extraction is identical. Refuse demonstrably different metadata.
    info_digest = ""
    new_source = next((Path(row.after) for row in roles if row.field == "source_extraction"), None)
    if new_source is None and not getattr(job, "source_extraction", None):
        new_source = next((Path(row.after) for row in roles if row.field == "source_root"), None)
    if new_source is not None and new_source.is_dir():
        new_info = new_source / "info.xml"
        old_source = Path(str(job.source_extraction or job.source_root or ""))
        old_info = old_source / "info.xml"
        try:
            info_digest = _sha256_small(new_info)
            old_digest = _sha256_small(old_info)
            if old_digest and info_digest and old_digest != info_digest:
                errors.append("info.xml er ulik på gammel og ny Source. Avbryter omkobling.")
            elif old_digest and not info_digest:
                errors.append("Tidligere Source har info.xml, men den nye mangler den.")
            elif not old_digest or not info_digest:
                warnings.append("Source-identitet kan ikke verifiseres med info.xml; manuell kontroll kreves.")
            else:
                warnings.append("info.xml samsvarer, men øvrige uttrekksfiler er ikke kontrollert.")
        except DwmApiError as exc:
            errors.append(str(exc))

    if not roles and not work_changed:
        return None
    if not ref:
        warnings.append("Utkast: endringene lagres i .n5jobs inntil Work er klargjort.")
    else:
        warnings.append("Work er autoritativ; jobblisten må lagres etter omkoblingen.")
    return JobRootRebase(job_id, str(getattr(cached, "job_uid", "") or ""),
                         str(cached.name), str(ref or ""), ref_after,
                         work_preview, tuple(roles), info_digest,
                         tuple(dict.fromkeys(errors)), tuple(dict.fromkeys(warnings)))


def preview_root_rebase(api, old_root: str | Path, new_root: str | Path) -> RootRebasePlan:
    """Read-only. No recursion over Source, DOKUMENT, AIP or unknown drives."""
    old, new = _roots(old_root, new_root)
    with api._guard:
        api._assert_idle()
        ids = [job.job_id for job in api._batch.jobs()]
    jobs = []
    for job_id in ids:
        record = _job_record(api, job_id, old, new)
        if record:
            jobs.append(record)
    # A batch must not point two independent Work jobs at one target manifest.
    # Detect the collision before *any* job is written, not after a partial run.
    targets = {}
    validated = []
    for record in jobs:
        new_ref = record.work_manifest_after
        if new_ref:
            try:
                key = str(Path(new_ref).resolve(strict=False)).casefold()
            except (OSError, ValueError, RuntimeError):
                key = new_ref.casefold()
            other = targets.get(key)
            if other is not None and other != record.job_id:
                record = replace(record, errors=record.errors + (
                    "To jobber ville peke til samme Work-manifest: " + other,
                ))
            else:
                targets[key] = record.job_id
        validated.append(record)
    return RootRebasePlan(old, new, tuple(validated))


def _same_location(a: str | Path | None, b: str | Path | None) -> bool:
    """Handle Win32 8.3 aliases, junctions and UNC case without text comparison."""
    if not a or not b:
        return a == b
    first, second = Path(a), Path(b)
    try:
        if first.exists() and second.exists():
            return first.samefile(second)
        return first.resolve(strict=False) == second.resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return False


def _commit_roles(api, plan: JobRootRebase) -> None:
    """One job is persisted to canonical Work *before* its in-memory swap.

    This deliberately handles legacy output_root as well as all modern roles;
    the public update_storage API currently omits output_root for historical
    GUI compatibility. It never mutates source files or job execution state.
    """
    with api._guard:
        api._assert_idle()
        current = api._require_job(plan.job_id)
        if str(getattr(current, "job_uid", "") or "") != plan.job_uid:
            raise DwmApiError("Varig jobb-ID endret etter forhåndsvisning.")
        next_job = deepcopy(current)
        for row in plan.roles:
            current_path = getattr(next_job, row.field, None)
            # Work operations may already have been updated by the a3 relink.
            if not (_same_location(current_path, row.before)
                    or _same_location(current_path, row.after)):
                raise DwmApiError("Lagringsrollen " + row.field + " er endret siden forhåndsvisningen.")
            setattr(next_job, row.field, Path(row.after))
        ref = api._work_references.get(plan.job_id)
        if ref:
            if not ref.is_file() or plan.job_id in api._unavailable_work_ids:
                raise DwmApiError("Autoritativ Work er frakoblet. Rollen kan ikke oppdateres.")
            try:
                store = WorkJobStore(ref.parent)
                store.write(next_job, event_kind="storage.root_rebased",
                            detail="Kontrollert rotomkobling", origin_joblist=str(api._path or ""))
            except (OSError, WorkJobStoreError) as exc:
                raise DwmApiError("Kunne ikke lagre nye roller i Work: " + str(exc)) from exc
        jobs = [next_job if item.job_id == plan.job_id else item for item in api._batch.jobs()]
        api._batch.replace_all(jobs)
        api._dirty = True
    api._emit("job.storage_root_rebased", next_job, message=plan.job_id)


def _write_portable_manifest(api, item: JobRootRebase, old: str, new: str) -> None:
    ref = api._work_references.get(item.job_id)
    if ref is None:
        return  # Drafts do not have a Work-owned metadata location yet.
    root = ref.parent.resolve(strict=True)
    if not root.is_dir() or not ref.is_file():
        raise DwmApiError("Work er ikke tilgjengelig for lagring av relative lagringsstier.")
    output = root / PORTABLE_FILE
    _manifest_owner(output, item.job_uid)
    document: dict[str, Any] = {
        "file_type": PORTABLE_FILE_TYPE, "format_version": PORTABLE_VERSION,
        "job_uid": item.job_uid, "roots": [],
    }
    if output.is_file():
        document = json.loads(output.read_text(encoding="utf-8-sig"))
    existing = [row for row in document.get("roots", [])
                if isinstance(row, dict) and row.get("original_root") != old]
    existing.append({
        "original_root": old, "current_root": new,
        "roles": {row.field: {"relative": row.relative, "resolved": row.after}
                  for row in item.roles},
        "work_manifest_relative": (
            rebase_storage_path(item.work_manifest_before, old, new) or ("", "")
        )[1] if item.work_manifest_before else "",
    })
    document["roots"] = existing[-12:]
    temp = output.with_name("." + output.name + "." + uuid4().hex + ".tmp")
    try:
        with temp.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(document, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, output)
    finally:
        if temp.exists():
            temp.unlink()


def apply_root_rebase(api, plan: RootRebasePlan, *, consent: bool = False) -> tuple[str, ...]:
    """Apply one confirmed, fully rechecked plan. Never promise batch atomicity.

    A Work move is performed first via a3's UUID-verified relink. Other roles
    follow in a per-job Work write. Failure stops immediately; earlier jobs
    remain committed and can be inspected/recovered before another attempt.
    """
    if not consent:
        raise DwmApiError("Rotomkobling krever uttrykkelig godkjenning.")
    if not plan.jobs:
        raise DwmApiError("Ingen lagringsstier ligger under den valgte roten.")
    if plan.errors:
        raise DwmApiError("Rotomkobling blokkert:\n" + "\n".join(plan.errors))
    fresh = preview_root_rebase(api, plan.old_root, plan.new_root)
    if fresh != plan:
        raise DwmApiError("Stier eller Work-status er endret etter forhåndsvisningen. Kontroller på nytt.")
    completed: list[str] = []
    for item in plan.jobs:
        try:
            if item.work_preview is not None:
                apply_work_link(api, item.work_preview, consent=True)
            if item.roles:
                _commit_roles(api, item)
            _write_portable_manifest(api, item, plan.old_root, plan.new_root)
        except Exception as exc:
            done = ", ".join(completed) if completed else "Ingen"
            raise DwmApiError(
                f"Omkobling stoppet ved {item.job_id}: {exc}. "
                f"Allerede oppdaterte jobber: {done}. "
                "Kontroller disse i Work og lagre jobblisten før ny forhåndsvisning."
            ) from exc
        completed.append(item.job_id)
    return tuple(completed)
