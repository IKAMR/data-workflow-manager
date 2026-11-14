"""Read-only link between a15 evidence staging and the existing DIAS package workflow.

No AIP/AIC or DIAS info.xml is created here. The established package operation,
metadata mapping and user-defined preservation decisions remain authoritative.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from noark5_workflow.analysis.canonical_results import _validate_work
from noark5_workflow.analysis.canonical_preservation_v0115_a15 import (
    OUT, INDEX, verify_candidate,
)

DIAS_OPERATION = 'noark5_workflow.operations.dias_package'
DIAS_METADATA = 'noark5_workflow.operations.dias_mets'
DIAS_INFO_BRIDGE = 'app.dias_info_v0113_a2'


def inspect_dias_preservation_link(work: str | Path) -> dict[str, Any]:
    """Inspect the known, exact a15 candidate path without editing Work or Source.

    Results are descriptive only: absence of evidence, decisions or packaging
    does not establish that an intake must be rejected or a SIP must be retained.
    """
    root, identity = _validate_work(Path(work))
    root = root.resolve()
    target = root / OUT
    manifest = target / INDEX
    if target.is_symlink() or manifest.is_symlink():
        raise ValueError('Symbolsk lenke i pakkekandidat er ikke tillatt')
    if not target.exists():
        state = 'not_created'
        files = 0
        requirements = []
    elif not manifest.is_file():
        state = 'manifest_missing'
        files = 0
        requirements = []
    else:
        validation = verify_candidate(root)
        state = 'verified_evidence_candidate' if validation['verified'] else 'evidence_integrity_failed'
        files = int(validation.get('files', 0))
        # The manifest's own unresolved conditions remain descriptive, not approval logic.
        import json
        document = json.loads(manifest.read_text(encoding='utf-8'))
        requirements = list(document.get('open_requirements', []))
    return {
        'work_job_uid': identity['job_uid'],
        'evidence_candidate': OUT,
        'evidence_state': state,
        'evidence_files': files,
        'open_requirements': requirements,
        'dias_operation': DIAS_OPERATION,
        'dias_metadata': DIAS_METADATA,
        'dias_info_bridge': DIAS_INFO_BRIDGE,
        'dias_aip_created_by_this_check': False,
        'sip_retention_decision_by_this_check': False,
        'approval_registered_by_this_check': False,
    }
