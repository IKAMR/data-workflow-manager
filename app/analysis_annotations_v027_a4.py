"""Scoped Analyse annotations over DWM's existing report-bound depot ledger.

One note targets an area, control, observed-value group or exact source finding.
The note is never duplicated to descendant records. Projections distinguish
inherited, direct and child notes; no note is interpreted as approval.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from pathlib import Path
from typing import Any, Iterable
import json

from app.analysis_workspace_v027_a2 import (
    AREAS, AnalysisSnapshot, part_identity, rule_findings,
)

VIEW_ID = 'analysis'
PREFIX = 'analysis-a4:'
LEVELS = ('area', 'control', 'group', 'item')
AREAS_BY_KIND = {
    'part': AREAS[0], 'year': AREAS[1], 'period_finding': AREAS[1],
    'metadata': AREAS[2], 'format': AREAS[3], 'preservation': AREAS[4],
}
MAX_COMMENTS = 100_000


@dataclass(frozen=True)
class Target:
    level: str
    scope: str
    area: str
    control: str = ''
    group: str = ''
    item: str = ''

    def __post_init__(self):
        if self.level not in LEVELS or self.area not in AREAS:
            raise ValueError('Ukjent kommentarnivaa eller kontrollomraade')
        if not self.scope or (self.level != 'area' and not self.control):
            raise ValueError('Kommentar mangler entydig omfang eller kontroll')
        if self.level == 'group' and not self.group:
            raise ValueError('Gruppekommentar mangler verdivalg')
        if self.level == 'item' and not self.item:
            raise ValueError('Forekomstkommentar mangler faktisk funn-ID')

    @property
    def id(self) -> str:
        fields = [self.level, self.scope, self.area, self.control,
                  self.group, self.item]
        return PREFIX + json.dumps(fields, ensure_ascii=False, separators=(',', ':'))


def parse_target(value: object) -> Target | None:
    if not isinstance(value, str) or not value.startswith(PREFIX):
        return None
    try:
        parts = json.loads(value[len(PREFIX):])
        if (not isinstance(parts, list) or len(parts) != 6
                or any(not isinstance(v, str) for v in parts)):
            return None
        return Target(*parts)
    except (ValueError, TypeError):
        return None


def part_scope(snapshot: AnalysisSnapshot, part_index: int) -> str | None:
    if not 0 <= part_index < len(snapshot.parts):
        return None
    native_id = str(part_identity(snapshot.parts[part_index]).get('system_id') or '')
    return 'part:' + native_id if native_id else None


def control_context(snapshot: AnalysisSnapshot, kind: str, payload: Any,
                    part_index: int | None) -> tuple[str, str, str]:
    """(area, control, scope) without borrowing unrelated data scopes."""
    if kind not in AREAS_BY_KIND:
        raise ValueError('Ukjent delresultattype')
    area = AREAS_BY_KIND[kind]
    scope = part_scope(snapshot, part_index) if part_index is not None else None
    if kind in ('part', 'preservation'):
        scope = part_scope(snapshot, payload)
        if not scope:
            raise ValueError('Arkivdel mangler entydig system-ID')
        control = kind + ':' + scope
    elif kind == 'metadata':
        control = 'metadata:' + str(payload.get('metadata_id') or '')
    elif kind == 'format':
        # Format inventories are not mapped reliably to archive parts/years.
        scope = None
        control = 'format:' + str(payload.get('puid') or '')
    elif kind == 'year':
        control = 'year:' + str(payload)
    else:
        # Multiple review findings may share category and year. The report
        # immutable hash protects this exact data-bound identity.
        import hashlib
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                               default=str).encode('utf-8')
        control = 'period:' + hashlib.sha256(canonical).hexdigest()[:24]
    if not control or control.endswith(':'):
        raise ValueError('Delresultat mangler ID')
    return area, control, scope or 'extract'


def make_target(level: str, scope: str, area: str, control: str = '',
                group: str = '', item: str = '') -> Target:
    if level == 'area':
        return Target(level, scope, area)
    if level == 'control':
        return Target(level, scope, area, control)
    if level == 'group':
        return Target(level, scope, area, control, group)
    return Target(level, scope, area, control, group, item)


def value_groups(snapshot: AnalysisSnapshot, kind: str, payload: Any,
                 scope: str) -> tuple[tuple[str, int], ...]:
    """Observed groups from existing evidence; do not invent part totals.

    For the full extraction, the saved standard-value distribution also
    includes valid values.  Per archive part only the persisted *deviation*
    occurrences are known; those are not represented as a complete inventory.
    """
    if kind != 'metadata':
        return ()
    if scope == 'extract':
        distribution = payload.get('production_distribution') or {}
        if isinstance(distribution, dict) and distribution:
            values = []
            for value, raw in distribution.items():
                if not isinstance(value, str) or not value.strip() or isinstance(raw, bool):
                    continue
                try:
                    count = int(raw)
                except (TypeError, ValueError, OverflowError):
                    continue
                if count > 0 and str(raw).strip() == str(count):
                    values.append((value, count))
            return tuple(sorted(values, key=lambda x: (-x[1], x[0])))
    if not snapshot.findings_complete:
        return ()
    mid = str(payload.get('metadata_id') or '')
    items = rule_findings(snapshot, mid, None)
    if scope.startswith('part:'):
        items = tuple(f for f in items
                      if str(f.get('archive_part_id') or '') == scope[5:])
    counts = Counter(str(f.get('value') or '') for f in items)
    return tuple(sorted(((v, n) for v, n in counts.items() if v),
                        key=lambda x: (-x[1], x[0])))


def item_findings(snapshot: AnalysisSnapshot, kind: str, payload: Any,
                  scope: str, group: str = '') -> tuple[dict[str, Any], ...]:
    if kind != 'metadata' or not snapshot.findings_complete:
        return ()
    found = rule_findings(snapshot, str(payload.get('metadata_id') or ''), None)
    if scope.startswith('part:'):
        found = tuple(f for f in found
                      if str(f.get('archive_part_id') or '') == scope[5:])
    if group:
        found = tuple(f for f in found if str(f.get('value') or '') == group)
    # Only explicitly persisted stable identities can be annotated singly.
    return tuple(f for f in found if str(f.get('finding_uid') or '').strip())


def annotated_record_ids(records: Iterable[dict[str, Any]]) -> tuple[tuple[Target, dict[str, Any]], ...]:
    result = []
    for item in records:
        if not isinstance(item, dict) or item.get('status') == 'closed':
            continue
        source = (item.get('target') or {})
        if source.get('view_id') != VIEW_ID:
            continue
        target = parse_target(source.get('target_id'))
        if target is not None:
            result.append((target, item))
    return tuple(result)


def _scope_relationship(row_scope: str, note_scope: str) -> str | None:
    if row_scope == note_scope:
        return 'direct'
    if row_scope.startswith('part:') and note_scope == 'extract':
        return 'inherited'
    if row_scope == 'extract' and note_scope.startswith('part:'):
        return 'child'
    return None


def comment_matches(snapshot: AnalysisSnapshot, kind: str, payload: Any,
                    part_index: int | None,
                    records: Iterable[dict[str, Any]]) -> tuple[tuple[str, dict[str, Any]], ...]:
    """Return (direct|inherited|child, note) for a row.

    A group/individual note rolls up to its parent control but does not spread
    horizontally to other controls, parts or PUIDs. An area note is inherited.
    """
    area, control, scope = control_context(snapshot, kind, payload, part_index)
    result = []
    for target, note in annotated_record_ids(records):
        if target.area != area:
            continue
        relation = _scope_relationship(scope, target.scope)
        if relation is None:
            continue
        if target.level != 'area' and target.control != control:
            continue
        # Child level records roll up visibly to their parent control.
        if target.level in ('group', 'item') and relation == 'direct':
            relation = 'child'
        if target.level == 'area' and relation == 'direct':
            relation = 'inherited'
        result.append((relation, note))
    return tuple(result)


def comment_counts(matches: Iterable[tuple[str, dict[str, Any]]]) -> tuple[int, int, int]:
    kinds = Counter(name for name, _ in matches)
    return kinds['direct'], kinds['inherited'], kinds['child']


def comment_badge(matches: Iterable[tuple[str, dict[str, Any]]]) -> str:
    direct, inherited, child = comment_counts(matches)
    count = direct + inherited + child
    if not count:
        return ''
    return ('💬 ' if direct else '↳ 💬 ') + str(count)


def read_comments(report_path: Path | str) -> tuple[dict[str, Any], ...]:
    """Reuse the same report-bound ledger as the existing depot report views."""
    from noark5_workflow.analysis.depot_annotations import list_depot_annotations
    rows = list_depot_annotations(report_path, view_id=VIEW_ID)
    if len(rows) > MAX_COMMENTS:
        raise ValueError('For mange kommentarer i denne rapporten til sikker visning')
    return tuple(rows)


def save_comment(snapshot: AnalysisSnapshot, target: Target,
                 label: str, text: str, annotation_type: str, user: Any) -> dict[str, Any]:
    """Only the explicit action writes a comment sidecar inside the selected Work."""
    root = snapshot.work.resolve(strict=True)
    report = snapshot.report_path.resolve(strict=True)
    if not report.is_relative_to(root) or not report.is_file():
        raise ValueError('Kommentarmålet er ikke en rapport i valgt Work')
    sidecar = report.with_name('depot_annotations.json')
    if sidecar.is_symlink():
        raise ValueError('Kommentarlager kan ikke vaere en symbolsk lenke')
    if not str(text or '').strip():
        raise ValueError('Kommentar kan ikke vaere tom')
    from noark5_workflow.analysis.depot_annotations import record_depot_annotation
    return record_depot_annotation(
        report, annotation_type=annotation_type,
        text=text.strip(), user=user, view_id=VIEW_ID,
        target_type='analysis_' + target.level,
        target_id=target.id, target_label=label,
    )


def comment_export_rows(records: Iterable[dict[str, Any]]) -> tuple[dict[str, str], ...]:
    """Stable report-ready projection, without rewriting the saved depot report."""
    result = []
    for target, note in annotated_record_ids(records):
        result.append({
            'scope': target.scope, 'area': target.area,
            'level': target.level, 'control': target.control,
            'group': target.group, 'item': target.item,
            'text': str(note.get('text') or ''),
            'type': str(note.get('annotation_type') or ''),
            'status': str(note.get('status') or ''),
            'created_at': str(note.get('created_at') or ''),
            'user': str((note.get('user') or {}).get('username') or ''),
            'annotation_id': str(note.get('annotation_id') or ''),
        })
    return tuple(result)
