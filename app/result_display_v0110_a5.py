"""Read-only presentation helpers for the v0.1.10-a5 result center.

No test execution, archival source traversal, or changes to persisted evidence.
Test labels are taken from the shipped Noark 5 catalog; Arkade fallback rows
come exclusively from tests already materialized in a depot report.
"""
from __future__ import annotations

from functools import lru_cache
from html import escape
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


CATALOG = Path(__file__).resolve().parents[1] / 'config' / 'noark5' / 'tests' / 'xpath_catalog_2026_05_26.json'
MAX_PREVIEW_BYTES = 512_000


@lru_cache(maxsize=4)
def load_technical_test_names(catalog_path: str | Path = CATALOG) -> dict[str, str]:
    """Use the existing versioned catalog, never a guessed name from an N5 number."""
    try:
        path = Path(catalog_path)
        if not path.is_file() or path.stat().st_size > 2_000_000:
            return {}
        obj = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(obj, dict) or not isinstance(obj.get('tests'), list):
            return {}
    except (OSError, TypeError, ValueError, UnicodeError):
        return {}
    labels: dict[str, str] = {}
    for item in obj['tests']:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name') or '').strip()
        if not name:
            continue
        legacy = item.get('legacy') if isinstance(item.get('legacy'), dict) else {}
        keys = (item.get('test_id'), legacy.get('job_id'))
        for raw in keys:
            key = str(raw or '').strip().casefold()
            if key:
                labels.setdefault(key, name)
    return labels


def technical_test_name(details: Any, visible_id: str, *, names: Mapping[str, str] | None = None) -> str:
    """Return the catalog name, or an honest missing-name marker."""
    known = names if names is not None else load_technical_test_names()
    obj = details if isinstance(details, dict) else {}
    for raw in (obj.get('test_id'), obj.get('legacy_job_id'), visible_id):
        name = known.get(str(raw or '').strip().casefold())
        if name:
            return name
    return 'Navn ikke registrert i testkatalogen'


def arkade_tests_from_depot(snapshots: Iterable[Any]) -> tuple[dict[str, Any], ...]:
    """Read genuine Arkade test coverage preserved in the stored depot report.

    Used only when the normalized external source cannot be loaded in the
    bounded Qt viewer (e.g. a very large full Arkade results JSON). A listed
    import is not itself proof that any individual test has run. We accept
    only explicit ``arkade.present is True`` on materialized control areas.
    """
    rows = []
    for shot in snapshots:
        report = shot.depot if isinstance(shot.depot, dict) else {}
        validation = report.get('external_validation') or {}
        if not isinstance(validation, dict):
            continue
        external = validation.get('arkade5') or {}
        if not isinstance(external, dict):
            continue
        imports = external.get('imports') or []
        if not isinstance(imports, list):
            continue
        for run in imports[:250]:
            if not isinstance(run, dict):
                continue
            coverage = run.get('coverage') or {}
            if not isinstance(coverage, dict):
                continue
            areas = coverage.get('arkade_control_areas') or []
            if not isinstance(areas, list):
                continue
            import_id = str(run.get('import_id') or '')
            for area in areas[:250]:
                if not isinstance(area, dict):
                    continue
                arkade = area.get('arkade') or {}
                if not isinstance(arkade, dict) or arkade.get('present') is not True:
                    continue
                test_id = str(area.get('arkade_test_id') or '').strip()
                if not test_id:
                    continue
                rows.append({
                    'job': shot.job,
                    'test_id': test_id,
                    'title': str(area.get('arkade_test_name') or 'Testnavn ikke tilgjengelig'),
                    'status': str(arkade.get('status') or 'unknown'),
                    'errors': arkade.get('number_of_errors'),
                    'import_id': import_id,
                    'date_of_testing': run.get('date_of_testing'),
                    'source_version': run.get('source_version'),
                    'source_file': run.get('source_file'),
                    'source_sha256': run.get('source_sha256'),
                    'details': {
                        'proveniens': 'Lagret Arkade 5-testdekning fra depotrapport (ikke ny kjøring)',
                        'import_id': import_id,
                        'arkade_versjon': run.get('source_version'),
                        'testdato': run.get('date_of_testing'),
                        'kilde_fil': run.get('source_file'),
                        'kilde_sha256': run.get('source_sha256'),
                        'arkade_kontroll': area,
                    },
                    'file': shot.results.depot_report_path,
                })
    return tuple(rows)


def read_work_markdown(candidate: str | Path | None, work_roots: Iterable[Path],
                       *, max_bytes: int = MAX_PREVIEW_BYTES) -> str | None:
    """Preview small UTF-8 Markdown artifacts inside known Work roots only."""
    if not candidate:
        return None
    try:
        file = Path(candidate)
        if file.suffix.casefold() not in {'.md', '.markdown'}:
            return None
        target = file.resolve(strict=True)
        if not target.is_file() or target.stat().st_size > max_bytes:
            return None
        for root in work_roots:
            base = Path(root).resolve(strict=True)
            if target.is_relative_to(base):
                return target.read_text(encoding='utf-8-sig')
    except (OSError, UnicodeError, TypeError, ValueError, RuntimeError):
        return None
    return None


