"""Optional, non-destructive external evidence output for a native depot report."""
from __future__ import annotations

from pathlib import Path


def write_depot_evidence_outputs(report_path: str | Path, work_operations: str | Path) -> dict:
    """Create verified companions beside a completed native report.

    No files are generated if there is no KDRS import. The native report is
    never opened for writing. Failures are reported rather than swallowed.
    """
    report_path = Path(report_path)
    work = Path(work_operations)
    if not (work / 'external_evidence' / 'kdrs_query').is_dir():
        return {'status': 'not_available', 'reason': 'Ingen importerte KDRS Query-resultater'}

    from .evidence_report_bridge_a5 import write_depot_evidence_companion
    from .evidence_projection_a5 import write_effective_projection
    from .effective_depot_report_a5 import write_derived_depot_report
    from .evidence_html_a5 import write_evidence_html
    from .derived_depot_html_a5 import write_derived_depot_html

    original = report_path.read_bytes()
    companion = write_depot_evidence_companion(report_path, work)
    projection = write_effective_projection(report_path, companion)
    derived = write_derived_depot_report(report_path, projection)
    html = write_evidence_html(projection)
    derived_html = write_derived_depot_html(derived)
    if report_path.read_bytes() != original:
        raise ValueError('Original depotrapport ble uventet endret under evidensgenerering')
    return {'status': 'generated', 'evidence_companion': str(companion),
            'effective_projection': str(projection), 'derived_report': str(derived),
            'evidence_html': str(html), 'derived_html': str(derived_html)}
