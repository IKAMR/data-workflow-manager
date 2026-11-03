"""Explicit, side-effect-free preflight planning for DWM v0.1.8-a6.

Source is NEVER generated or guessed into the execution role. Work folders may
be proposed, but callers must obtain consent and call the separate provision
command. This module does not import any GUI implementation or inspect payload
folders recursively.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


NOARK5_MARKERS = frozenset({
    "arkivstruktur.xml", "arkivuttrekk.xml", "arkivstruktur.tar",
})


@dataclass(frozen=True)
class PreflightIssue:
    code: str
    level: str   # 'error' or 'warning'
    message: str


@dataclass(frozen=True)
class PreflightAction:
    kind: str    # 'set_work_operations' or 'mkdir'
    path: str
    description: str


@dataclass(frozen=True)
class PreflightReport:
    job_id: str
    issues: tuple[PreflightIssue, ...]
    actions: tuple[PreflightAction, ...]

    @property
    def errors(self) -> tuple[PreflightIssue, ...]:
        return tuple(item for item in self.issues if item.level == "error")

    @property
    def warnings(self) -> tuple[PreflightIssue, ...]:
        return tuple(item for item in self.issues if item.level == "warning")

    @property
    def ready(self) -> bool:
        # Warnings require an explicit user acknowledgement before execution.
        return not self.errors and not self.actions and not self.warnings


@dataclass(frozen=True)
class WorkLocationProposal:
    """Interpret a user's directory without duplicating standard Work levels."""
    selected: Path
    work_root: Path
    work_operations: Path
    selected_role: str


def propose_work_location(
    selected: str | Path, *, app_subfolder: str = "dwm",
) -> WorkLocationProposal:
    """Accept Work root, repository_operations, dwm or a job folder.

    This is a READ-ONLY suggestion, never creates folders or changes a job.
    Unknown subfolders inside repository_operations are rejected rather than
    interpreting them as new Work roots and creating duplicated directories.
    """
    chosen = Path(selected)
    if not str(chosen).strip() or str(chosen) == ".":
        raise ValueError("Velg en eksisterende Work-mappe.")
    repository = next(
        (part for part in (chosen, *chosen.parents)
         if part.name.casefold() == "repository_operations"),
        None,
    )
    if repository is None:
        return WorkLocationProposal(
            chosen, chosen, chosen / "repository_operations", "work_root",
        )

    relative = chosen.relative_to(repository).parts
    app_name = str(app_subfolder or "").strip()
    if not relative:
        role = "work_operations"
    elif app_name and relative[0].casefold() == app_name.casefold():
        role = "app_subfolder" if len(relative) == 1 else "job_subfolder"
    else:
        raise ValueError(
            "Valgt mappe ligger inne i repository_operations, men er ikke "
            "den konfigurerte DWM-undermappen. Velg Work-hovedmappen, "
            "repository_operations eller DWM-undermappen direkte: " + str(chosen)
        )
    return WorkLocationProposal(chosen, repository.parent, repository, role)


def _path(value) -> Path | None:
    return Path(value) if value else None


