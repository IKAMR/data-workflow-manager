"""a11.5: one read-only practical QA run for historical KDRS vs DWM.

No KDRS/Saxon or DWM XPath execution is started. `--preflight` checks only
metadata and file presence, never hashes multi-GB Noark XML. Full reports are
staged outside Source/Work and published only after all writers succeed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from typing import Any, Callable

from app.noark5_kdrs_parity_v021_a11 import (
    OUTPUTS as PARITY_FILES, compare, digest, read_json, write_report,
)
from app.noark5_kdrs_text_import_v021_a11 import (
    MAX_REPORT_BYTES, PROFILES, REPORT_NAMES as IMPORT_FILES, SOURCE_FILES,
    STANDARD_VARIANTS, _read_report, build_import, write_import,
)

REPORT_TYPE = 'noark5_a11_practical_kdrs_qa_not_full_parity'
EXTRA_FILES = ('noark5-a11-practical-qa.json', 'noark5-a11-practical-qa.md')
MAX_DISCOVERY_FILES = 48


def _parse_reports(specs: list[str]) -> dict[str, Path]:
    reports: dict[str, Path] = {}
    for spec in specs:
        profile, sep, path = spec.partition('=')
        if not sep or profile not in PROFILES or not path.strip():
            raise ValueError('--report skal ha format STANDARD=fil, U1=fil eller U2=fil')
        if profile in reports:
            raise ValueError(f'Duplisert profil: {profile}')
        reports[profile] = Path(path)
    if not reports:
        raise ValueError('Ingen KDRS-rapporter er valgt')
    return reports


def _classify_report(path: Path) -> tuple[str, str, list[str]]:
    """Use genuine KDRS job IDs, not a guessed filename suffix."""
    query_filename, jobs = _read_report(path)
    names = [job.job_id for job in jobs]
    if set(names) == {'U01'} and len(names) == 1:
        profile = 'U1'
    elif set(names) == {'U02'} and len(names) == 1:
        profile = 'U2'
    elif any(name in {'U01', 'U02'} for name in names):
        raise ValueError(f'Blandet Standard/U01/U02-fil; velg separat KDRS-kilde: {path.name}')
    else:
        profile = 'STANDARD'
    return profile, query_filename, names


def discover_reports(folder: Path) -> dict[str, Path]:
    """Inspect flat KDRS directory, preserving the caller's path spelling.

    Windows may expose one directory using both a long path and an 8.3 short
    alias. Resolve only for the containment check; returned file paths must
    retain the selected directory spelling instead of changing it silently.
    """
    canonical_folder = folder.resolve()
    if not folder.is_dir():
        raise ValueError(f'KDRS-mappen finnes ikke: {folder}')
    files = sorted((f for f in folder.iterdir()
                    if f.is_file() and f.name.casefold().startswith('kdrs_query_results_')
                    and f.suffix.casefold() == '.txt'), key=lambda p: p.name.casefold())
    if len(files) > MAX_DISCOVERY_FILES:
        raise ValueError('For mange mulige KDRS-resultatfiler; bruk eksplisitte --report-valg')
    if not files:
        raise ValueError('Fant ingen kdrs_query_results_*.txt i valgt KDRS-mappe')
    grouped: dict[str, list[Path]] = {}
    for file in files:
        if file.resolve().parent != canonical_folder:
            raise ValueError(f'KDRS-fil peker utenfor valgt mappe: {file.name}')
        if file.stat().st_size > MAX_REPORT_BYTES:
            raise ValueError(f'KDRS-tekstfil overskrider størrelsesgrensen: {file.name}')
        profile, _, _ = _classify_report(file)
        grouped.setdefault(profile, []).append(file)
    duplicates = {key: [f.name for f in value] for key, value in grouped.items() if len(value) > 1}
    if duplicates:
        details = '; '.join(f'{profile}: {", ".join(files)}' for profile, files in sorted(duplicates.items()))
        raise ValueError('Tvetydige KDRS-profiler: ' + details + '. Bruk --report eksplisitt.')
    return {key: files[0] for key, files in grouped.items()}


def resolve_index(index: Path | None, run_dir: Path | None) -> Path:
    if (index is None) == (run_dir is None):
        raise ValueError('Oppgi enten --dwm-index eller --dwm-run-dir')
    selected = index if index is not None else run_dir / 'index.json'
    if not selected.is_file():
        raise ValueError(f'Finner ikke DWM index.json: {selected}')
    return selected.resolve()


def _safe_source_name(name: str) -> bool:
    return (isinstance(name, str) and name.endswith('.xml') and name not in {'.xml', '..xml'}
            and Path(name).name == name and not any(c in name for c in ('/', '\\', ':')))


def inspect_inputs(dwm_root: Path, xml_root: Path, dwm_index: Path,
                   reports: dict[str, Path]) -> dict[str, Any]:
    """Metadata preflight: never open XML content or assert execution-time bytes."""
    catalog = read_json(dwm_root / 'config/noark5/tests/xpath_catalog_2026_05_26.json')
    tests = catalog.get('tests')
    if not isinstance(tests, list):
        raise ValueError('DWM-testkatalogen mangler testlisten')
    legacy_lookup = {}
    for test in tests:
        if not isinstance(test, dict):
            raise ValueError('Ugyldig DWM-katalograd')
        legacy_id = (test.get('legacy') or {}).get('job_id')
        if isinstance(legacy_id, str):
            if legacy_id in legacy_lookup:
                raise ValueError(f'Duplisert KDRS-jobb i katalog: {legacy_id}')
            legacy_lookup[legacy_id] = test
    index = read_json(dwm_index)
    if index.get('result_set_format_version') != 2 or not isinstance(index.get('tests'), list):
        raise ValueError('Valgt DWM index.json er ikke resultatformat v2')
    by_test = {}
    for entry in index['tests']:
        if not isinstance(entry, dict) or not isinstance(entry.get('test_id'), str):
            raise ValueError('Ugyldig DWM-resultatindeks')
        if entry['test_id'] in by_test:
            raise ValueError(f'Duplisert test-ID i DWM-resultat: {entry["test_id"]}')
        by_test[entry['test_id']] = entry
    results = []
    source_names: set[str] = set()
    findings = []
    for profile in ('STANDARD', 'U1', 'U2'):
        if profile not in reports:
            continue
        report = reports[profile].resolve()
        header, jobs = _read_report(report)
        recognized = {SOURCE_FILES[profile]}
        if profile == 'STANDARD':
            recognized.update(STANDARD_VARIANTS)
        else:
            recognized.add(SOURCE_FILES['STANDARD'])
            recognized.update(STANDARD_VARIANTS)
        actual_profile, _, ids = _classify_report(report)
        if actual_profile != profile:
            raise ValueError(f'KDRS-jobber i {report.name} er {actual_profile}, ikke {profile}')
        if header not in recognized:
            findings.append({'severity':'WARNING', 'reason':'query_source_header_unrecognized',
                             'profile':profile, 'filename':report.name, 'query_file_basename':header})
        statuses = Counter()
        for job in jobs:
            test = legacy_lookup.get(job.job_id)
            if test is None:
                findings.append({'severity':'WARNING','reason':'job_not_in_dwm_catalog',
                                 'profile':profile,'job_id':job.job_id})
                statuses['not_in_catalog'] += 1
                continue
            source_xml = test.get('source_xml')
            if not _safe_source_name(source_xml):
                findings.append({'severity':'FEIL', 'reason':'unsafe_catalog_source_xml',
                                 'job_id':job.job_id, 'source_xml':str(source_xml)})
                statuses['invalid_xml_name'] += 1
                continue
            source_names.add(source_xml)
            dwm = by_test.get(test.get('test_id'))
            if dwm is None:
                statuses['missing_dwm_test'] += 1
            else:
                statuses[str(dwm.get('status') or 'unknown')] += 1
        results.append({'profile':profile,'report':str(report),
                        'report_bytes':report.stat().st_size,
                        'query_file_basename':header,'jobs':ids,
                        'dwm_test_status_counts':dict(statuses)})
        if profile == 'U2' and by_test.get('kdrs.u02', {}).get('status') != 'ok':
            findings.append({'severity':'WARNING','reason':'u2_dwm_regression_result_missing_or_not_ok'})
        if profile == 'U1' and by_test.get('kdrs.u01', {}).get('status') != 'ok':
            findings.append({'severity':'WARNING','reason':'u1_dwm_regression_result_missing_or_not_ok'})
    xml_entries = []
    xml_base = xml_root.resolve()
    for name in sorted(source_names):
        path = (xml_base / name).resolve()
        exists = path.is_relative_to(xml_base) and path.is_file()
        xml_entries.append({'source_xml':name, 'present':exists,
                            'size_bytes':path.stat().st_size if exists else None})
        if not exists:
            findings.append({'severity':'FEIL','reason':'xml_source_missing', 'source_xml':name})
    return {'report_type':'noark5_a11_preflight_metadata_only', 'dwm_index':str(dwm_index),
            'dwm_index_sha256':digest(dwm_index), 'reports':results, 'xml_files':xml_entries,
            'findings':findings, 'xml_sha256_read':False,
            'historical_saxon_runtime_attested':False}


def _disjoint_output(output_dir: Path, *protected_roots: Path) -> None:
    out = output_dir.resolve()
    for protected in protected_roots:
        root = protected.resolve()
        if out.is_relative_to(root) or root.is_relative_to(out):
            raise ValueError(f'Utdata må være adskilt fra Source/Work/KDRS/DWM: {root}')
    if out.exists():
        raise FileExistsError(f'Utdata-mappen finnes allerede; velg en ny: {out}')


def _qa_summary(preflight: dict, legacy: dict, mapping: dict, inventory: list[dict],
                parity: dict) -> dict:
    status = parity['summary']
    reasons = Counter(row.get('reason') or '' for row in parity['comparisons']
                      if row['status'] != 'MATCH_PROVISIONAL')
    severity = Counter(row['severity'] for row in preflight['findings'])
    imported = Counter(row['mapping_status'] for row in inventory)
    return {
        'report_type':REPORT_TYPE, 'format_version':1,
        'noark_version':legacy.get('noark_version'),
        'created_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'preflight':preflight,
        'source_report_hashes':legacy.get('kdrs_reports_sha256', {}),
        'kdrs_reference_source_hashes':legacy.get('kdrs_reference_source_sha256', {}),
        'xml_sha256_at_import':legacy.get('xml_sha256', {}),
        'imported_jobs':len(inventory), 'mapped_metric_rows':len(mapping['comparisons']),
        'import_status_counts':dict(imported),
        'import_issues':legacy.get('import_issues', []),
        'preflight_findings_by_severity':dict(severity),
        'comparison_summary':status,
        'unmatched_reason_counts':dict(reasons),
        'review_status':'REVIEW_REQUIRED' if mapping['comparisons'] else 'INSUFFICIENT_EVIDENCE',
        'historical_execution_time_xml_sha256_attested':False,
        'whole_saxon_lxml_parity_verified':False,
        'normative_noark_conformance_verified':False,
        'source_modified':False,
        'notes':('KDRS historiske resultater og DWM-kjøring må knyttes til samme '
                 'faktiske uttrekk. Dagens XML SHA-256 er ikke en attest av '
                 'historiske input-byte eller en godkjenningsbeslutning.')
    }


def _qa_markdown(report: dict) -> str:
    pre = report['preflight']
    s = report['comparison_summary']
    lines = [
        '# Noark 5 a11.5 – praktisk KDRS/DWM-kvalitetssikring', '',
        f"Oppgitt Noark-versjon: **{report['noark_version']}**.", '',
        '## Datagrunnlag', '',
        f"DWM-indeks: `{pre['dwm_index']}`", '',
        '| KDRS-profil | Jobber | DWM ok | DWM mangler | Fil |',
        '| --- | ---: | ---: | ---: | --- |',
    ]
    for r in pre['reports']:
        counts = r['dwm_test_status_counts']
        # Display only a filename; raw KDRS text can contain restricted content.
        filename = Path(r['report']).name.replace('|', '\\|')
        lines.append(f"| {r['profile']} | {len(r['jobs'])} | {counts.get('ok',0)} | "
                     f"{counts.get('missing_dwm_test',0)} | {filename} |")
    lines += ['', '## Sammenligninger', '',
              f"Eksplisitt kartlagte verdier: **{report['mapped_metric_rows']}**.",
              f"MATCH_PROVISIONAL: **{s['provisional_matches']}**; "
              f"MISMATCH_PROVISIONAL: **{s['provisional_mismatches']}**; "
              f"NOT_COMPARABLE: **{s['not_comparable']}**.", '',
              '| Profil | Sammenligninger | Treffer | Avvik | Ikke sammenlignbart |',
              '| --- | ---: | ---: | ---: | ---: |']
    for name, item in sorted(s.get('by_profile', {}).items()):
        lines.append(f"| {name} | {item['rows']} | {item['matches']} | "
                     f"{item['mismatches']} | {item['not_comparable']} |")
    lines += ['', '## Funn som må avklares', '']
    if report['unmatched_reason_counts']:
        for reason, count in sorted(report['unmatched_reason_counts'].items()):
            lines.append(f'- `{reason}`: {count}')
    else:
        lines.append('Ingen foreløpige sammenligningsavvik registrert.')
    if report['import_issues'] or pre['findings']:
        lines.append(f"- Import-/kilde-QA: {len(report['import_issues'])} importfunn, "
                     f"{len(pre['findings'])} forhåndskontrollfunn")
    lines += ['', '## Videre faglig behandling', '',
              'Funn må kontrolleres mot original XML, historisk kjøring og valgt '
              'Noark-versjon før en konklusjon. En oppført nullverdi er ikke '
              'det samme som manglende data.', '',
              '**Ingen historisk Saxon-kjøring eller input-byteidentitet er attestert.** '
              'Samsvar er foreløpig, ikke dokumentert komplett semantisk paritet '
              'eller normativ Noark 5-godkjenning.', '',
              'Arkade 5 sine Noark 5-tester og parallellkjøring er utsatt til '
              'egen ToDo. Kvalitetssikringsrapport og depotets godkjenningsrapport '
              'bygges på egne dokumenterte vurderings- og beslutningslag.', '']
    return '\n'.join(lines)


def run_practical_qa(*, dwm_root: Path, xml_root: Path, dwm_index: Path,
                     reports: dict[str, Path], noark_version: str,
                     output_dir: Path,
                     progress: Callable[[str], None] | None = None) -> dict:
    """Stage the complete nine-file report set and publish atomically."""
    dwm_root = dwm_root.resolve()
    xml_root = xml_root.resolve()
    dwm_index = dwm_index.resolve()
    reports = {p:path.resolve() for p,path in reports.items()}
    if noark_version not in ('3.1','4.0','5.0'):
        raise ValueError('Noark-versjon må være 3.1, 4.0 eller 5.0')
    if not dwm_root.is_dir() or not xml_root.is_dir():
        raise ValueError('DWM-repo og Source-mappe må finnes')
    if not reports or set(reports) - PROFILES:
        raise ValueError('Ingen gyldige KDRS-rapporter valgt')
    _disjoint_output(output_dir, dwm_root, xml_root, dwm_index.parent,
                     *(r.parent for r in reports.values()))
    preflight = inspect_inputs(dwm_root, xml_root, dwm_index, reports)
    if any(issue['severity'] == 'FEIL' for issue in preflight['findings']):
        reasons = sorted({item['reason'] for item in preflight['findings'] if item['severity'] == 'FEIL'})
        raise ValueError('Forhåndskontroll stoppet: ' + ', '.join(reasons))
    parent = output_dir.resolve().parent
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.noark5-a11.5-', dir=parent) as temporary:
        staging = Path(temporary)
        if progress:
            progress('Leser KDRS-resultater og hasher angitte XML-filer (strømmet SHA-256).')
        legacy, mapping, inventory = build_import(dwm_root=dwm_root, xml_root=xml_root,
            reports=reports, noark_version=noark_version, dwm_index_path=dwm_index)
        write_import(legacy, mapping, inventory, staging)
        if progress:
            progress(f"Sammenligner {len(mapping['comparisons'])} kandidatverdier mot DWM-indeksen.")
        parity = compare(dwm_index, staging/IMPORT_FILES[0], staging/IMPORT_FILES[1], xml_root)
        write_report(parity, staging)
        summary = _qa_summary(preflight, legacy, mapping, inventory, parity)
        (staging/EXTRA_FILES[0]).write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
        (staging/EXTRA_FILES[1]).write_text(_qa_markdown(summary), encoding='utf-8')
        expected = set(IMPORT_FILES) | set(PARITY_FILES) | set(EXTRA_FILES)
        if {p.name for p in staging.iterdir()} != expected:
            raise ValueError('Ufullstendig rapportpakke; ingen utdata publiseres')
        if output_dir.exists():
            raise FileExistsError('Utdata-mappen ble opprettet av en annen prosess')
        staging.rename(output_dir)
        if progress:
            progress(f'Publisert {len(expected)} QA-filer i {output_dir}.')
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='a11.5: praktisk KDRS/DWM QA uten nye XPath-kjøringer')
    parser.add_argument('--dwm-root', required=True, type=Path)
    parser.add_argument('--xml-root', required=True, type=Path)
    parser.add_argument('--noark-version', required=True, choices=('3.1','4.0','5.0'))
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--kdrs-dir', type=Path,
                           help='Automatisk, ikke-rekursiv oppdagelse av originale KDRS-tekstfiler')
    selection.add_argument('--report', action='append', metavar='STANDARD|U1|U2=STI',
                           help='Eksplisitt filvalg (kan gjentas) ved tvetydig katalog')
    run = parser.add_mutually_exclusive_group(required=True)
    run.add_argument('--dwm-index', type=Path)
    run.add_argument('--dwm-run-dir', type=Path, help='Mappe som inneholder DWM index.json')
    parser.add_argument('--preflight', action='store_true',
                        help='Kun metadata og kildefileksistens; ikke hash store XML')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args(argv)
    try:
        reports = discover_reports(args.kdrs_dir) if args.kdrs_dir else _parse_reports(args.report or [])
        index = resolve_index(args.dwm_index, args.dwm_run_dir)
        if args.preflight:
            preflight = inspect_inputs(args.dwm_root, args.xml_root, index, reports)
            print(json.dumps(preflight, ensure_ascii=False, indent=2))
            return 2 if any(x['severity'] == 'FEIL' for x in preflight['findings']) else 0
        if args.output_dir is None:
            parser.error('--output-dir kreves ved faktisk QA-kjøring')
        summary = run_practical_qa(dwm_root=args.dwm_root, xml_root=args.xml_root,
                                  dwm_index=index, reports=reports,
                                  noark_version=args.noark_version,
                                  output_dir=args.output_dir,
                                  progress=lambda msg: print(msg, flush=True))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print('a11.5 QA-pakke:', args.output_dir)
    print('Sammenligninger:', summary['mapped_metric_rows'])
    print('Resultater:', summary['comparison_summary']['provisional_matches'], 'MATCH_PROVISIONAL,',
          summary['comparison_summary']['provisional_mismatches'], 'MISMATCH_PROVISIONAL,',
          summary['comparison_summary']['not_comparable'], 'NOT_COMPARABLE')
    print('Status:', summary['review_status'], '(ingen automatisk Noark-godkjenning)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
