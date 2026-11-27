"""A20: attach independent Arkade PRONOM, refresh derived A210 on A220 resume."""
from pathlib import Path
from noark5_workflow.core.result import OperationResult
from noark5_workflow.external_evidence.arkade5_pronom_standalone_v027_a20 import (
    import_preserved_pronom, verify_standalone_reference,
)
from noark5_workflow.operations import canonical_evidence_v022_a7 as base
from noark5_workflow.operations import canonical_evidence_v026_a3 as previous


def _refresh(root, identity):
    relative = base.ROOT_NAME + '/canonical-results.json'
    original = base._read(root / relative)
    if (original.get('extraction') or {}).get('stable_id') != identity['job_uid']:
        raise base.EvidenceError('Kanonisk evidens tilhorer en annen jobb.')
    sources = original.get('a7_evidence_sources') or {}
    for source in sources.values():
        for key, digest in (('file', 'sha256'), ('manifest', 'manifest_sha256')):
            if base._hash(base._within(root, source[key])) != source[digest]:
                raise base.EvidenceError('Eksisterende evidens er endret: ' + source[key])
    if 'arkade_pronom' in sources:
        verify_standalone_reference(root, sources['arkade_pronom'],
                                    job_id=identity['job_id'], job_uid=identity['job_uid'])
        return False
    candidate = import_preserved_pronom(root, job_id=identity['job_id'], job_uid=identity['job_uid'])
    if candidate is None:
        return False
    original.setdefault('a7_evidence_sources', {})['arkade_pronom'] = candidate
    coverage = original.setdefault('a7_source_coverage', {})
    coverage.update(arkade_pronom='linked', fully_verified_noark5=False, approval=None)
    base._publish_json(root, relative, original)
    return True


def build_evidence(work, *, job_id='', run_id=''):
    result = previous.build_evidence(work, job_id=job_id, run_id=run_id)
    root, identity = base._work_identity(Path(work), job_id)
    if _refresh(root, identity):
        result['external_sources'] = list(base._read(root / base.ROOT_NAME / 'canonical-results.json')['a7_evidence_sources'])
    return result


def analyze_external(work, *, job_id=''):
    root, identity = base._work_identity(Path(work), job_id)
    rel = base.ROOT_NAME + '/canonical-results.json'
    old = base._read(root / rel)
    changed = _refresh(root, identity)
    try:
        return base.analyze_external(root, job_id=job_id)
    except Exception:
        if changed:
            base._publish_json(root, rel, old)
        raise


class BuildNoark5CanonicalEvidenceOperation(previous.BuildNoark5CanonicalEvidenceOperation):
    worker = staticmethod(build_evidence)


class AnalyzeNoark5ExternalEvidenceOperation(base.AnalyzeNoark5ExternalEvidenceOperation):
    worker = staticmethod(analyze_external)


class AuditNoark5EvidenceOperation(previous.AuditNoark5EvidenceOperation):
    """A missing Noark report remains an explicit deficit, not approval.

    Permit report preparation only in the specific standalone PRONOM case;
    all other missing families and invalid/mismatched evidence remain blocking.
    """
    def run(self, ctx):
        result = super().run(ctx)
        if result.ok or ctx.cancelled():
            return result
        data = result.data or {}
        if data.get('missing') != ['arkade_noark'] or data.get('status') != 'missing_expected_sources':
            return result
        try:
            root, identity = base._work_identity(Path(ctx.work_operations), str(ctx.metadata.get('job_id') or ''))
            canonical = base._read(root / base.ROOT_NAME / 'canonical-results.json')
            source = (canonical.get('a7_evidence_sources') or {}).get('arkade_pronom') or {}
            if not verify_standalone_reference(root, source,
                    job_id=identity['job_id'], job_uid=identity['job_uid']):
                return result
            audit = base._read(root / base.ROOT_NAME / 'evidence-audit.json')
            if (audit.get('external_analysis_status') != 'analyzed'
                    or audit.get('missing_source_families') != ['arkade_noark']):
                return result
            # The base audit has verified every referenced hash. Preserve its
            # missing_expected_sources status and null approval fields.
            warning = 'Arkade Noark 5-rapport mangler. Rapporter/KS er ufullstendige utkast; ingen godkjenning.'
            audit['report_preparation_with_missing_evidence'] = True
            audit['report_preparation_warning'] = warning
            base._publish_json(root, base.ROOT_NAME + '/evidence-audit.json', audit)
            return OperationResult(True, warning, data={**data, 'evidence_complete': False},
                                   warnings=[warning], outputs=result.outputs)
        except (OSError, ValueError, RuntimeError, KeyError, TypeError):
            return result
