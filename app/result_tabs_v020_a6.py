"""Stable grouping of the existing result tabs, independent of Qt."""
from __future__ import annotations


GROUP_DEFINITIONS = (
    ('Oversikt', ('Oversikt', 'Arkivdeler', 'Årsfordeling', 'Tekniske kontroller')),
    ('Eksterne kontroller', ('Arkade 5', 'PRONOM', 'KDRS Query', 'Arkade-dekning')),
    ('Rapporter og evidens', ('Depotrapporter', 'Evidensfiler', 'Kildeoversikt')),
    ('Faglig vurdering', ('Periodevurdering', 'Depotvurdering')),
)


def grouped_result_titles(titles):
    """Pure grouping: every original tab appears exactly once, in source order.

    New/unknown result types remain reachable, under the overview group.
    """
    available = list(dict.fromkeys(str(title) for title in titles))
    groups = []
    used = set()
    for heading, known in GROUP_DEFINITIONS:
        selected = [title for title in available if title in known and title not in used]
        groups.append((heading, tuple(selected)))
        used.update(selected)
    unknown = [title for title in available if title not in used]
    name, entries = groups[0]
    groups[0] = (name, tuple(entries + tuple(unknown)))
    return tuple(groups)

