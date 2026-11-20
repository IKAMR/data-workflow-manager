"""Source-faithful interpretation of DWM's normalized Siegfried statistics."""
from __future__ import annotations


def summarize_dwm_siegfried_statistics(doc: dict) -> dict | None:
    """Return format evidence only; never infer validation or depot approval."""
    if (doc.get('evidence_type') != 'dwm_siegfried_pronom_identification' or
            doc.get('source_system') != 'DWM / Siegfried' or
            doc.get('format_version') != 1):
        return None
    counters = ('files_total', 'identified', 'unidentified', 'ambiguous')
    if any(type(doc.get(key)) is not int or not 0 <= doc[key] <= 1_000_000_000_000
           for key in counters):
        raise ValueError('Siegfried-statistikk har ugyldige filantall.')
    total, identified, unidentified, ambiguous = (doc[key] for key in counters)
    if identified + unidentified != total or ambiguous > identified:
        raise ValueError('Siegfried-statistikk har selvmotsigende filantall.')
    rows = doc.get('format_groups')
    if not isinstance(rows, list) or len(rows) > 100_000:
        raise ValueError('Siegfried-statistikk har ugyldige formatgrupper.')
    formats = []
    for item in rows:
        if not isinstance(item, dict) or type(item.get('count')) is not int or not 0 <= item['count'] <= 1_000_000_000_000:
            raise ValueError('Siegfried-statistikk har ugyldig formatantall.')
        puid = item.get('puid')
        if not isinstance(puid, str) or len(puid) > 150:
            raise ValueError('Siegfried-statistikk har ugyldig PRONOM-ID.')
        formats.append({'puid': puid, 'format': str(item.get('format') or '')[:400],
                        'version': str(item.get('version') or '')[:80],
                        'reported_count': item['count']})
    return {
        'source_format': 'dwm_siegfried_pronom_statistics_v1',
        'interpretation': 'format_statistics_only',
        'reported_total_files': total,
        'reported_identified_files': identified,
        'reported_unidentified_files': unidentified,
        'reported_ambiguous_files': ambiguous,
        'format_rows': len(formats),
        'formats': formats,
        'technical_validation_verified': False,
        'archive_creator_acceptance': None,
        'depot_approval': None,
        'note': 'PRONOM-formatidentifikasjon, ingen Noark 5- eller depotgodkjenning.',
    }
