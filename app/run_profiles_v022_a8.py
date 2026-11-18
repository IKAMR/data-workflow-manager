"""v0.2.2-a8: reusable Noark 5 run profiles, no execution side effects.

Profiles are *templates* for a newly configured job. The job's workflow_ids
remain the frozen, authoritative execution plan after selection. Microtests
are intentionally NOT exposed as switches until adapter capabilities exist.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping, Iterable

from app.workflow_dependencies_v022_a7 import ensure_a7_processing, validate_dependencies

DEFAULT_PROFILE_ID = 'dwm_standard'
ARKADE_NOARK = 'arkade5_noark5_test'
ARKADE_PRONOM = 'arkade5_pronom_analysis'
ARKADE_IDS = (ARKADE_NOARK, ARKADE_PRONOM)
ADVANCED_IDS = ('analyse_noark5_core', 'analyse_noark5_u1',
                'run_noark5_xpath_regression_2026')
BASE_IDS = ('metadata_inventory', 'validate_xml_schema', 'analyse_arkivstruktur',
            'run_noark5_xpath_tests_2026', 'siegfried_pronom_identification')


@dataclass(frozen=True)
class RunProfile:
    profile_id: str
    name: str
    operation_ids: tuple[str, ...]
    description: str = ''
    builtin: bool = False


def _compose(technical: Iterable[str]) -> tuple[str, ...]:
    technical = tuple(technical)
    if len(set(technical)) != len(technical):
        raise ValueError('Dupliserte tekniske deljobber.')
    ids = ensure_a7_processing(technical)
    problems = validate_dependencies(ids)
    if problems:
        raise ValueError('Ugyldige avhengigheter: ' + '; '.join(problems))
    return ids


def builtin_profiles() -> tuple[RunProfile, ...]:
    return (
        RunProfile('dwm_standard', 'Standard DWM', _compose(BASE_IDS),
                   'DWM XPath, XML/XSD, Siegfried, evidens, rapport og KS-utkast.', True),
        RunProfile('dwm_advanced', 'Avansert DWM', _compose((*BASE_IDS, *ADVANCED_IDS)),
                   'Supplerende historiske og regresjonsrettede kontroller; ingen Arkade.', True),
        RunProfile('dwm_complete', 'Komplett DWM + Arkade 5',
                   _compose((*BASE_IDS, *ADVANCED_IDS, *ARKADE_IDS)),
                   'Alle DWM-familier og begge uavhengige Arkade-kontroller.', True),
    )


def toggle_arkade(profile: RunProfile, *, noark: bool, pronom: bool) -> RunProfile:
    """Remove/reinsert individual Arkade operations *before* processing.

    Avoid carrying a stale A200 importer or moving an Arkade scan after A210.
    """
    existing = tuple(op for op in profile.operation_ids if op not in ARKADE_IDS
                     and op not in ('import_arkade5_reports',
                                    'build_noark5_canonical_evidence',
                                    'analyze_noark5_external_evidence',
                                    'audit_noark5_evidence', 'compose_noark5_views',
                                    'build_noark5_depot_report', 'build_noark5_qa_draft'))
    selected = (*existing, *((ARKADE_NOARK,) if noark else ()),
                *((ARKADE_PRONOM,) if pronom else ()))
    return RunProfile(profile.profile_id, profile.name, _compose(selected),
                      profile.description, profile.builtin)


def profile_controls(profile: RunProfile) -> tuple[bool, bool]:
    return (ARKADE_NOARK in profile.operation_ids,
            ARKADE_PRONOM in profile.operation_ids)


def _validate_custom(item: object) -> RunProfile:
    if not isinstance(item, dict):
        raise ValueError('Profil er ikke et objekt.')
    profile_id = item.get('profile_id')
    name = item.get('name')
    ids = item.get('operation_ids')
    if not isinstance(profile_id, str) or not re.fullmatch(r'custom_[a-z0-9_]{1,60}', profile_id):
        raise ValueError('Ugyldig profil-ID.')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        raise ValueError('Profilnavn må ha 1–100 tegn.')
    if not isinstance(ids, list) or not ids or not all(isinstance(v, str) for v in ids):
        raise ValueError('Ugyldig operasjonsliste.')
    operations = tuple(ids)
    if len(set(operations)) != len(operations):
        raise ValueError('Dupliserte deljobber.')
    allowed = set(BASE_IDS + ADVANCED_IDS + ARKADE_IDS +
                  ('import_arkade5_reports', 'build_noark5_canonical_evidence',
                   'analyze_noark5_external_evidence', 'audit_noark5_evidence',
                   'compose_noark5_views', 'build_noark5_depot_report',
                   'build_noark5_qa_draft'))
    if set(operations) - allowed:
        raise ValueError('Ukjente eller ikke-støttede operasjoner i profilen.')
    issues = validate_dependencies(operations)
    if issues:
        raise ValueError('; '.join(issues))
    # Newly saved Noark-5 profiles containing a XPath master must always
    # contain the full postprocessing chain.
    if 'run_noark5_xpath_tests_2026' in operations and _compose(
            [op for op in operations if op in BASE_IDS + ADVANCED_IDS + ARKADE_IDS]
            ) != operations:
        raise ValueError('Profilen mangler eller feilplasserer obligatorisk etterbehandling.')
    return RunProfile(profile_id, name.strip(), operations,
                      str(item.get('description', ''))[:500], False)


def custom_profiles(settings: Mapping) -> tuple[RunProfile, ...]:
    raw = settings.get('noark5_custom_run_profiles', [])
    if not isinstance(raw, list):
        return ()
    profiles = tuple(_validate_custom(item) for item in raw)
    ids = [profile.profile_id for profile in profiles]
    if len(ids) != len(set(ids)) or len(ids) > 100:
        raise ValueError('Dupliserte eller for mange brukerprofiler.')
    return profiles


def available_profiles(settings: Mapping) -> tuple[RunProfile, ...]:
    return (*builtin_profiles(), *custom_profiles(settings))


def selected_default(settings: Mapping) -> RunProfile:
    wanted = str(settings.get('noark5_default_run_profile') or DEFAULT_PROFILE_ID)
    return next((p for p in available_profiles(settings) if p.profile_id == wanted),
                builtin_profiles()[0])


def serialize_custom(profile: RunProfile) -> dict:
    validated = _validate_custom({'profile_id': profile.profile_id, 'name': profile.name,
                                  'operation_ids': list(profile.operation_ids),
                                  'description': profile.description})
    return {'profile_id': validated.profile_id, 'name': validated.name,
            'operation_ids': list(validated.operation_ids),
            'description': validated.description}


def save_custom_profile(settings: Mapping, name: str, operations: Iterable[str]) -> dict:
    import unicodedata
    normalized = unicodedata.normalize('NFKD', str(name)).encode('ascii', 'ignore').decode()
    slug = re.sub('[^a-z0-9]+', '_', normalized.lower()).strip('_')[:50] or 'profil'
    original = list(custom_profiles(settings))
    chosen = next((f'custom_{slug}_{i}' for i in range(1, 1001)
                   if f'custom_{slug}_{i}' not in {p.profile_id for p in original}), None)
    if chosen is None:
        raise ValueError('Ingen ledig profil-ID.')
    profile = RunProfile(chosen, name.strip(), tuple(operations))
    payload = [serialize_custom(p) for p in original] + [serialize_custom(profile)]
    return {'noark5_custom_run_profiles': payload}


def operation_microtest_support() -> dict[str, str]:
    """Informational only. Never pretend test-level switches are implemented."""
    return {'arkade5_noark5_test': 'planlagt - må kartlegge støtte i installert Arkade CLI',
            'arkade5_pronom_analysis': 'planlagt - per formatregel og filgruppe',
            'run_noark5_xpath_tests_2026': 'planlagt - per test-ID og regelversjon'}