def _within(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def source_marker_names(directory: Path) -> frozenset[str]:
    """Read only the selected folder's immediate names (never DOKUMENT)."""
    with os.scandir(directory) as entries:
        return frozenset(item.name.casefold() for item in entries)


def check_extraction_folder(path: str | Path, *, profile_id: str = "noark5") -> tuple[PreflightIssue, ...]:
    source = Path(path)
    if not source.is_dir():
        return (PreflightIssue(
            "SOURCE_NOT_FOUND", "error",
            f"Source – uttrekk er ikke tilgjengelig som mappe: {source}",
        ),)
    try:
        names = source_marker_names(source)
    except OSError as exc:
        return (PreflightIssue(
            "SOURCE_NOT_READABLE", "error",
            f"Kan ikke lese Source – uttrekk: {source} ({exc})",
        ),)

    if profile_id.casefold() == "noark5" and not (names & NOARK5_MARKERS):
        hint = ""
        for child in (source / "uttrekk", source / "content" / "uttrekk"):
            try:
                if child.is_dir() and source_marker_names(child) & NOARK5_MARKERS:
                    hint = f" Mulig riktig uttrekksmappe: {child}."
                    break
            except OSError:
                pass
        return (PreflightIssue(
            "NOARK5_MARKER_NOT_FOUND", "error",
            "Valgt Source – uttrekk mangler Noark 5-kjennetegn "
            "(arkivstruktur.xml / arkivuttrekk.xml / arkivstruktur.tar). "
            "Velg mappen med selve uttrekket."
            + hint,
        ),)
    return ()


def inspect_job(job, *, effective_work_operations: str | Path | None,
                app_subfolder: str = "dwm") -> PreflightReport:
    """Build a deterministic, read-only plan. No mkdir, no job mutation.

    Work root is a suggestion source only.  A missing Work operations role can
    be assigned from an explicitly chosen Work root *after* confirmation.
    """
    issues: list[PreflightIssue] = []
    actions: list[PreflightAction] = []
    job_id = str(getattr(job, "job_id", "") or "")

    def issue(code: str, level: str, message: str) -> None:
        issues.append(PreflightIssue(code, level, message))

    extraction = _path(getattr(job, "source_extraction", None))
    unpacked = _path(getattr(job, "source_unzipped", None))
    root = _path(getattr(job, "source_root", None))
    if extraction is None:
        if unpacked is not None:
            issue(
                "EXTRACTION_ROLE_MISSING", "error",
                "Source – uttrekk (fjerde mappefelt) mangler. "
                f"Du har valgt Source – utpakket: {unpacked}. "
                "Dette feltet er ikke uttrekksmappen. Velg riktig mappe i Source – uttrekk.",
            )
        else:
            issue(
                "EXTRACTION_ROLE_MISSING", "error",
                "Source – uttrekk må angis eksplisitt. "
                + (f"Source – hovedmappe ({root}) er ikke nok." if root else "Velg mappen som inneholder uttrekket."),
            )
    else:
        if not extraction.is_absolute():
            issue("RELATIVE_SOURCE", "error", f"Source – uttrekk må ha en absolutt sti: {extraction}")
        else:
            issues.extend(check_extraction_folder(extraction, profile_id=str(getattr(job, "profile_id", "") or "noark5")))

    # Optional Source roles are not silently used as a substitute for extraction.
    for label, path, kind in (
        ("Source – hovedmappe", root, "dir"),
        ("Source – utpakket", unpacked, "dir"),
        ("Source – TAR", _path(getattr(job, "source_tar", None)), "file"),
    ):
        if path is not None and not (path.is_file() if kind == "file" else path.is_dir()):
            issue("OPTIONAL_SOURCE_NOT_AVAILABLE", "warning", f"{label} er angitt, men ikke tilgjengelig: {path}")

    work_root = _path(getattr(job, "work_root", None))
    base = _path(getattr(job, "work_operations", None))
    effective = _path(effective_work_operations)

    if base is None and work_root is not None:
        try:
            proposal = propose_work_location(work_root, app_subfolder=app_subfolder)
        except ValueError as exc:
            issue("WORK_ROOT_AMBIGUOUS", "error", str(exc))
        else:
            base = proposal.work_operations
            issue("WORK_ROLE_PROPOSAL", "warning", f"Work – operations er ikke satt. Foreslått: {base}")
            actions.append(PreflightAction(
                "set_work_operations", str(base),
                "Sett Work – operations til foreslått mappe (endrer jobbens lagringsrolle)",
            ))
        # Existing API calculation returns None when work_operations is empty.
        # The caller must re-calculate the effective path after accepting the role.
    elif base is None:
        issue(
            "WORK_NOT_CONFIGURED", "error",
            "Work – operations er ikke valgt. Velg en Work-hovedmappe eller Work – operations. "
            "DWM kan deretter foreslå og opprette undermappene med din godkjenning.",
        )

    if base is not None:
        if not base.is_absolute():
            issue("RELATIVE_WORK", "error", f"Work – operations må ha en absolutt sti: {base}")
        if base.exists() and base.is_dir() and not os.access(base, os.W_OK):
            issue("WORK_NOT_WRITABLE", "error", f"Ingen skrivetilgang til Work – operations: {base}")
        if base.exists() and not base.is_dir():
            issue("WORK_IS_FILE", "error", f"Work – operations peker på en fil, ikke en mappe: {base}")
        if extraction is not None and (_within(base, extraction) or _within(extraction, base)):
            issue("SOURCE_WORK_OVERLAP", "error", f"Work – operations må ikke overlappe Source – uttrekk: {base}")
        if work_root is not None and work_root.exists() and not work_root.is_dir():
            issue("WORK_ROOT_IS_FILE", "error", f"Work – hovedmappe er ikke en mappe: {work_root}")
        if effective is not None:
            if extraction is not None and (_within(effective, extraction) or _within(extraction, effective)):
                issue("SOURCE_WORK_OVERLAP", "error", f"Effektiv Work-mappe overlapper Source – uttrekk: {effective}")
            if not effective.is_absolute():
                issue("RELATIVE_EFFECTIVE_WORK", "error", f"DWM-arbeidsområdet må ha en absolutt sti: {effective}")
            if effective.exists() and not effective.is_dir():
                issue("EFFECTIVE_WORK_IS_FILE", "error", f"DWM-arbeidsområdet peker på en fil: {effective}")
            elif effective.is_dir() and not os.access(effective, os.W_OK):
                issue("EFFECTIVE_WORK_NOT_WRITABLE", "error", f"Ingen skrivetilgang til DWM-arbeidsområdet: {effective}")
            elif not effective.exists():
                ancestor = effective
                while not ancestor.exists() and ancestor != ancestor.parent:
                    ancestor = ancestor.parent
                if ancestor.is_dir() and not os.access(ancestor, os.W_OK):
                    issue("WORK_PARENT_NOT_WRITABLE", "error", f"Ingen skrivetilgang til overordnet Work-mappe: {ancestor}")
                actions.append(PreflightAction(
                    "mkdir", str(effective),
                    "Opprett manglende Work – operations / dwm / jobb-undermappe (inkl. foreldre)",
                ))
        elif not base.exists():
            # Assigning work_operations first will yield the full effective path;
            # do not create an incomplete Work tree prematurely.
            pass

    # Work – content is an optional storage role, but when configured it must
    # be a real (or explicitly approved) directory outside the extraction.
    work_content = _path(getattr(job, "work_content", None))
    if work_content is not None:
        if not work_content.is_absolute():
            issue("RELATIVE_WORK_CONTENT", "error", f"Work – content må ha en absolutt sti: {work_content}")
        if extraction is not None and _within(work_content, extraction):
            issue("SOURCE_WORK_CONTENT_OVERLAP", "error", f"Work – content må ikke ligge i Source – uttrekk: {work_content}")
        if work_content.exists() and not work_content.is_dir():
            issue("WORK_CONTENT_IS_FILE", "error", f"Work – content peker på en fil: {work_content}")
        elif not work_content.exists():
            actions.append(PreflightAction("mkdir", str(work_content), "Opprett valgt Work – content-mappe"))

    archive = _path(getattr(job, "archive_root", None))
    if archive is not None and not archive.is_absolute():
        issue("RELATIVE_AIP", "error", f"AIP må ha en absolutt sti: {archive}")
    if archive is not None and extraction is not None and (_within(archive, extraction) or _within(extraction, archive)):
        issue("SOURCE_AIP_OVERLAP", "error", f"AIP må være adskilt fra Source – uttrekk: {archive}")
    if archive is not None and base is not None and (_within(archive, base) or _within(base, archive)):
        issue("AIP_WORK_OVERLAP", "error", f"AIP og Work – operations må ha adskilte områder: {archive} / {base}")
    if "dias_package" in (getattr(job, "workflow_ids", []) or []):
        if archive is None:
            issue("AIP_NOT_CONFIGURED", "error", "Arbeidsflyten inneholder DIAS-pakking, men AIP / arkiv er ikke valgt.")
        elif archive.exists() and not archive.is_dir():
            issue("AIP_IS_FILE", "error", f"AIP / arkiv peker på en fil: {archive}")
        elif not archive.exists():
            actions.append(PreflightAction("mkdir", str(archive), "Opprett valgt AIP-mappe (nødvendig for DIAS-pakking)"))

    if not (getattr(job, "workflow_ids", None) or []):
        issue("WORKFLOW_EMPTY", "error", "Jobben har ingen operasjoner i arbeidsflyten.")

    return PreflightReport(job_id, tuple(issues), tuple(actions))


def paths_to_create(actions: Iterable[PreflightAction]) -> tuple[Path, ...]:
    return tuple(Path(item.path) for item in actions if item.kind == "mkdir")
