"""v0.2.6-a3: source-bound recovery of Arkade PRONOM in A210/A230.

A Noark import and its later PRONOM attachment do not necessarily live in
one Arkade import manifest. Never treat an A160 success as proof that the
latest A210 manifest contains that attachment. Only a verified, same-job,
Work-preserved statistics CSV is eligible for supplemental linking.

A230 can refresh *derived* A210/A220 projections after a previous failed
A230, without rerunning Source tests or changing the persisted job cursor.
Previous derived versions are archived by the existing Work history writer.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from noark5_workflow.core.context import OperationContext
from noark5_workflow.core.result import OperationResult
from noark5_workflow.operations import canonical_evidence_v022_a7 as prior
from noark5_workflow.operations.canonical_evidence_v022_a7 import (
    BuildNoark5CanonicalEvidenceOperation as _PreviousBuild,
    AuditNoark5EvidenceOperation as _PreviousAudit,
    EvidenceError,
)


_FAMILY = 'arkade_pronom'


def _verified_pronom_candidate(root: Path, manifest_path: Path, manifest: dict) -> tuple[dict | None, str]:
    """Accept only the actual CSV and normalized data under this import.

    The manifest being present, A160 returning OK, and a normalized JSON
    existing on disk are not sufficient separately. Hash original Noark and
    the preserved PRONOM CSV independently. No Source-path fallback is used.
    """
    details = ((manifest.get('pronom_evidence') or {}).get('statistics') or {})
    relative = str(details.get('normalized_file') or '')
    if not relative:
        return None, 'PRONOM-statistikk er ikke registrert i importmanifestet'
    if details.get('imported') is False:
        return None, 'PRONOM-statistikk er markert som ikke importert'
    try:
        stat = prior._within(root, relative)
        import_dir = manifest_path.parent
        if (import_dir / 'normalized').is_symlink() or (import_dir / 'source').is_symlink():
            return None, 'Arkade-importen har symbolsk lenke til evidensmappe'
        if stat != import_dir / 'normalized' / 'pronom_statistics.json':
            return None, 'PRONOM-referansen peker ikke til samme Arkade-import'
        if not stat.is_file() or stat.is_symlink() or stat.stat().st_size > prior.MAX_JSON:
            return None, 'Normalisert PRONOM-statistikk mangler eller overstiger sikker filgrense'
        parsed = prior._read(stat)
        if (parsed.get('evidence_type') != 'arkade5_pronom_format_statistics'
                or parsed.get('source_system') != 'Arkade 5'
                or parsed.get('format_version') != 1
                or not isinstance((parsed.get('csv') or {}).get('rows'), list)):
            return None, 'PRONOM-statistikk har ugyldig kilde-/formatstruktur'
        source = parsed.get('source') or {}
        preserved = prior._within(root, str(source.get('preserved_file') or ''))
        if preserved.parent != import_dir / 'source' or not preserved.is_file():
            return None, 'Bevart original CSV finnes ikke i samme Arkade-import'
        source_digest = str(source.get('sha256') or '').casefold()
        if len(source_digest) != 64 or prior._hash(preserved).casefold() != source_digest:
            return None, 'SHA-256 for bevart PRONOM-CSV stemmer ikke'
        manifest_digest = str(details.get('sha256') or '').casefold()
        if manifest_digest and manifest_digest != source_digest:
            return None, 'PRONOM-manifest og normalisert kilde har ulik SHA-256'
        # Anchor to the original Noark report on this same, job-owned import.
        ark_source = manifest.get('source') or {}
        ark_original = prior._within(root, str(ark_source.get('preserved_file') or ''))
        ark_digest = str(ark_source.get('sha256') or '').casefold()
        if (ark_original.parent != import_dir / 'source' or not ark_original.is_file()
                or len(ark_digest) != 64 or prior._hash(ark_original).casefold() != ark_digest):
            return None, 'Original Arkade Noark-rapport kan ikke SHA-256-verifiseres'
        return {
            'file': stat.relative_to(root).as_posix(),
            'sha256': prior._hash(stat),
            'manifest': manifest_path.relative_to(root).as_posix(),
            'manifest_sha256': prior._hash(manifest_path),
        }, ''
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return None, 'PRONOM-evidens kunne ikke verifiseres: ' + str(exc)


def _find_pronom_in_same_work(root: Path, identity: dict) -> tuple[dict | None, str]:
    """Select latest unambiguous, verified same-job PRONOM import.

    Different Arkade Noark and PRONOM import IDs are permitted, but neither
    another job's Work nor unowned/manual imports can silently be claimed.
    """
    candidates: list[tuple[str, Path, dict]] = []
    problems: list[str] = []
    other_jobs = 0
    unowned_pronom = 0
    import_count = 0
    for path in prior._members(root, 'external_evidence/arkade5/*/manifest.json'):
        manifest = prior._read(path)
        by = manifest.get('imported_by') or {}
        if (str(by.get('job_id') or '') != str(identity['job_id']) or
                str(by.get('job_uid') or '') not in ('', str(identity['job_uid']))):
            other_jobs += 1
            if (((manifest.get('pronom_evidence') or {}).get('statistics') or {})
                    .get('normalized_file')):
                unowned_pronom += 1
            continue
        import_count += 1
        candidate, reason = _verified_pronom_candidate(root, path, manifest)
        if candidate is None:
            problems.append(path.parent.name + ': ' + reason)
        else:
            candidates.append((str(manifest.get('imported_at') or ''), path, candidate))
    if not candidates:
        if problems:
            reason = '; '.join(problems[:3])
            if len(problems) > 3:
                reason += f' (+{len(problems)-3} andre importer)'
            if unowned_pronom:
                reason += (f'; PRONOM finnes i {unowned_pronom} import(er) uten '
                           'verifisert JOB-ID; kan ikke kobles automatisk')
            return None, reason
        if other_jobs and not import_count:
            return None, 'Arkade-importer finnes, men ingen er registrert på aktiv JOB-ID'
        return None, 'Ingen verifisert Arkade PRONOM-statistikk finnes i denne jobbens Work'
    candidates.sort(key=lambda row: (row[0], row[1].as_posix()))
    if (len(candidates) > 1 and
            (not candidates[-1][0] or candidates[-1][0] == candidates[-2][0])):
        return None, 'Flere verifiserte PRONOM-importer mangler entydig siste tidspunkt; velg kilde manuelt'
    return candidates[-1][2], ''


def _sources(root: Path, identity: dict) -> dict[str, dict]:
    """Keep prior source selection, augment missing Arkade PRONOM only."""
    linked = prior._select_external_sources(root, identity)
    if _FAMILY not in linked:
        recovered, _reason = _find_pronom_in_same_work(root, identity)
        if recovered is not None:
            linked[_FAMILY] = recovered
    return linked


def build_evidence(work: str | Path, *, job_id: str = '', run_id: str = '') -> dict:
    """A210, preserving master selection and canonical schema from v0.2.5."""
    from noark5_workflow.analysis.canonical_results import build_canonical_results
    root, identity = prior._work_identity(Path(work), job_id)
    master = prior._select_master(root, identity, run_id)
    doc = build_canonical_results(root, master_paths=(master,), write=False)
    sources = _sources(root, identity)
    doc['a7_evidence_sources'] = sources
    doc['a7_dependency_no'] = 210
    doc['a7_source_coverage'] = {
        'dwm_xpath': 'verified',
        'arkade_noark': 'linked' if 'arkade_noark' in sources else 'not_available',
        'arkade_pronom': 'linked' if 'arkade_pronom' in sources else 'not_available',
        'siegfried_pronom': 'linked' if 'siegfried_pronom' in sources else 'not_available',
        'fully_verified_noark5': False,
        'approval': None,
    }
    doc['limitations'].append('A7 external references are source-separated, not canonical observations')
    target = prior._publish_json(root, prior.ROOT_NAME + '/canonical-results.json', doc)
    return {'path': str(target), 'observations': len(doc['observations']),
            'external_sources': list(sources), 'job_uid': identity['job_uid']}


def _write_diagnostic(root: Path, result: dict, reason: str) -> dict:
    """Add human explanation to the persisted audit without changing status."""
    path = root / prior.ROOT_NAME / 'evidence-audit.json'
    report = prior._read(path)
    report['missing_source_reasons'] = {_FAMILY: reason}
    prior._publish_json(root, prior.ROOT_NAME + '/evidence-audit.json', report)
    return {**result, 'missing_reasons': {_FAMILY: reason}}


def audit_evidence(work: str | Path, *, job_id: str = '') -> dict:
    """A230: recover verified older PRONOM with versioned, reversible writes.

    First do the original strict audit. Only if Arkade PRONOM alone is absent
    from the A210 snapshot, a valid same-job source is found, and A220 is
    consistent with that snapshot, refresh the two *derived* snapshots.
    The run cursor, Source, Arkade/CLI output and all original inputs stay put.
    """
    root, identity = prior._work_identity(Path(work), job_id)
    initial = prior.audit_evidence(root, job_id=job_id)
    missing = initial.get('missing') or []
    if _FAMILY not in missing:
        return initial
    candidate, reason = _find_pronom_in_same_work(root, identity)
    if candidate is None:
        return _write_diagnostic(root, initial, reason)
    if len(missing) != 1:
        return _write_diagnostic(root, initial,
                                 'PRONOM kan kobles, men andre forventede kilder mangler også; ' 
                                 'reparer de øvrige kildene før A230 kan fullføres')

    canonical_relative = prior.ROOT_NAME + '/canonical-results.json'
    analysis_relative = prior.ROOT_NAME + '/canonical-external-analysis.json'
    canonical_path = root / canonical_relative
    external_path = root / analysis_relative
    old_canonical = prior._read(canonical_path)
    old_audit = prior._read(root / prior.ROOT_NAME / 'evidence-audit.json')
    old_sha = prior._hash(canonical_path)
    current_sources = old_canonical.get('a7_evidence_sources') or {}
    if not current_sources.get('arkade_noark'):
        return _write_diagnostic(root, initial,
                                 'Kanonisk Arkade Noark-referanse mangler; A210 må kontrolleres')
    if not external_path.is_file() or external_path.is_symlink():
        return _write_diagnostic(root, initial,
                                 'A220 analysefil mangler; A220 må fullføres før A230')
    old_external = prior._read(external_path, limit=128 * 1024 * 1024)
    old_external_sha = prior._hash(external_path)
    if (old_external.get('extraction_stable_id') != identity['job_uid']
            or (old_external.get('canonical_reference') or {}).get('sha256') != old_sha):
        return _write_diagnostic(root, initial,
                                 'A220-kildereferansen samsvarer ikke med A210; ingen automatisk reparasjon')
    analyzed = {
        (row.get('evidence') or {}).get('work_relative_path'):
        (row.get('evidence') or {}).get('sha256')
        for row in old_external.get('sources') or [] if isinstance(row, dict)
    }
    if (len(analyzed) != len(current_sources) or
            any(analyzed.get(s['file']) != s['sha256'] for s in current_sources.values())):
        return _write_diagnostic(root, initial,
                                 'A220 inneholder ikke alle verifiserte A210-kilder; ingen automatisk reparasjon')
    if prior._hash(canonical_path) != old_sha or prior._hash(external_path) != old_external_sha:
        raise EvidenceError('A210/A220 endret seg under evidensreparasjonen; prøv igjen')

    updated = deepcopy(old_canonical)
    updated['a7_evidence_sources'][_FAMILY] = candidate
    coverage = updated.setdefault('a7_source_coverage', {})
    coverage[_FAMILY] = 'linked'
    updated['a230_source_relink'] = {
        'family': _FAMILY,
        'reason': 'Gyldig eldre Arkade-import ble ikke valgt av A210',
        'previous_canonical_sha256': old_sha,
        'source_work_relative_path': candidate['file'],
        'source_sha256': candidate['sha256'],
        'automatic_approval': False,
    }
    try:
        prior._publish_json(root, canonical_relative, updated)
        prior.analyze_external(root, job_id=job_id)
        checked = prior.audit_evidence(root, job_id=job_id)
        if checked.get('missing'):
            raise EvidenceError('Fortsettelse mangler fortsatt evidenskilder')
        persisted = prior._read(root / prior.ROOT_NAME / 'evidence-audit.json')
        persisted['a230_relinked'] = {
            'family': _FAMILY,
            'source_work_relative_path': candidate['file'],
            'previous_canonical_sha256': old_sha,
            'previous_external_sha256': old_external_sha,
            'source_sha256': candidate['sha256'],
            'no_original_sources_modified': True,
            'automatic_approval': False,
        }
        prior._publish_json(root, prior.ROOT_NAME + '/evidence-audit.json', persisted)
        return {**checked, 'recovered': [_FAMILY]}
    except Exception as exc:
        # Restore the exact previous derived projections. The atomic Work
        # publisher keeps both old and new versions under noark5_evidence/history.
        failures = []
        for relative, previous in ((canonical_relative, old_canonical),
                                   (analysis_relative, old_external),
                                   (prior.ROOT_NAME + '/evidence-audit.json', old_audit)):
            try:
                prior._publish_json(root, relative, previous)
            except Exception as restore_exc:
                failures.append(f'{relative}: {restore_exc}')
        if failures:
            raise EvidenceError('A230 gjenkobling feilet og tilbakerulling feilet: '
                                + '; '.join(failures)) from exc
        raise EvidenceError('A230 gjenkobling feilet; tidligere A210/A220 gjenopprettet: '
                            + str(exc)) from exc


class BuildNoark5CanonicalEvidenceOperation(_PreviousBuild):
    """A210 with explicit run ID, retaining upstream job/running contracts."""
    worker = staticmethod(build_evidence)

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
                run_id=str(ctx.metadata.get('run_id') or ''),
            )
            if ctx.cancelled():
                return OperationResult(False, 'Avbrutt av bruker.')
            ctx.progress(1.0, self.definition.name + ' fullfort')
            return OperationResult(True, self.definition.name + ': gjennomfort, ingen automatisk godkjenning.',
                                   data=output, outputs=[output['path']])
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
            return OperationResult(False, self.definition.name + ': ' + str(exc))


class AuditNoark5EvidenceOperation(_PreviousAudit):
    """A230 never reports success while expected families are missing."""
    worker = staticmethod(audit_evidence)

    def run(self, ctx: OperationContext) -> OperationResult:
        result = super().run(ctx)
        if not result.ok:
            return result
        output = result.data or {}
        if output.get('missing'):
            families = ', '.join(str(name) for name in output['missing'])
            reasons = output.get('missing_reasons') or {}
            explanation = '; '.join(f'{k}: {v}' for k, v in reasons.items())
            message = 'Evidens mangler for valgte kontroller: ' + families
            if explanation:
                message += '. Årsak: ' + explanation
            return OperationResult(False, message, data=output, outputs=result.outputs)
        if output.get('recovered'):
            return OperationResult(True,
                'A230: verifisert Arkade PRONOM gjenkoblet fra samme Work; '
                'A210/A220-projeksjoner oppdatert, tidligere versjoner bevart. '
                'Ingen automatisk faglig godkjenning.',
                data=output, outputs=result.outputs)
        return result
