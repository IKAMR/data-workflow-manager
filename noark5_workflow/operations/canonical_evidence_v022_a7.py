"""a7 Noark 5 Work-only postprocessing with explicit dependency identifiers.

No Source reads, no source results copied, no automatic approval. The canonical
snapshot is a projection of a *single verified* XPath master. External inputs
are selected via versioned Work manifests and remain source-separated.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import tempfile
from typing import Any

from noark5_workflow.core.context import OperationContext
from noark5_workflow.core.operation import BaseOperation, ExecutionTarget, OperationDefinition
from noark5_workflow.core.result import OperationResult


ROOT_NAME = 'noark5_evidence'
MAX_CANDIDATES = 80
MAX_JSON = 100_000_000


class EvidenceError(ValueError):
    pass


def _read(path: Path, *, limit: int = MAX_JSON) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise EvidenceError('Utrygg, manglende eller for stor evidensfil: ' + path.name)
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        raise EvidenceError('Evidensfilen er ikke et JSON-objekt: ' + path.name)
    return data


def _hash(path: Path) -> str:
    h = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _source_token(value: object) -> str:
    # Supports preserved native Windows paths when a Work ZIP is inspected on Unix.
    return str(value or '').strip().replace('\\', '/').rstrip('/').casefold()


def _within(root: Path, value: str | Path) -> Path:
    s = str(value).replace('\\', '/')
    if s.startswith('/') or ':' in s.split('/')[0] or '..' in s.split('/'):
        raise EvidenceError('Evidenssti er ikke en sikker Work-relativ sti: ' + str(value))
    path = root.joinpath(*[p for p in s.split('/') if p])
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise EvidenceError('Evidens peker utenfor Work: ' + str(value))
    return path


def _work_identity(work: Path, claimed_job: str = '') -> tuple[Path, dict]:
    from noark5_workflow.analysis.canonical_results import _validate_work
    root, identity = _validate_work(work)
    if claimed_job and identity['job_id'] != claimed_job:
        raise EvidenceError('Work-Jobb-ID stemmer ikke med aktiv jobb.')
    return root, identity


def _members(root: Path, pattern: str) -> list[Path]:
    base = root / pattern.split('/')[0]
    if not base.is_dir() or base.is_symlink():
        return []
    paths = sorted(root.glob(pattern))
    if len(paths) > MAX_CANDIDATES:
        raise EvidenceError('For mange historiske evidenskandidater. Velg kjoregrunnlag manuelt.')
    return [p for p in paths if p.is_file() and not p.is_symlink()
            and p.resolve().is_relative_to(root.resolve())]


def _select_master(root: Path, identity: dict, run_id: str = '') -> Path:
    choices = []
    for path in _members(root, 'noark5_tests/xpath/*/master-results.json'):
        run = path.parent
        manifest = _read(run / 'artifact_manifest.json')
        if (manifest.get('operation_id') != 'run_noark5_xpath_tests_2026'
                or manifest.get('job_id') != identity['job_id']
                or manifest.get('job_uid') != identity['job_uid']):
            continue
        job = _read(root / 'job.json').get('job') or {}
        if (_source_token(manifest.get('source_extraction')) !=
                _source_token(job.get('source_extraction') or job.get('source_root'))):
            raise EvidenceError('XPath-master har en annen Source enn denne Work-jobben.')
        master = _read(path)
        if (master.get('format_version') != 1 or
                (master.get('source') or {}).get('execution_profile') != 'normal' or
                not isinstance(master.get('tests'), list)):
            continue
        choices.append((str(manifest.get('run_id') or ''), path))
    if not choices:
        raise EvidenceError('Ingen validert ordinær XPath-master i denne Work-jobben.')
    matching = [p for rid, p in choices if run_id and rid == run_id]
    if len(matching) == 1:
        return matching[0]
    # Previous completed jobs may have a single unambiguous historical run.
    if len(choices) == 1:
        return choices[0][1]
    # If several runs exist, use the depot report's explicit source run ONLY
    # if it resolves to exactly one of the validated candidates.
    reports = _members(root, 'noark5_reports/depot_validation/*/depot_validation_report.json')
    if len(reports) == 1:
        report = _read(reports[0])
        ref = str((report.get('evidence') or {}).get('source_xpath_run') or '')
        linked = [p for _, p in choices if _source_token(p.parent) == _source_token(ref)]
        if len(linked) == 1:
            return linked[0]
    raise EvidenceError('Flere ordinare XPath-kjoringer i Work: kildevalg maa avklares, ingen automatisk blanding.')


def _select_external_sources(root: Path, identity: dict) -> dict[str, dict]:
    """One verified imported Arkade set and one Siegfried run, if available."""
    chosen: dict[str, dict] = {}
    arkade = []
    for path in _members(root, 'external_evidence/arkade5/*/manifest.json'):
        m = _read(path)
        by = m.get('imported_by') or {}
        if str(by.get('job_id') or '') != identity['job_id']:
            continue
        normalized = _within(root, str(m.get('normalized_file') or ''))
        from noark5_workflow.analysis.canonical_external_import_v0115_a10 import MAX_SOURCE_NORMALIZED
        if normalized.stat().st_size > MAX_SOURCE_NORMALIZED:
            from noark5_workflow.analysis.streaming_arkade import has_normalized_arkade_tests
            if not has_normalized_arkade_tests(normalized):
                continue
        else:
            doc = _read(normalized)
            if (str(doc.get('source_system') or '') != 'Arkade 5' or
                    not isinstance(doc.get('tests'), list)):
                continue
        s = m.get('source') or {}
        original = _within(root, str(s.get('preserved_file') or ''))
        if str(s.get('sha256') or '') != _hash(original):
            raise EvidenceError('Arkade-kildehash stemmer ikke med originalen i Work.')
        candidates = [('arkade_noark', normalized)]
        rel = ((m.get('pronom_evidence') or {}).get('statistics') or {}).get('normalized_file')
        if rel:
            stat = _within(root, str(rel))
            if stat.is_file():
                candidates.append(('arkade_pronom', stat))
        arkade.append((str(m.get('imported_at') or ''),path, candidates))
    if len(arkade) > 1:
        arkade.sort(key=lambda x:(x[0],x[1].as_posix()))
        if not arkade[-1][0] or arkade[-1][0] == arkade[-2][0]:
            raise EvidenceError('Flere Arkade-importer uten entydig siste tidspunkt; kilden maa velges manuelt.')
    if arkade:
        _, path, candidates = arkade[-1]
        for kind, candidate in candidates:
            chosen[kind] = {'file': candidate.relative_to(root).as_posix(),
                            'sha256': _hash(candidate),
                            'manifest': path.relative_to(root).as_posix(),
                            'manifest_sha256': _hash(path)}
    sf = []
    for path in _members(root, 'external_evidence/siegfried/*/manifest.json'):
        m = _read(path)
        if str(m.get('job_id') or '') != identity['job_id']:
            continue
        if str(m.get('job_uid') or '') not in ('', identity['job_uid']):
            raise EvidenceError('Siegfried-historikk tilhorer en annen varig jobb-ID.')
        job = _read(root / 'job.json').get('job') or {}
        if (_source_token(m.get('source_root')) !=
                _source_token(job.get('source_extraction') or job.get('source_root'))):
            raise EvidenceError('Siegfried-rapporten gjelder en annen Source.')
        stat = path.parent / 'pronom_statistics.json'
        if stat.is_file() and not stat.is_symlink():
            statistics = _read(stat)
            if ((m.get('run_id') and statistics.get('run_id') and
                 m['run_id'] != statistics['run_id']) or
                (type(m.get('files_total')) is int and
                 type(statistics.get('files_total')) is int and
                 m['files_total'] != statistics['files_total'])):
                raise EvidenceError('Siegfried-manifest og PRONOM-statistikk gjelder ulike kjøringer.')
            sf.append((str(m.get('created_at') or ''),path,stat))
    if sf:
        sf.sort(key=lambda item: (item[0], item[1].as_posix()))
        if len(sf) > 1 and sf[-1][0] == sf[-2][0]:
            raise EvidenceError('Flere Siegfried-kjoringer med samme tidspunkt.')
        _, manifest, stat = sf[-1]
        chosen['siegfried_pronom'] = {
            'file': stat.relative_to(root).as_posix(), 'sha256': _hash(stat),
            'manifest': manifest.relative_to(root).as_posix(),
            'manifest_sha256': _hash(manifest),
        }
    return chosen


def _publish_json(root: Path, relative: str, document: dict) -> Path:
    target = _within(root, relative)
    parent = target.parent
    if target.is_symlink() or parent.is_symlink():
        raise EvidenceError('Resultatmappen er en symbolsk lenke.')
    parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    if relative.endswith('/canonical-external-analysis.json'):
        from noark5_workflow.analysis.canonical_external_import_v0115_a10 import MAX_ANALYSIS_OUTPUT
        if len(data) > MAX_ANALYSIS_OUTPUT:
            selected = ', '.join((item.get('evidence') or {}).get('work_relative_path', '')
                                 for item in (document.get('sources') or [])[:3])
            raise EvidenceError(f'Generert ekstern analyse er {len(data)} bytes; '
                                f'grensen er {MAX_ANALYSIS_OUTPUT} bytes. '
                                f'Valgte kilder: {selected}. Reduser kildeutvalget.')
    if target.is_file():
        prior = target.read_bytes()
        if prior == data:
            return target
        history = parent / 'history'
        if history.is_symlink():
            raise EvidenceError('Historikkmappen er en symbolsk lenke.')
        history.mkdir(exist_ok=True)
        prior_hash = sha256(prior).hexdigest()
        old = history / (target.stem + '-' + prior_hash + '.json')
        if not old.exists():
            fd, tempname = tempfile.mkstemp(prefix='.history-', dir=history)
            try:
                with os.fdopen(fd, 'wb') as f:
                    f.write(prior)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tempname, old)
            finally:
                if os.path.exists(tempname):
                    os.unlink(tempname)
    fd, tempname = tempfile.mkstemp(prefix='.a7-', dir=parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tempname, target)
    finally:
        if os.path.exists(tempname):
            os.unlink(tempname)
    return target


def build_evidence(work: str | Path, *, job_id: str = '', run_id: str = '') -> dict:
    from noark5_workflow.analysis.canonical_results import build_canonical_results
    root, identity = _work_identity(Path(work), job_id)
    master = _select_master(root, identity, run_id)
    doc = build_canonical_results(root, master_paths=(master,), write=False)
    external = _select_external_sources(root, identity)
    # Native external results are references, NOT invented canonical tests.
    doc['a7_evidence_sources'] = external
    doc['a7_dependency_no'] = 210
    doc['a7_source_coverage'] = {
        'dwm_xpath': 'verified',
        'arkade_noark': 'linked' if 'arkade_noark' in external else 'not_available',
        'arkade_pronom': 'linked' if 'arkade_pronom' in external else 'not_available',
        'siegfried_pronom': 'linked' if 'siegfried_pronom' in external else 'not_available',
        'fully_verified_noark5': False,
        'approval': None,
    }
    doc['limitations'].append('A7 external references are source-separated, not canonical observations')
    target = _publish_json(root, ROOT_NAME + '/canonical-results.json', doc)
    return {'path': str(target), 'observations': len(doc['observations']),
            'external_sources': list(external), 'job_uid': identity['job_uid']}


def _dwm_siegfried_statistics(doc: dict) -> dict | None:
    """Compatibility wrapper for callers that handle ``EvidenceError``."""
    from noark5_workflow.analysis.siegfried_statistics import summarize_dwm_siegfried_statistics
    try:
        return summarize_dwm_siegfried_statistics(doc)
    except ValueError as exc:
        raise EvidenceError(str(exc)) from exc


def analyze_external(work: str | Path, *, job_id: str = '') -> dict:
    from noark5_workflow.analysis.canonical_external_import_v0115_a10 import analyze_external_results
    root, identity = _work_identity(Path(work), job_id)
    doc = _read(root / ROOT_NAME / 'canonical-results.json')
    if (doc.get('extraction') or {}).get('stable_id') != identity['job_uid']:
        raise EvidenceError('Kanonisk evidens og aktiv Work-jobb stemmer ikke.')
    expected = doc.get('a7_evidence_sources') or {}
    selected = []
    for name in ('arkade_noark', 'arkade_pronom', 'siegfried_pronom'):
        info = expected.get(name)
        if not info:
            continue
        path = _within(root, info['file'])
        if _hash(path) != info['sha256']:
            raise EvidenceError('Evidens er endret siden kanonisering: ' + name)
        selected.append(info['file'])
    if selected:
        external = analyze_external_results(root, tuple(selected), write=False)
        for item in external.get('sources') or ():
            reference = item.get('evidence') or {}
            rel = reference.get('work_relative_path')
            if not rel or not any(rel == selected_path for selected_path in selected):
                raise EvidenceError('Ekstern analyse har returnert en ukjent Work-kilde.')
        counted_unparsed = sum((src.get('analysis') or {}).get('interpretation') == 'not_parsed'
                               for src in external.get('sources') or ())
        external['summary']['unparsed_files'] = counted_unparsed
        external['a7_dependency_no'] = 220
        target = _publish_json(root, ROOT_NAME + '/canonical-external-analysis.json', external)
        return {'path': str(target), 'sources': len(selected),
                'unparsed': counted_unparsed}
    # Honest absence: do not invent empty analysis as a successful import.
    return {'path': None, 'sources': 0, 'unparsed': 0,
            'note': 'Ingen eksterne resultater er dokumentert i valgt Work'}


def audit_evidence(work: str | Path, *, job_id: str = '') -> dict:
    root, identity = _work_identity(Path(work), job_id)
    canonical = _read(root / ROOT_NAME / 'canonical-results.json')
    if (canonical.get('extraction') or {}).get('stable_id') != identity['job_uid']:
        raise EvidenceError('Kanonisk evidens tilhorer en annen jobb.')
    sources = canonical.get('a7_evidence_sources') or {}
    checked = []
    for kind, source in sources.items():
        path = _within(root, source['file'])
        manifest = _within(root, source['manifest'])
        if (_hash(path) != source['sha256'] or
                _hash(manifest) != source['manifest_sha256']):
            raise EvidenceError('Kilde er endret etter sammenstilling: ' + kind)
        checked.append({'kind': kind, 'path': source['file'], 'sha256': source['sha256']})
    external = root / ROOT_NAME / 'canonical-external-analysis.json'
    status = 'not_analyzed'
    if external.is_file() and not external.is_symlink():
        from noark5_workflow.analysis.canonical_external_import_v0115_a10 import MAX_ANALYSIS_OUTPUT
        data = _read(external, limit=MAX_ANALYSIS_OUTPUT)
        ref = data.get('canonical_reference') or {}
        if data.get('extraction_stable_id') != identity['job_uid'] or \
           ref.get('sha256') != _hash(root / ROOT_NAME / 'canonical-results.json'):
            raise EvidenceError('Ekstern analyse er foreldet i forhold til kanonisk evidens.')
        status = 'analyzed'
    workflow = list((_read(root / 'job.json').get('job') or {}).get('workflow_ids') or ())
    selected = set(workflow)
    from app.workflow_dependencies_v022_a7 import BY_ID, validate_dependencies
    dependency_errors = validate_dependencies(workflow)
    if dependency_errors:
        raise EvidenceError('Ugyldige avhengigheter i lagret Work-jobb: ' + ' | '.join(dependency_errors))
    dependency_map = [
        {'dependency_no': BY_ID[op].number, 'operation_id': op,
         'phase': BY_ID[op].phase,
         'requires_after': [n for n in BY_ID[op].follows
                            if any(BY_ID[item].number == n for item in workflow if item in BY_ID)]}
        for op in workflow if op in BY_ID
    ]
    expected = {'arkade_noark': 'arkade5_noark5_test',
                'arkade_pronom': 'arkade5_pronom_analysis',
                'siegfried_pronom': 'siegfried_pronom_identification'}
    doc = {
        'model_id': 'dwm.noark5.evidence-audit.a7.v1',
        'job_uid': identity['job_uid'], 'job_id': identity['job_id'],
        'dependency_no': 230,
        'workflow_dependency_map': dependency_map,
        'workflow_order_verified': True,
        'canonical_sha256': _hash(root / ROOT_NAME / 'canonical-results.json'),
        'external_analysis_status': status,
        'verified_references': checked,
        'missing_source_families': [kind for kind, op in expected.items()
                                    if op in selected and kind not in sources],
        'not_configured_source_families': [kind for kind, op in expected.items()
                                          if op not in selected],
        'status': ('missing_expected_sources' if any(op in selected and kind not in sources
                         for kind,op in expected.items()) else
                   'sources_linked_needs_review' if checked else 'internal_only_needs_review'),
        'technical_approval': None, 'depot_approval': None,
        'notes': 'Manglende kildefamilie betyr ukjent, aldri null eller godkjent.',
    }
    target = _publish_json(root, ROOT_NAME + '/evidence-audit.json', doc)
    return {'path': str(target), 'linked': len(checked),
            'missing': list(doc['missing_source_families']), 'status': doc['status']}


def _build_qa_basis_legacy_v022_a7(work: str | Path, *, job_id: str = '') -> dict:
    from noark5_workflow.reporting.qa_workflow_v022_a3 import (
        build_review_snapshot_v022_a3, finding_summary,
    )
    root, identity = _work_identity(Path(work), job_id)
    audit = _read(root / ROOT_NAME / 'evidence-audit.json')
    if audit['job_uid'] != identity['job_uid']:
        raise EvidenceError('Evidensrevisjonen tilhorer feil jobb.')
    snapshot = build_review_snapshot_v022_a3(work=root)
    summary = finding_summary(root, snapshot)
    doc = {'model_id': 'dwm.noark5.qa-basis.draft.a7.v1',
           'dependency_no': 260, 'job_uid': identity['job_uid'],
           'status': 'UTKAST', 'automatic_approval': False,
           'evidence_audit_sha256': _hash(root / ROOT_NAME / 'evidence-audit.json'),
           'depot_report_source': snapshot.get('dwm_report_source'),
           'findings': summary, 'archive_creator_acceptance': None,
           'depot_approval': None,
           'note': 'Faglig godkjenning og endelig rapportpublisering er manuelle handlinger.'}
    target = _publish_json(root, ROOT_NAME + '/qa-basis-draft.json', doc)
    # Readable review basis, not the separately published a3 KS/depot bundle.
    from html import escape
    issues = list(snapshot.get('findings') or ())
    body = ["<!doctype html><html lang='no'><head><meta charset='utf-8'>",
            "<title>Noark 5 KS-grunnlag (UTKAST)</title>",
            "<style>body{font:15px/1.5 Segoe UI,Arial,sans-serif;max-width:1100px;",
            "margin:2em auto;padding:0 1em}li{margin-bottom:1em}</style></head><body>",
            "<h1>KS-grunnlag - UTKAST, IKKE GODKJENT</h1>",
            "<p>Jobb: "+escape(identity['job_id'])+". Ingen automatisk depotgodkjenning.</p>",
            "<p>Antall uavklarte: "+str(summary.get('unreviewed', '?'))+"; ",
            "faglig vurdert: "+str(summary.get('reviewed','?'))+".</p><ol>"]
    for finding in issues[:250]:
        if not isinstance(finding,dict):
            continue
        message = finding.get('message') or finding.get('summary') or ''
        body.append('<li><b>'+escape(str(finding.get('test_id') or ''))+
                    '</b> - '+escape(str(message)[:1600])+'</li>')
    if len(issues)>250:
        body.append('<p>Viser 250 av '+str(len(issues))+' funn. Se fullstendig avviksregister.</p>')
    body.append("</ol><p>Faglig vurdering og publisering krever separat beslutning.</p></body></html>")
    html_target = root / ROOT_NAME / 'qa-basis-draft.html'
    if html_target.is_symlink():
        raise EvidenceError('HTML-utkastet er en utrygg lenke.')
    fd, tempname = tempfile.mkstemp(prefix='.qa-draft-',dir=html_target.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as out:
            out.write(''.join(body))
            out.flush()
            os.fsync(out.fileno())
        os.replace(tempname,html_target)
    finally:
        if os.path.exists(tempname):
            os.unlink(tempname)
    return {'path': str(target), 'html': str(html_target), 'summary': summary,
            'automatic_approval': False}


def build_qa_basis(work: str | Path, *, job_id: str = '') -> dict:
    """A260: stream complete source-bound findings; no 300-row ceiling."""
    from noark5_workflow.reporting.qa_a260_v023_a6 import build_qa_basis_a6
    return build_qa_basis_a6(work, job_id=job_id)


class _BaseEvidenceOperation(BaseOperation):
    raw_result_record = True
    worker = None

    def can_run(self, ctx: OperationContext) -> tuple[bool, str]:
        if ctx.work_operations is None:
            return False, 'Work - operations mangler.'
        if not (Path(ctx.work_operations) / 'job.json').is_file():
            return False, 'Work mangler autoritativ job.json.'
        return True, ''

    def run(self, ctx: OperationContext) -> OperationResult:
        if ctx.work_operations is None:
            return OperationResult(False, 'Work mangler.')
        if ctx.cancelled():
            return OperationResult(False, 'Avbrutt av bruker.')
        try:
            ctx.progress(0.05, self.definition.name)
            output = self.worker(
                ctx.work_operations,
                job_id=str(ctx.metadata.get('job_id') or ''),
                **({'run_id': str(ctx.metadata.get('run_id') or '')}
                   if self.worker is build_evidence else {}),
            )
            if ctx.cancelled():
                return OperationResult(False, 'Avbrutt av bruker.')
            ctx.progress(1.0, self.definition.name + ' fullfort')
            if self.worker is audit_evidence and output.get('missing'):
                return OperationResult(
                    False,
                    'Evidens mangler for valgte kontroller: ' + ', '.join(output['missing']),
                    data=output,
                    outputs=[output['path']],
                )
            return OperationResult(True, self.definition.name + ': gjennomfort, ingen automatisk godkjenning.',
                                   data=output, outputs=([output['path']] if output.get('path') else [])
                                               + ([output['html']] if output.get('html') else []))
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
            return OperationResult(False, self.definition.name + ': ' + str(exc))


class BuildNoark5CanonicalEvidenceOperation(_BaseEvidenceOperation):
    definition = OperationDefinition('build_noark5_canonical_evidence',
        'Kanonisk Noark 5-evidens [A210]',
        'Bygg verifisert intern masterindeks og lenker til eksterne Work-resultater.',
        ExecutionTarget.EITHER, 'Rapport')
    worker = staticmethod(build_evidence)


class AnalyzeNoark5ExternalEvidenceOperation(_BaseEvidenceOperation):
    definition = OperationDefinition('analyze_noark5_external_evidence',
        'Koble Arkade/Siegfried-evidens [A220]',
        'Analyser eksplisitt, kildebundet normalisert evidens fra samme Work.',
        ExecutionTarget.EITHER, 'Rapport')
    worker = staticmethod(analyze_external)


class AuditNoark5EvidenceOperation(_BaseEvidenceOperation):
    definition = OperationDefinition('audit_noark5_evidence',
        'Kontroller evidensdekning [A230]',
        'Verifiser identitet og SHA-256; dokumenter manglende kilder som ukjent.',
        ExecutionTarget.EITHER, 'Rapport')
    worker = staticmethod(audit_evidence)


class BuildNoark5QaDraftOperation(_BaseEvidenceOperation):
    definition = OperationDefinition('build_noark5_qa_draft',
        'Forbered KS-grunnlag (utkast) [A260]',
        'Lag nytt faglig kontrollgrunnlag i Work uten automatisk godkjenning.',
        ExecutionTarget.EITHER, 'Rapport')
    worker = staticmethod(build_qa_basis)
