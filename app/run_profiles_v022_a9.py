"""v0.2.2-a9: safe, editable Noark 5 run-profile templates.

A builtin profile is NEVER modified. Editing it produces a named custom copy.
Updating an existing custom profile changes a future-job template only;
existing .n5jobs/Work workflows remain frozen and untouched.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from app.run_profiles_v022_a8 import (
    ADVANCED_IDS, ARKADE_IDS, BASE_IDS, DEFAULT_PROFILE_ID,
    RunProfile, available_profiles, custom_profiles, save_custom_profile,
    serialize_custom,
)
from app.workflow_dependencies_v022_a7 import (
    AFTER_TESTS, ensure_a7_processing, validate_dependencies,
)

# Actual registered operation IDs. A190 is the 2026 regression adapter,
# NOT a fictitious unsuffixed operation.
TECHNICAL_IDS = tuple(dict.fromkeys((*BASE_IDS, *ADVANCED_IDS, *ARKADE_IDS)))
MANDATORY_IDS = ('run_noark5_xpath_tests_2026',)


@dataclass(frozen=True)
class ProfileEdit:
    """Settings delta, selected template ID, immutable new workflow."""
    changes: dict
    profile_id: str
    operation_ids: tuple[str, ...]


def technical_operations(profile: RunProfile) -> tuple[str, ...]:
    """Only the editable operations; dependent processing is always derived."""
    unknown = set(profile.operation_ids) - set(TECHNICAL_IDS) - set(AFTER_TESTS)
    if unknown:
        raise ValueError('Profilen har ikke-redigerbare operasjoner: ' + ', '.join(sorted(unknown)))
    return tuple(op for op in profile.operation_ids if op in TECHNICAL_IDS)


def compose_profile_operations(ordered_technical: Iterable[str]) -> tuple[str, ...]:
    """Validate the operator's exact technical order, then append processing.

    Do not claim processing microtasks are separately switchable. A210-A260
    are derived and guarded by a7, and A200 is conditional on either Arkade job.
    """
    ids = tuple(ordered_technical)
    if not ids:
        raise ValueError('Velg minst én teknisk deljobb.')
    if any(not isinstance(op, str) for op in ids):
        raise ValueError('Deljobb-ID må være tekst.')
    if len(ids) != len(set(ids)):
        raise ValueError('Dupliserte deljobber er ikke tillatt.')
    bad = set(ids) - set(TECHNICAL_IDS)
    if bad:
        raise ValueError('Ukjent teknisk deljobb: ' + ', '.join(sorted(bad)))
    for required in MANDATORY_IDS:
        if required not in ids:
            raise ValueError('A130 DWM Noark 5 XPath må inngå når kanonisk evidens og KS brukes.')
    flow = ensure_a7_processing(ids)
    problems = validate_dependencies(flow)
    if problems:
        raise ValueError('Ugyldig avhengighetsrekkefølge: ' + ' | '.join(problems))
    # A7 is the single source of truth for processing. Never silently lose
    # canonical evidence or draft QA from an edited DWM profile.
    for expected in ('build_noark5_canonical_evidence',
                     'analyze_noark5_external_evidence', 'audit_noark5_evidence',
                     'compose_noark5_views', 'build_noark5_depot_report',
                     'build_noark5_qa_draft'):
        if expected not in flow:
            raise ValueError('Obligatorisk etterbehandling mangler: ' + expected)
    return flow


def stage_profile_edit(settings: Mapping, source_profile_id: str,
                       name: str, ordered_technical: Iterable[str]) -> ProfileEdit:
    """Build a validated settings delta, without saving or changing a job.

    Builtins: create a new custom_ ID. User templates: update the selected ID.
    Caller must explicitly commit the changes at the normal Setup Save action.
    """
    profiles = {p.profile_id: p for p in available_profiles(settings)}
    original = profiles.get(str(source_profile_id))
    if original is None:
        raise ValueError('Kjøreprofilen finnes ikke lenger.')
    clean_name = str(name or '').strip()
    if not 1 <= len(clean_name) <= 100:
        raise ValueError('Profilnavnet må inneholde 1–100 tegn.')
    flow = compose_profile_operations(ordered_technical)
    if original.builtin:
        existing = custom_profiles(settings)
        if len(existing) >= 100:
            raise ValueError('Maksimum 100 brukerprofiler er nådd.')
        changes = save_custom_profile(settings, clean_name, flow)
        created = changes['noark5_custom_run_profiles'][-1]['profile_id']
        return ProfileEdit(changes, created, flow)
    # Custom profile: same identity, new template content only. Existing jobs
    # keep the immutable list stored with the job, even if the template changes.
    revised = RunProfile(original.profile_id, clean_name, flow,
                         original.description, False)
    payload = [serialize_custom(revised if p.profile_id == original.profile_id else p)
               for p in custom_profiles(settings)]
    changes = {'noark5_custom_run_profiles': payload}
    # Validate complete collection including duplicates and all dependencies.
    custom_profiles({**dict(settings), **changes})
    return ProfileEdit(changes, original.profile_id, flow)


def stage_default_profile(settings: Mapping, profile_id: str) -> dict:
    ids = {p.profile_id for p in available_profiles(settings)}
    if profile_id not in ids:
        raise ValueError('Ukjent kjøreprofil kan ikke settes som standard.')
    return {'noark5_default_run_profile': profile_id}


def legacy_fallback_sequence(profile: RunProfile) -> str:
    """Conservative compatibility setting for older non-Qt job creation.

    A legacy sequence cannot express a custom template. If both Arkade
    operations are present, use the existing Arkade preset; otherwise do not
    unexpectedly enable an unselected external adapter in older clients.
    The Qt a9 new-job path always installs profile.operation_ids directly.
    """
    if set(ARKADE_IDS).issubset(profile.operation_ids):
        return 'noark5_standard_arkade'
    return 'noark5_standard'


def staged_profile_settings_valid(settings: Mapping) -> tuple[RunProfile, ...]:
    """Central validation at the Setup API boundary before any disk writes."""
    profiles = available_profiles(settings)  # validates all saved custom items
    wanted = str(settings.get('noark5_default_run_profile') or DEFAULT_PROFILE_ID)
    if wanted not in {p.profile_id for p in profiles}:
        raise ValueError('Valgt standardprofil finnes ikke i de lagrede profilene.')
    return profiles


def install_default_on_new_job(api, before_job_ids: Iterable[str]) -> str | None:
    """Only change ONE genuinely new, unstarted Noark 5 job.

    Legacy jobs, Work content and pre-existing job lists are never migrated.
    The Qt Advanced new-job action calls this only after successful creation.
    """
    before = set(before_job_ids)
    added = [j for j in api.workspace().jobs if j.job_id not in before]
    if len(added) != 1:
        return None
    job = added[0]
    if str(getattr(job, 'profile_id', 'noark5') or 'noark5') != 'noark5':
        return None
    if int(getattr(job, 'next_operation_index', 0) or 0) != 0:
        return None
    if float(getattr(job, 'progress', 0) or 0) != 0:
        return None
    selected = next((p for p in staged_profile_settings_valid(api.settings)
                     if p.profile_id == str(api.settings.get('noark5_default_run_profile') or DEFAULT_PROFILE_ID)),
                    None)
    if selected is None:
        return None
    api.set_workflow(job.job_id, selected.operation_ids)
    return job.job_id