def readable_html(data: Any, *, max_nodes: int = 1000, max_depth: int = 9) -> str:
    """Present saved evidence as ONE flat, bounded key/value table.

    Nested HTML tables previously squeezed deeply nested Arkade/period details
    into unreadable columns. Keep section headings, but never nest tables.
    Original fields remain available in the separate raw/JSON mode.
    """
    known = {
        'arkade_kontroll': 'Arkade-kontroll', 'arkade': 'Arkade-resultat',
        'arkade_test_id': 'Arkade test-ID', 'arkade_test_name': 'Testnavn',
        'arkade_type': 'Kontrolltype', 'number_of_errors': 'Antall feil',
        'result_count': 'Antall funn', 'combined_status': 'Samlet dekning',
        'coverage_strategy': 'Dekningsstrategi', 'coverage': 'Dekning',
        'dwm_test_ids': 'DWM-test-ID-er', 'dwm_test_ids_present': 'DWM-tester utført',
        'relation': 'Relasjon', 'note_nb': 'Faglig merknad',
        'test_id': 'Test-ID', 'test_point': 'Noark-punkt',
        'testnavn_fra_testkatalog': 'Testnavn (katalog)',
        'import_id': 'Import-ID', 'importert_at': 'Importert',
        'kilde_sha256': 'Kilde SHA-256', 'kilde_fil': 'Kildefil',
        'arkade_versjon': 'Arkade-versjon', 'testdato': 'Testdato',
        'status': 'Status', 'source_status': 'Kildestatus',
        'source_row': 'Opprinnelig kildepost', 'source_version': 'Kildeversjon',
        'formatvurdering': 'Formatvurdering', 'begrunnelse': 'Begrunnelse',
        'matched_rule': 'Matchende formatregel', 'regelprofil': 'Valgt regelprofil',
        'historisk_arkade_raf': 'Historisk Arkade/RAF',
        'klassifisering': 'Klassifisering', 'pronom_kildefil': 'PRONOM-kildefil',
        'pronom_kilde_sha256': 'PRONOM kilde SHA-256',
        'merking': 'Merknad', 'proveniens': 'Proveniens',
        'arkivdel': 'Arkivdel', 'archive_part': 'Arkivdelmetadata',
        'periodeevidens': 'Periodeevidens', 'period_evidence': 'Periodeevidens',
        'period_reconciliation': 'Periodeavstemming',
        'vurderingspunkter': 'Vurderingspunkter', 'requires_review': 'Krever gjennomgang',
        'severity': 'Alvorlighetsgrad', 'summary': 'Sammendrag',
        'note': 'Merknad', 'system_id': 'System-ID',
        'title': 'Tittel', 'count': 'Antall', 'name': 'Navn',
        'job_uid': 'Jobb-UUID', 'report_path': 'Rapportfil',
    }
    remaining = [max(0, int(max_nodes))]
    rows = []
    truncated = [False]

    def scalar(value: Any) -> str:
        if value is None or value == '':
            return '<i>Ikke oppgitt</i>'
        if isinstance(value, bool):
            return 'Ja' if value else 'Nei'
        text = str(value)
        if len(text) > 2500:
            text = text[:2500] + ' … [avkortet i visning]'
        return escape(text).replace('\n', '<br>')

    def label(key: Any) -> str:
        raw = str(key)
        return escape(known.get(raw, raw.replace('_', ' ')))

    def section(title: str, count: int | None = None):
        suffix = f' ({count} oppføringer)' if count is not None else ''
        rows.append('<tr><td colspan="2" style="padding-top:12px; '
                    'border-bottom:1px solid #888;"><b>'
                    + title + suffix + '</b></td></tr>')

    def walk(value: Any, depth: int):
        if remaining[0] <= 0 or depth >= max_depth:
            truncated[0] = True
            return
        remaining[0] -= 1
        if isinstance(value, Mapping):
            if not value:
                rows.append('<tr><td colspan="2"><i>Ingen opplysninger</i></td></tr>')
            for key, item in value.items():
                if remaining[0] <= 0:
                    truncated[0] = True
                    break
                shown = label(key)
                if isinstance(item, Mapping):
                    section(shown)
                    walk(item, depth + 1)
                elif isinstance(item, (list, tuple)):
                    section(shown, len(item))
                    walk(item, depth + 1)
                else:
                    rows.append('<tr><td width="39%" valign="top"><b>' + shown
                                + '</b></td><td valign="top">' + scalar(item) + '</td></tr>')
                    remaining[0] -= 1
        elif isinstance(value, (list, tuple)):
            if not value:
                rows.append('<tr><td colspan="2"><i>Ingen oppføringer</i></td></tr>')
            for index, item in enumerate(value, start=1):
                if remaining[0] <= 0:
                    truncated[0] = True
                    break
                if isinstance(item, (Mapping, list, tuple)):
                    section(f'Oppføring {index}')
                    walk(item, depth + 1)
                else:
                    rows.append('<tr><td width="39%"><b>' + str(index)
                                + '</b></td><td>' + scalar(item) + '</td></tr>')
                    remaining[0] -= 1
        else:
            rows.append('<tr><td>Verdi</td><td>' + scalar(value) + '</td></tr>')

    walk(data, 0)
    if truncated[0]:
        rows.append('<tr><td colspan="2"><i>Avkortet – se Råtekst / JSON for '
                    'komplett grunnlag.</i></td></tr>')
    return ('<html><body><h3>Detaljer og evidens</h3>'
            '<table cellspacing="0" cellpadding="5" width="100%">'
            + ''.join(rows) + '</table>'
            '<p><i>Lesbar visning av lagret evidens; originaldata er uendret.</i></p>'
            '</body></html>')


def default_table_fraction(row_count: int, *, tab: str = '') -> float:
    """Initial table/detail split; larger tables get room without hiding details."""
    if row_count <= 3:
        return 0.22
    if row_count <= 12:
        return 0.40
    if row_count <= 30:
        return 0.65 if tab == 'PRONOM' else 0.55
    return 0.68
