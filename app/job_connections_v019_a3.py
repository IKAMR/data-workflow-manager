"""v0.1.9-a3: safe, GUI-neutral job-list location inspection and reconnection.

Work is authoritative; .n5jobs is only an index.  Scans are deliberately
limited to one known job.json per job and explicitly selected candidate paths.
No Source/DOKUMENT enumeration, implicit relocation, copying or folder creation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.application_api import DwmApiError
from app.work_persistence_v018_a10 import _path_overlap
from noark5_workflow.core.work_job_store import WorkJobStore, WorkJobStoreError

MAX_MANIFEST_BYTES = 4_000_000


@dataclass(frozen=True)
class JobLocationHealth:
    job_id: str
    job_uid: str
    work_label: str
    work_detail: str
    work_manifest: str
    source_label: str
    source_path: str
    last_known_status: str


@dataclass(frozen=True)
class WorkLinkPreview:
    job_id: str
    job_uid: str
    previous_manifest: Path
    selected_manifest: Path
    manifest_sha256: str
    state_sha256: str
    work_operations_before: str
    work_operations_after: str
    status: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class SourceLinkPreview:
    job_id: str
    job_uid: str
    previous_source: str
    selected_source: Path
    info_check: str
    info_sha256: str
    warnings: tuple[str, ...]
    updates: tuple[tuple[str, str], ...]


def _manifest_path(value: str | Path) -> Path:
    candidate = Path(value)
    if candidate.name == "job.json":
        candidate = candidate.parent
    try:
        root = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise DwmApiError("Work-mappen finnes ikke eller er frakoblet: " + str(exc)) from exc
    if not root.is_dir():
        raise DwmApiError("Velg DWM Work-mappen som inneholder job.json.")
    manifest = root / "job.json"
    if not manifest.is_file():
        raise DwmApiError("Valgt mappe inneholder ikke en DWM job.json.")
    for filename in ("job.json", "job-state.json", "job-events.jsonl"):
        item = root / filename
        if item.exists() and not item.resolve(strict=True).is_relative_to(root):
            raise DwmApiError("Work-filen peker utenfor det valgte Work-området: " + filename)
    return manifest


def _hash_checked(path: Path, *, max_bytes: int = MAX_MANIFEST_BYTES) -> str:
    try:
        if not path.is_file():
            return ""
        if not path.resolve(strict=True).is_relative_to(path.parent.resolve(strict=True)):
            raise DwmApiError("Filen peker utenfor valgt område: " + str(path))
        if path.stat().st_size > max_bytes:
            raise DwmApiError("Jobbmanifestet er større enn tillatt kontrollgrense.")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError as exc:
        raise DwmApiError("Kunne ikke kontrollere Work-filen: " + str(exc)) from exc


def _read_uid(path: Path) -> str:
    """Read only a bounded manifest, not the event stream or extraction."""
    _hash_checked(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise DwmApiError("Ugyldig jobbmanifest i Work: " + str(exc)) from exc
    if (not isinstance(data, dict) or data.get("file_type") != "dwm-work-job"
            or data.get("format_version") != 1 or not isinstance(data.get("job"), dict)):
        raise DwmApiError("Dette er ikke et støttet DWM-jobbmanifest.")
    return str(data.get("job_uid") or "")


def _same_path(a: Path, b: Path) -> bool:
    try:
        if a.exists() and b.exists():
            return a.samefile(b)
        return a.resolve(strict=False) == b.resolve(strict=False)
    except (OSError, ValueError, RuntimeError):
        return False


def inspect_job_locations(api) -> tuple[JobLocationHealth, ...]:
    """Fresh read-only statuses. An old .n5jobs status is never current proof."""
    view = api.workspace()
    results = []
    for job in view.jobs:
        info = api.work_job_info(job.job_id)
        uid = str(info.get("job_uid") or "")
        ref_raw = str(info.get("work_manifest") or "")
        source = str(job.source_extraction or job.source_root or "")
        if not source:
            source_label = "Ukjent" if ref_raw else "Ikke angitt"
        else:
            try:
                source_label = "Tilgjengelig" if Path(source).is_dir() else "Frakoblet"
            except (OSError, ValueError):
                source_label = "Frakoblet"
        if not ref_raw:
            label = "Utkast"
            detail = "Jobben er ikke registrert som autoritativ i Work."
        else:
            ref = Path(ref_raw)
            if not ref.is_file():
                label = "Frakoblet"
                detail = "Work er ikke tilgjengelig. Jobblisten viser kun sist kjente status."
            else:
                try:
                    actual_uid = _read_uid(ref)
                    if not uid or actual_uid != uid:
                        label = "ID-konflikt"
                        detail = "Work har en annen varig jobb-ID. Ingen endringer er gjort."
                    elif job.job_id in getattr(api, "_unavailable_work_ids", ()):  # stale offline snapshot
                        label = "Gjenåpne"
                        detail = "Work er tilbake, men jobben har fortsatt offline-status. Koble til på nytt."
                    else:
                        label = "Tilkoblet"
                        detail = "Work-manifest og jobblistens varige ID stemmer."
                except DwmApiError as exc:
                    label = "Ugyldig"
                    detail = str(exc)
        results.append(JobLocationHealth(
            job.job_id, uid, label, detail, ref_raw,
            source_label, source, job.status,
        ))
    return tuple(results)


def _suffix_after_base(old_root: Path, base: Path | None) -> Path | None:
    if base is None:
        return None
    try:
        return old_root.relative_to(Path(base))
    except (ValueError, OSError):
        return None


def _base_from_suffix(new_root: Path, suffix: Path) -> Path:
    parts = suffix.parts
    if not parts:
        return new_root
    if tuple(part.casefold() for part in new_root.parts[-len(parts):]) != tuple(
            part.casefold() for part in parts):
        raise DwmApiError(
            "Work-mappens interne struktur er endret. Velg den samme DWM-undermappen "
            "som før, eller gjennomfør en separat kontrollert migrering."
        )
    return new_root.parents[len(parts) - 1]


def _inspect_work_link(api, job_id: str, selected: str | Path) -> WorkLinkPreview:
    current = api._require_job(job_id)
    original_ref = api._work_references.get(job_id)
    if original_ref is None:
        raise DwmApiError("Dette er en jobbliste uten Work-referanse. Bruk «Åpne jobb fra Work». ")
    expected = str(getattr(current, "job_uid", "") or "")
    if not expected:
        raise DwmApiError("Jobblisten mangler varig Work-ID. Kan ikke koble om automatisk.")
    selected_ref = _manifest_path(selected)
    actual = _read_uid(selected_ref)
    if actual != expected:
        raise DwmApiError(
            "Feil Work-jobb: varig jobb-ID stemmer ikke med " + job_id
            + ". Ingen referanser er endret."
        )
    for other_id, other_ref in api._work_references.items():
        if other_id != job_id and _same_path(selected_ref, Path(other_ref)):
            raise DwmApiError("Work-mappen er allerede knyttet til " + other_id)
    try:
        recovered = WorkJobStore(selected_ref.parent).load()
    except (OSError, WorkJobStoreError) as exc:
        raise DwmApiError("Work kan ikke gjenopprettes: " + str(exc)) from exc
    if str(recovered.job_uid) != expected:
        raise DwmApiError("Work-status og jobbmanifest har forskjellig ID.")
    if str(recovered.profile_id or "") != str(current.profile_id or ""):
        raise DwmApiError("Work-profil stemmer ikke med jobblistens profil.")
    if any(str(getattr(job, "job_uid", "") or "") == expected and job.job_id != job_id
           for job in api._batch.jobs()):
        raise DwmApiError("En annen jobb i listen har samme varige Work-ID.")
    for field in ("source_root", "source_tar", "source_unzipped", "source_extraction",
                  "archive_root", "output_root"):
        if _path_overlap(selected_ref.parent, getattr(recovered, field, None)):
            raise DwmApiError("Work-mappen overlapper Source eller AIP: " + field)
    old_root = Path(original_ref).parent
    different = not _same_path(old_root, selected_ref.parent)
    if different and Path(original_ref).is_file():
        raise DwmApiError(
            "Det opprinnelige Work-området er fremdeles tilgjengelig. "
            "Omkobling til en annen kopi ville forgrene samme jobbidentitet. "
            "Bruk kun denne funksjonen når den gamle plasseringen er frakoblet."
        )
    old_ops = recovered.work_operations
    warnings = []
    if different:
        suffix = _suffix_after_base(old_root, old_ops)
        if suffix is None:
            raise DwmApiError(
                "Kan ikke utlede ny Work – operations fra eksisterende jobbdata. "
                "Ingen automatisk flytting eller gjetting av lagringsroller."
            )
        new_ops = _base_from_suffix(selected_ref.parent, suffix)
        warnings.append("Kun Work – operations knyttes til ny plassering. "
                        "Work content, Source og AIP endres ikke.")
    else:
        new_ops = old_ops
    if new_ops is None:
        raise DwmApiError("Work mangler en entydig Work – operations-rolle.")
    return WorkLinkPreview(
        job_id, expected, Path(original_ref), selected_ref,
        _hash_checked(selected_ref),
        _hash_checked(selected_ref.with_name("job-state.json")),
        str(old_ops or ""), str(new_ops), recovered.status.value,
        tuple(warnings),
    )


def preview_work_link(api, job_id: str, selected: str | Path) -> WorkLinkPreview:
    with api._guard:
        api._assert_idle()
        return _inspect_work_link(api, job_id, selected)


def apply_work_link(api, preview: WorkLinkPreview, *, consent: bool = False):
    """Relink only matching Work UUID. Persist the new operations base if moved."""
    if not consent:
        raise DwmApiError("Omkobling krever uttrykkelig godkjenning.")
    with api._guard:
        api._assert_idle()
        current = _inspect_work_link(api, preview.job_id, preview.selected_manifest)
        if current != preview:
            raise DwmApiError("Work er endret etter forhåndsvisningen. Kontroller på nytt.")
        store = WorkJobStore(preview.selected_manifest.parent)
        try:
            job = store.load()
        except (OSError, WorkJobStoreError) as exc:
            raise DwmApiError("Work-status kunne ikke leses: " + str(exc)) from exc
        job.job_id = preview.job_id  # local job-list identity; never change job_uid
        moved = preview.work_operations_after != preview.work_operations_before
        if moved:
            job.work_operations = Path(preview.work_operations_after)
            try:
                store.write(
                    job, event_kind="work.path_relinked",
                    detail="Work – operations koblet til " + str(preview.selected_manifest.parent),
                    origin_joblist=str(api._path or ""),
                )
            except (OSError, WorkJobStoreError) as exc:
                raise DwmApiError("Kunne ikke lagre ny Work-plassering: " + str(exc)) from exc
        # Update the index only in memory. The user explicitly saves .n5jobs.
        jobs = api._batch.jobs()
        jobs = [job if candidate.job_id == preview.job_id else candidate for candidate in jobs]
        api._batch.replace_all(jobs)
        api._work_references[preview.job_id] = store.definition_path
        api._unavailable_work_ids = frozenset(set(api._unavailable_work_ids) - {preview.job_id})
        api._active_job_id = preview.job_id
        api._dirty = True
        position = next(i for i, item in enumerate(jobs, 1) if item.job_id == preview.job_id)
        result = api._view(job, position)
    api._emit("job.work_relinked", job, message=str(preview.selected_manifest.parent))
    return result


def _inspect_source_link(api, job_id: str, selected: str | Path) -> SourceLinkPreview:
    job = api._require_job(job_id)
    if job_id in api._unavailable_work_ids:
        raise DwmApiError("Koble først til autoritativ Work; Source kan ikke endres fra offline-utdraget.")
    active = job.source_extraction or job.source_root
    if active is None:
        raise DwmApiError("Jobben har ingen tidligere Source-sti. Bruk Lagring for å konfigurere den.")
    candidate = Path(selected)
    try:
        candidate = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise DwmApiError("Uttrekksmappen finnes ikke: " + str(exc)) from exc
    if not candidate.is_dir():
        raise DwmApiError("Velg en eksisterende mappe for uttrekket.")
    for field in ("work_root", "work_content", "work_operations", "archive_root", "output_root"):
        if _path_overlap(candidate, getattr(job, field, None)):
            raise DwmApiError("Source kan ikke overlappe Work eller AIP: " + field)
    ref = api._work_references.get(job_id)
    if ref is not None and _path_overlap(candidate, Path(ref).parent):
        raise DwmApiError("Source kan ikke overlappe autoritativ Work.")
    # Never deduce an extraction identity merely from the directory name.
    old_info = Path(active) / "info.xml"
    new_info = candidate / "info.xml"
    info_check = "Ikke sammenlignbar"
    info_sha256 = _hash_checked(new_info, max_bytes=32_000_000) if new_info.is_file() else ""
    warnings = ["Uttrekkets identitet er ikke bevist av mappenavnet. "
                "Bekreft manuelt at dette er det samme uttrekket."]
    if old_info.is_file() and new_info.is_file():
        if _hash_checked(old_info, max_bytes=32_000_000) != info_sha256:
            raise DwmApiError("info.xml er ulik den tidligere kilden. Omkobling stoppet.")
        info_check = "info.xml samsvarer (SHA-256)"
        warnings = ["info.xml samsvarer, men dette verifiserer ikke alle datafiler. "
                    "Kontroller fortsatt at dette er samme uttrekk."]
    elif str(job.profile_id or "").lower() == "noark5" and not new_info.is_file():
        warnings.append("info.xml finnes ikke på toppnivået. Kontroller uttrekksstrukturen før kjøring.")
    updates = {"source_extraction": str(candidate)}
    for role in ("source_root", "source_unzipped"):
        original = getattr(job, role, None)
        if original is not None and _same_path(Path(original), Path(active)):
            updates[role] = str(candidate)
    return SourceLinkPreview(
        job_id, str(getattr(job, "job_uid", "") or ""), str(active), candidate,
        info_check, info_sha256, tuple(warnings), tuple(sorted(updates.items())),
    )


def preview_source_link(api, job_id: str, selected: str | Path) -> SourceLinkPreview:
    with api._guard:
        api._assert_idle()
        return _inspect_source_link(api, job_id, selected)


def apply_source_link(api, preview: SourceLinkPreview, *, consent: bool = False):
    if not consent:
        raise DwmApiError("Omkobling av Source krever uttrykkelig godkjenning.")
    with api._guard:
        api._assert_idle()
        current = _inspect_source_link(api, preview.job_id, preview.selected_source)
        if current != preview:
            raise DwmApiError("Source eller jobben er endret etter forhåndsvisningen.")
    # The original API handles Work persistence and immutable job identity.
    return api.update_storage(preview.job_id, dict(preview.updates))
