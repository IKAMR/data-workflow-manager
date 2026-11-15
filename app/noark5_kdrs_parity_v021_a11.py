"""Evidence-gated comparison of KDRS/Saxon exports against DWM/lxml results.

No inferred equivalence: a comparison is permitted only with an explicit
same-extract SHA-256 manifest and explicitly mapped result paths. Never modifies
XML or the existing Work results. Does not invoke Saxon or KDRS Query.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from hashlib import sha256
import json
import re
from pathlib import Path
from typing import Any

REPORT_TYPE = 'noark5_a11_kdrs_dwm_evidence_gated_parity'
MAX_BYTES = 64_000_000
MAX_ROWS = 20_000
MISSING = object()
OUTPUTS = ('noark5-a11-parity.json', 'noark5-a11-parity.csv', 'noark5-a11-summary.md')


def read_json(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError(f'Input mangler eller er for stor: {path}')
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        raise ValueError(f'Forventer JSON-objekt: {path}')
    return data


def digest(path: Path) -> str:
    """Stream hash input; Noark XML can be many gigabytes."""
    h = sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def extract_manifest(root: Path, filenames: list[str]) -> dict[str, str]:
    """Hash exact on-disk bytes; only declared, safe, repository-relative XML."""
    root = root.resolve()
    out = {}
    for name in filenames:
        rel = Path(name)
        if rel.is_absolute() or '..' in rel.parts or rel.suffix.lower() != '.xml':
            raise ValueError(f'Utrygt eller ugyldig XML-filnavn: {name}')
        p = (root / rel).resolve()
        if not p.is_relative_to(root) or not p.is_file():
            raise ValueError(f'XML mangler/er utenfor uttrekk: {name}')
        out[name] = digest(p)
    return out


def get_path(value: Any, path: str) -> Any:
    """Explicit JSON path, dot-separated object keys and numeric list indices."""
    if not path or path.startswith('.') or '..' in path:
        return MISSING
    current = value
    for part in path.split('.'):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdecimal() and int(part) < len(current):
            current = current[int(part)]
        else:
            return MISSING
    return current


def canonical(value: Any) -> Any:
    """Compare JSON values with dict ordering ignored, list ordering retained."""
    if isinstance(value, dict):
        return ('object', tuple((k, canonical(v)) for k, v in sorted(value.items())))
    if isinstance(value, list):
        return ('array', tuple(canonical(v) for v in value))
    if isinstance(value, bool):
        return ('bool', value)
    if value is None:
        return ('null',)
    if isinstance(value, (int, float)):
        return ('number', value)
    if isinstance(value, str):
        return ('string', value)
    raise ValueError('Ugyldig JSON-verdi')


def safe_result_file(root: Path, filename: str) -> Path:
    rel = Path(filename)
    if rel.is_absolute() or '..' in rel.parts or rel.suffix.lower() != '.json':
        raise ValueError('Utrygg resultatfil')
    path = (root / rel).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Resultatfil utenfor DWM-indeks')
    return path


def compare(dwm_index_path: Path, kdrs_path: Path, mapping_path: Path,
            xml_root: Path) -> dict:
    """KDRS export contract: {format_version:1, engine:'Saxon',
    xml_sha256:{'arkivstruktur.xml':'...'}, jobs:{'C01':{'count':2}}}.
    Mapping contract: {format_version:1, comparisons:[{job_id:'C01',
    test_id:'kdrs.c01', kdrs_path:'count', dwm_path:'archive_count'}]}.
    The paths select inside KDRS jobs[job_id] and DWM result['values'].
    """
    dwm_index_path = dwm_index_path.resolve()
    kdrs = read_json(kdrs_path)
    mapping = read_json(mapping_path)
    index = read_json(dwm_index_path)
    if index.get('result_set_format_version') != 2 or not isinstance(index.get('tests'), list):
        raise ValueError('Ukjent DWM-resultatindeks')
    if kdrs.get('format_version') != 1 or kdrs.get('engine') != 'Saxon':
        raise ValueError('KDRS-resultater må være dokumentert Saxon-eksport v1')
    if mapping.get('format_version') != 1 or not isinstance(mapping.get('comparisons'), list):
        raise ValueError('Ugyldig eksplisitt sammenligningskontrakt')
    if len(mapping['comparisons']) > MAX_ROWS:
        raise ValueError('For mange sammenligninger')
    hashes = kdrs.get('xml_sha256')
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError('KDRS-eksport mangler XML-byteidentitet')
    actual = extract_manifest(xml_root, list(hashes))
    identity_ok = bool(hashes) and all(hashes[name] == actual[name] for name in hashes)
    # Preserve the per-file byte comparison but avoid rehashing the same
    # multi-GB XML for each archive part and metric (thousands of U2 rows).
    hash_cache = {(xml_root.resolve() / name).resolve(): value
                  for name, value in actual.items()}

    def current_hash(path: Path) -> str:
        resolved = path.resolve()
        if resolved not in hash_cache:
            hash_cache[resolved] = digest(resolved)
        return hash_cache[resolved]

    # Duplicate test IDs are ambiguous; last-entry-wins would be unsafe.
    by_id = {}
    for entry in index['tests']:
        if not isinstance(entry, dict) or not isinstance(entry.get('test_id'), str):
            raise ValueError('Ugyldig DWM-indeksrad')
        if entry['test_id'] in by_id:
            raise ValueError('Duplisert DWM test-ID i resultatindeks')
        by_id[entry['test_id']] = entry
    jobs = kdrs.get('jobs') if isinstance(kdrs.get('jobs'), dict) else {}
    results = []
    seen = set()
    for item in mapping['comparisons']:
        if not isinstance(item, dict):
            raise ValueError('Ugyldig sammenligningsrad')
        job_id = str(item.get('job_id', ''))
        test_id = str(item.get('test_id', ''))
        kp = str(item.get('kdrs_path', ''))
        dp = str(item.get('dwm_path', ''))
        key = (job_id, test_id, kp, dp)
        if key in seen:
            raise ValueError('Duplikat sammenligningsdefinisjon')
        seen.add(key)
        row = dict(job_id=job_id, test_id=test_id, kdrs_path=kp, dwm_path=dp,
                   profile=item.get('profile') or jobs.get(job_id, {}).get('source_profile') or '',
                   archive_part_index=(item.get('archive_part') or {}).get('index') if isinstance(item.get('archive_part'), dict) else '',
                   archive_part_title=(item.get('archive_part') or {}).get('title') if isinstance(item.get('archive_part'), dict) else '',
                   status='NOT_COMPARABLE', reason='')
        dwm = by_id.get(test_id)
        if not identity_ok:
            row['reason'] = 'kdrs_xml_sha256_mismatch'
        elif not dwm or dwm.get('status') != 'ok':
            row['reason'] = 'dwm_test_missing_or_not_ok'
        elif job_id not in jobs:
            row['reason'] = 'kdrs_job_missing'
        else:
            f = safe_result_file(dwm_index_path.parent, str(dwm.get('file', '')))
            if not f.is_file():
                row['reason'] = 'dwm_result_file_missing'
            else:
                record = read_json(f)
                xml_name = record.get('source_xml')
                src = record.get('source_path')
                # No trust in a filename alone: verify DWM source *bytes* today.
                if record.get('test_id') != test_id or record.get('status') != 'ok':
                    row['reason'] = 'dwm_result_identity_invalid'
                elif xml_name not in hashes or not src or not Path(src).is_file():
                    row['reason'] = 'dwm_xml_identity_unavailable'
                elif current_hash(Path(src)) != hashes[xml_name]:
                    row['reason'] = 'dwm_xml_sha256_mismatch'
                elif jobs[job_id].get('source_xml') not in (None, xml_name):
                    row['reason'] = 'kdrs_dwm_source_xml_mismatch'
                else:
                    # An archive-part scalar is never paired merely because
                    # its numeric index and count happen to match. Require
                    # explicit identity with both recorded result objects.
                    kpart = re.fullmatch(r'metrics\.archive_parts\.(\d+)\.values\.[A-Za-z_][A-Za-z_0-9]*', kp)
                    dpart = re.fullmatch(r'archive_parts\.(\d+)\.values\.[A-Za-z_][A-Za-z_0-9]*', dp)
                    part_comparison = ('archive_parts.' in kp or 'archive_parts.' in dp or
                                       item.get('archive_part') is not None)
                    guard_ok = True
                    if part_comparison:
                        if not kpart or not dpart or kpart.group(1) != dpart.group(1):
                            row['reason'] = 'archive_part_mapping_path_invalid'
                            guard_ok = False
                        else:
                            expected = item.get('archive_part')
                            i = int(kpart.group(1))
                            kid = get_path(jobs[job_id], f'metrics.archive_parts.{i}.archive_part')
                            did = get_path(record.get('values', {}), f'archive_parts.{i}.archive_part')
                            if (not isinstance(expected, dict) or
                                    not isinstance(kid, dict) or not isinstance(did, dict) or
                                    not isinstance(expected.get('index'), int) or
                                    expected.get('index') != i + 1 or
                                    not isinstance(expected.get('title'), str) or
                                    not expected['title'] or
                                    any(obj.get('index') != expected['index'] or
                                        obj.get('title') != expected['title']
                                        for obj in (kid, did)) or
                                    did.get('system_id') != expected.get('system_id')):
                                row['reason'] = 'archive_part_identity_mismatch'
                                guard_ok = False
                    if guard_ok:
                        lhs = get_path(jobs[job_id], kp)
                        rhs = get_path(record.get('values', {}), dp)
                        if lhs is MISSING or rhs is MISSING:
                            row['reason'] = 'metric_not_found'
                        else:
                            row['kdrs_value'] = lhs
                            row['dwm_value'] = rhs
                            row['status'] = 'MATCH_PROVISIONAL' if canonical(lhs) == canonical(rhs) else 'MISMATCH_PROVISIONAL'
        results.append(row)
    counts = Counter(r['status'] for r in results)
    total = len(results)
    status = 'REVIEW_REQUIRED'
    if total and counts['MATCH_PROVISIONAL'] == total and mapping.get('scope') == 'complete_legacy_jobs':
        # This is per explicitly declared metrics; it cannot prove full XPath
        # semantic equivalence unless all originals and outputs are covered.
        status = 'ALL_DECLARED_METRICS_MATCH_PROVISIONAL' 
    return {'report_type': REPORT_TYPE, 'format_version': 1,
            'kdrs_export_sha256': digest(kdrs_path),
            'dwm_index_sha256': digest(dwm_index_path),
            'comparison_contract_sha256': digest(mapping_path),
            'source_xml_hashes_match_kdrs_export': identity_ok,
            'comparison_scope': mapping.get('scope', 'partial'),
            'provenance_warning': 'DWM kildefilsti og gjeldende bytehash beviser ikke historisk byteidentitet ved kjøring; krever uavhengig kjøringsattestasjon',
            'summary': {'rows': total, 'provisional_matches': counts['MATCH_PROVISIONAL'],
                        'provisional_mismatches': counts['MISMATCH_PROVISIONAL'],
                        'not_comparable': counts['NOT_COMPARABLE'],
                        'by_profile': {profile: {
                            'rows':sum(row['profile']==profile for row in results),
                            'matches':sum(row['profile']==profile and row['status']=='MATCH_PROVISIONAL' for row in results),
                            'mismatches':sum(row['profile']==profile and row['status']=='MISMATCH_PROVISIONAL' for row in results),
                            'not_comparable':sum(row['profile']==profile and row['status']=='NOT_COMPARABLE' for row in results),
                        } for profile in sorted({row['profile'] for row in results})},
                        'status': status, 'normative_coverage_verified': False,
                        'whole_standard_saxon_lxml_parity_verified': False,
                        'execution_time_source_identity_attested': False},
            'comparisons': results}


def write_report(report: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    if any((output_dir / name).exists() for name in OUTPUTS):
        raise FileExistsError('a11-rapporter finnes allerede; bruk en ny output-dir')
    (output_dir / OUTPUTS[0]).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with (output_dir / OUTPUTS[1]).open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'profile', 'job_id', 'test_id', 'archive_part_index', 'archive_part_title',
            'kdrs_path', 'dwm_path', 'status', 'reason', 'kdrs_value', 'dwm_value',
        ])
        writer.writeheader()
        for row in report['comparisons']:
            cells = {}
            for key in writer.fieldnames:
                value = row.get(key, '')
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False, sort_keys=True)
                elif value is None:
                    value = ''
                cell = str(value)
                # Avoid spreadsheet formula execution when CSV is opened in Excel.
                if cell.startswith(('=', '+', '-', '@')):
                    cell = "'" + cell
                cells[key] = cell
            writer.writerow(cells)
    s = report['summary']
    profile_lines = ''.join(
        f"- {profile or 'UKJENT'}: {v['rows']} rader, "
        f"{v['matches']} MATCH_PROVISIONAL, {v['mismatches']} MISMATCH_PROVISIONAL, "
        f"{v['not_comparable']} NOT_COMPARABLE\n"
        for profile, v in s.get('by_profile', {}).items()
    )
    (output_dir / OUTPUTS[2]).write_text(
        '# Noark 5 a11 – Saxon/lxml-regresjon\n\n'
        f"Sammenligninger: {s['rows']}; MATCH: {s['provisional_matches']}; MISMATCH: {s['provisional_mismatches']}; "
        f"NOT_COMPARABLE: {s['not_comparable']}.\n\n"
        + ('## Per KDRS-profil\n\n' + profile_lines + '\n' if profile_lines else '')
        + 'Ingen automatisk normativ verifikasjon eller full Saxon/lxml-paritet. '
        'MATCH_PROVISIONAL gjelder bare eksplisitt deklarerte felt og gjeldende XML-byteidentitet; historisk kjøringsidentitet er ikke attestert.\n',
        encoding='utf-8')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='a11: dokumentert KDRS/Saxon mot DWM/lxml')
    parser.add_argument('--dwm-index', required=True, type=Path)
    parser.add_argument('--kdrs-results', required=True, type=Path)
    parser.add_argument('--mapping', required=True, type=Path)
    parser.add_argument('--xml-root', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args(argv)
    report = compare(args.dwm_index, args.kdrs_results, args.mapping, args.xml_root)
    write_report(report, args.output_dir)
    for name in OUTPUTS:
        print(args.output_dir / name)
    print(report['summary'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
