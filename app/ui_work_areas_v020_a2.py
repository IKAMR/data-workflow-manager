"""v0.2.0-a2: truthful depot work-area integration and maturity catalog.

Integration state (available/legacy/partial/planned) is NOT a depot approval,
archive processing status or operation maturity. These cards are UI routes.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.operation_metadata import MATURITY_LEVELS, MATURITY_LABELS


@dataclass(frozen=True)
class WorkArea:
    key: str
    state: str
    state_label: str
    detail: str
    route: str | None
    maturity: str = 'alpha'  # 0=alpha, 1=beta, 2=stable (UI integration only)

    @property
    def maturity_level(self) -> int:
        return MATURITY_LEVELS[self.maturity]

    @property
    def maturity_label(self) -> str:
        return MATURITY_LABELS[self.maturity]


# Ordered depot navigation, independent of the underlying operation registry.
# Ingest is alpha as a GUI integration even though an established legacy
# receiving implementation exists. Stable indicates only a stable GUI route.
WORK_AREAS = (
    WorkArea('ingest', 'legacy', 'Eldre GUI',
             'Mottak/Ingest finnes i det eksisterende grensesnittet. '
             'Det startes separat etter bekreftelse.', 'legacy_ingest', 'alpha'),
    WorkArea('antivirus', 'planned', 'Ikke integrert',
             'Ingen antiviruskontroll er koblet til denne arbeidsflaten.', None, 'alpha'),
    WorkArea('workspace', 'available', 'Tilgjengelig',
             'Gå til eksisterende Work-steg i Enkel modus. '
             'Ingen mapper opprettes automatisk.', 'basic_work', 'stable'),
    WorkArea('control', 'available', 'Tilgjengelig',
             'Bruk eksisterende Enkel eller Avansert kontroll av uttrekk.', 'control', 'stable'),
    WorkArea('report', 'available', 'Tilgjengelig',
             'Åpne eksisterende resultatvisninger eller rapportdialog.', 'report', 'beta'),
    WorkArea('preserve', 'partial', 'Delvis integrert',
             'DIAS-koblingskontroll i Qt; eksisterende DIAS AIP-pakking '
             'ligger fremdeles i eldre GUI.', 'preservation', 'beta'),
    WorkArea('crm', 'planned', 'Ikke integrert',
             'Ingen kobling til intern CRM er implementert.', None, 'alpha'),
    WorkArea('access', 'planned', 'Ikke integrert',
             'Ingen innsyns- eller publiseringstjeneste er implementert.', None, 'alpha'),
)
AREA_BY_KEY = {area.key: area for area in WORK_AREAS}


def work_area(key: str) -> WorkArea:
    """Unknown sections cannot silently become a different operation."""
    return AREA_BY_KEY[key]


def normalize_area_visibility(value) -> int:
    """Zero is the backwards-compatible default; invalid stored data fails closed."""
    if value is None:
        return 0
    if type(value) is int and value in (0, 1, 2):
        return value
    return 2


def cards_for(visible_keys, sections, minimum_level: int = 0):
    """Filter by profile AND UI maturity without reordering production steps."""
    wanted = set(visible_keys)
    threshold = normalize_area_visibility(minimum_level)
    return tuple((key, title, work_area(key))
                 for key, title, _description in sections
                 if key in wanted and work_area(key).maturity_level >= threshold)


def destination(key: str) -> str | None:
    """Planned sections must never trigger an operation."""
    return work_area(key).route
