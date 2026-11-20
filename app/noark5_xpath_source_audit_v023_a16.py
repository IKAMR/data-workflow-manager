"""A16: read-only source/provenance audit for DWM's historical KDRS XPath map.

Confirms the saved source bytes (Git blob SHA-1) and legacy job identities;
reports differences without rewriting XPath expressions or making claims about
Noark normative completeness, Saxon/lxml parity or approval. Optionally checks
all 15 version-specific XSD reference files in IKAMR's source library.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha1, sha256
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any

KDRS_REPOSITORY = 'IKAMR/KDRS_Query'
KDRS_COMMIT = 'a68d809ee04c8aceb75976c668bf9746e26d67cb'
NOARK_REPOSITORY = 'IKAMR/digital-archive-workflow'
NOARK_COMMIT = '8d28e312e1e38af8cb93bfe05cecef11e09af34f'
CATALOG_REL = 'config/noark5/tests/xpath_catalog_2026_05_26.json'
KDRS_FILES = {
    'Standard': ('xml-queries_noark5_2026-05-26.txt', 'f629b073c48ecf19ece748117f91277947303ed5'),
    'U1': ('xml-queries_noark5_2026-05-26_U1.txt', '0233fb5c9b1a9c28454c3ba93ebf745f80f81dfd'),
    'U2': ('xml-queries_noark5_2026-05-26_U2.txt', '051d3da8d247bca7d1629b08254116609778423a'),
}
XSD_BLOBS = {
    '3.1': ('4a4f5fecc912b193782d61c5e194b1f178d515ed',
            '05c7146fd8a43927b0569c19ac1a1b5de9c5ff63',
            '9852c434895246cea3a17acb3531a5823256a980',
            '2620e5dc5544fabf8bc548566b20d54ac7bbbab9',
            '99915b68399b5aa1c8ad7694eec5a78b88363d13'),
    '4.0': ('85a9693b4780aefc4af640afe5913085c638efbb',
            '7d5b5dc85958afeb85be2f44f671673ab525f3e4',
            '028cf97e685995057d0031d308c6f5a763867c2c',
            '37f635e79c1ff88a4d7753f94e7f901bf5d5bfcf',
            'bb54dcf1dd89d9d145e6c52776f7d5aba4ebe8d0'),
    '5.0': ('0a6261fc7856886a1793830b9041ea266794e4c6',
            '1e4846b49255a5ffd1ffee1025d8fe95b1dba73f',
            '78fe38e6db19def7927cc9ef2dde9632a815b290',
            '0e381a644070583d7133f854aec9e6dbe7478fd0',
            '35bfa954bafa1687f0bb422debed97a1f13c3e24'),
}
XSD_NAMES = ('arkivstruktur.xsd', 'endringslogg.xsd', 'loependeJournal.xsd',
             'metadatakatalog.xsd', 'offentligJournal.xsd')
MAX_SOURCE = 2 * 1024 * 1024
MAX_CATALOG = 8 * 1024 * 1024


class XPathSourceAuditError(ValueError):
    pass


def _blob(raw: bytes) -> str:
    """Git blob object identifier (SHA-1) for reproducible source identity."""
    return sha1(b'blob ' + str(len(raw)).encode('ascii') + b'\0' + raw).hexdigest()


def _load_source(path: Path, expected: str, *, repo: str, commit: str, relative: str) -> tuple[dict, str | None]:
    item: dict[str, Any] = {'repository': repo, 'commit': commit,
                            'path': relative, 'expected_git_blob_sha1': expected,
                            'status': 'missing', 'sha256': '', 'bytes': None}
    if not path.is_file() or path.is_symlink():
        return item, None
    size = path.stat().st_size
    if size > MAX_SOURCE:
        item['status'] = 'oversized_reference_copy'
        item['bytes'] = size
        return item, None
    try:
        raw = path.read_bytes()
        text = raw.decode('utf-8-sig')
    except (OSError, UnicodeError):
        item['status'] = 'unreadable'
        return item, None
    item['sha256'] = sha256(raw).hexdigest()
    item['actual_git_blob_sha1'] = _blob(raw)
    item['bytes'] = len(raw)
    item['status'] = ('git_blob_verified' if item['actual_git_blob_sha1'] == expected
                      else 'source_bytes_differ')
    return item, text


def _jobs(text: str) -> list[dict]:
    """Read only actual [XML_QUERY] definitions and their legacy switches."""
    result = []
    blocks = re.split(r'(?m)^\[XML_QUERY\][ \t]*\r?\n', text)
    for block in blocks[1:]:
        # Subsequent [SQL_QUERY] etc. aren't XML definitions.
        block = re.split(r'(?m)^\[[A-Z_]+\][ \t]*$', block, maxsplit=1)[0]
        def field(key: str) -> str:
            match = re.search(r'(?m)^' + re.escape(key) + r'[ \t]*=[ \t]*([^\r\n#]*)', block)
            return match.group(1).strip() if match else ''
        job_id, enabled = field('job_id'), field('job_enabled')
        if (not job_id or not re.fullmatch(r'[A-Za-z0-9_.-]+', job_id)
                or not enabled.isdigit() or '#START#' not in block or '#STOP#' not in block):
            raise XPathSourceAuditError('Ufullstendig KDRS XML_QUERY-blokk')
        result.append({'job_id': job_id, 'job_enabled': int(enabled),
                       'job_name': field('job_name')})
    return result


def _catalog(root: Path) -> tuple[list[dict], dict]:
    path = root / CATALOG_REL
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_CATALOG:
        raise XPathSourceAuditError('DWM XPath-katalogen mangler eller er for stor')
    raw = path.read_bytes()
    try:
        doc = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise XPathSourceAuditError('DWM XPath-katalogen er uleselig') from exc
    if (not isinstance(doc, dict) or doc.get('catalog_id') != 'noark5-kdrs-query-2026-05-26'
            or not isinstance(doc.get('tests'), list)):
        raise XPathSourceAuditError('Ukjent XPath-katalogmodell')
    return doc['tests'], {'path': CATALOG_REL, 'sha256': sha256(raw).hexdigest(),
                          'bytes': len(raw), 'catalog_status': doc.get('status')}


def audit_sources(repo_root: str | Path, *, kdrs_directory: str | Path | None = None,
                  noark_root: str | Path | None = None) -> dict:
    """Inventory and identity-check only; all original files remain read-only."""
    repo = Path(repo_root).resolve(strict=True)
    kdrs = Path(kdrs_directory).resolve(strict=True) if kdrs_directory else repo / 'docs/reference/kdrs-query'
    tests, catalog = _catalog(repo)
    by_legacy: dict[str, dict] = {}
    for t in tests:
        if not isinstance(t, dict) or not isinstance(t.get('legacy'), dict):
            raise XPathSourceAuditError('Katalogen inneholder ugyldig testpost')
        legacy_id = str(t['legacy'].get('job_id') or '')
        if not legacy_id or legacy_id in by_legacy:
            raise XPathSourceAuditError('Katalogen har manglende eller duplisert legacy jobb-ID')
        by_legacy[legacy_id] = t

    sources = []
    all_jobs: list[dict] = []
    issues: list[dict] = []
    observed_ids: set[str] = set()
    for profile, (filename, expected) in KDRS_FILES.items():
        item, raw = _load_source(kdrs / filename, expected, repo=KDRS_REPOSITORY,
                                  commit=KDRS_COMMIT, relative='doc/' + filename)
        item['profile'] = profile
        sources.append(item)
        if raw is None:
            issues.append({'kind': 'source_missing_or_unverified', 'source': profile,
                           'job_id': '', 'detail': item['status']})
            continue
        ids_here: set[str] = set()
        try:
            jobs = _jobs(raw)
        except XPathSourceAuditError as exc:
            issues.append({'kind': 'unreadable_legacy_definitions', 'source': profile,
                           'job_id': '', 'detail': str(exc)})
            continue
        item['xml_query_count'] = len(jobs)
        for job in jobs:
            ident = job['job_id']
            if ident in ids_here:
                issues.append({'kind': 'duplicate_source_job', 'source': profile,
                               'job_id': ident, 'detail': 'Duplisert i kildeprofil'})
            ids_here.add(ident)
            observed_ids.add(ident)
            match = by_legacy.get(ident)
            row = {'profile': profile, **job, 'catalog_test_id': match.get('test_id') if match else '',
                   'catalog_status': match.get('status') if match else '',
                   'catalog_enabled': (match.get('legacy') or {}).get('job_enabled') if match else None,
                   'source_verified': item['status'] == 'git_blob_verified'}
            all_jobs.append(row)
            if not match:
                issues.append({'kind': 'missing_catalog_mapping', 'source': profile,
                               'job_id': ident, 'detail': 'KDRS-jobb mangler DWM-testidentitet'})
            elif row['catalog_enabled'] != job['job_enabled']:
                issues.append({'kind': 'execution_hint_differs', 'source': profile,
                               'job_id': ident, 'detail':
                               f"KDRS job_enabled={job['job_enabled']}, DWM={row['catalog_enabled']}"})
    extras = sorted(k for k in by_legacy if k not in observed_ids)
    for ident in extras:
        if ident.startswith('DWM-'):
            continue  # Explicitly supplemental; no historical KDRS query.
        issues.append({'kind': 'catalog_without_kdrs_definition', 'source': 'catalog',
                       'job_id': ident, 'detail': 'Registrert test uten historisk job-ID'})

    xsd_sources = []
    if noark_root is not None:
        base = Path(noark_root).resolve(strict=True)
        for version, shas in XSD_BLOBS.items():
            for name, expected in zip(XSD_NAMES, shas):
                rel = f'docs/kilder/noark/noark5/v{version}/schemas/{name}'
                record, _ = _load_source(base / rel, expected, repo=NOARK_REPOSITORY,
                                          commit=NOARK_COMMIT, relative=rel)
                record['noark_version'] = version
                xsd_sources.append(record)
                if record['status'] != 'git_blob_verified':
                    issues.append({'kind': 'noark_xsd_source_unverified',
                                   'source': version, 'job_id': name,
                                   'detail': record['status']})

    identities = [x for x in all_jobs if x['profile'] == 'Standard']
    verified = all(s['status'] == 'git_blob_verified' for s in sources)
    unmapped = sum(i['kind'] in ('missing_catalog_mapping','catalog_without_kdrs_definition') for i in issues)
    status = ('identity_checked_with_open_semantic_qa'
              if verified and unmapped == 0 and
              (noark_root is None or all(x['status'] == 'git_blob_verified' for x in xsd_sources))
              else 'incomplete_or_source_changed')
    return {
        'model_id': 'dwm.noark5.xpath-source-audit.a16.v1', 'status': status,
        'automatic_approval': False, 'semantic_parity_verified': False,
        'normative_requirement_coverage_verified': False,
        'catalog': catalog,
        'kdrs_sources': sources, 'source_commit': KDRS_COMMIT,
        'standard_legacy_jobs': len(identities),
        'distinct_legacy_jobs': len(observed_ids),
        'catalog_tests': len(tests), 'catalog_supplemental_tests': sorted(k for k in extras if k.startswith('DWM-')),
        'job_rows': all_jobs, 'issues': issues,
        'noark_source_commit': NOARK_COMMIT,
        'noark_xsd_inventory': xsd_sources if noark_root is not None else None,
        'noark_xsd_status': ('not_assessed' if noark_root is None else
                              'all_blobs_match' if all(x['status'] == 'git_blob_verified' for x in xsd_sources)
                              else 'source_mismatch_or_missing'),
        'limitations': [
            'Legacy job ID and job_enabled comparison is not XPath semantic equivalence.',
            'U1/U2 can be regression references with intentionally different execution hints.',
            'Git blob SHA-1 establishes pinned Git object identity; SHA-256 is reported separately.',
            'XSD file identity is not validation of extraction XML or proof of normative completeness.',
            'Noark 3.1, 4.0 and 5.0 must not be merged without documented source QA.',
        ],
    }


def _csv_safe(value: Any) -> str:
    text = '' if value is None else str(value)
    # Excel and compatible tools may treat leading whitespace then a formula
    # sigil as executable spreadsheet content. The original evidence is not
    # changed; only the CSV presentation is made inert.
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description='Kildebundet QA for KDRS Standard/U1/U2 og valgfri Noark XSD-inventar')
    p.add_argument('--repo-root', default=str(Path(__file__).resolve().parents[1]))
    p.add_argument('--kdrs-directory', help='Mappe med originalfilene, for eksempel KDRS_Query/doc')
    p.add_argument('--noark-root', help='Lokal digital-archive-workflow-reporot for 15 XSD SHA-kontroller')
    p.add_argument('--output-dir', required=True, help='Ny resultatmappe utenfor kildekatalogen')
    args = p.parse_args(argv)
    report = audit_sources(args.repo_root, kdrs_directory=args.kdrs_directory,
                           noark_root=args.noark_root)
    root = Path(args.output_dir).resolve(strict=False)
    if root.exists():
        raise XPathSourceAuditError('Resultatmappen finnes allerede: ' + str(root))
    if not root.parent.is_dir() or root.parent.is_symlink():
        raise XPathSourceAuditError('Resultatmappens overordnede mappe må eksistere')
    for protected in (Path(args.repo_root).resolve(strict=True),
                      Path(args.kdrs_directory).resolve(strict=True) if args.kdrs_directory else None,
                      Path(args.noark_root).resolve(strict=True) if args.noark_root else None):
        if protected and (root == protected or root.is_relative_to(protected)):
            raise XPathSourceAuditError('Resultatmappen må ligge utenfor kilderepoene')
    stage = Path(tempfile.mkdtemp(prefix='.dwm-a16-', dir=root.parent))
    try:
        (stage/'a16-xpath-source-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n',encoding='utf-8')
        with (stage/'a16-kdrs-mapping.csv').open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=('profile','job_id','job_enabled','job_name',
                                                   'catalog_test_id','catalog_status','catalog_enabled','source_verified'))
            writer.writeheader()
            for item in report['job_rows']:
                writer.writerow({k: _csv_safe(item[k]) for k in writer.fieldnames})
        stage.rename(root)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    print(f"A16 XPath-kildeavstemming: {report['standard_legacy_jobs']} Standard-jobber, "
          f"{report['catalog_tests']} DWM-tester, {len(report['issues'])} QA-punkter, "
          f"status={report['status']}")
    return 0 if report['status'] == 'identity_checked_with_open_semantic_qa' else 2


if __name__ == '__main__':
    raise SystemExit(main())
