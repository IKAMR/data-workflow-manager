"""Identity-safe reuse of saved Basic jobs when a multi-job form is stale.

This does NOT loosen the existing register_basic_plan source/work guards.
Only a confirmed, unchanged job may skip redundant registration; genuine
edits and incomplete drafts still use the old guarded registration path.
"""
from __future__ import annotations

import ntpath
from pathlib import Path


def same_storage_path(first, second) -> bool:
    if not first or not second:
        return False
    a, b = str(first), str(second)
    # Windows job lists can be inspected from Linux in the regression suite.
    # Do not rely on os.path.normcase which is case-sensitive on Linux.
    if '\\' in a or '\\' in b or ntpath.splitdrive(a)[0] or ntpath.splitdrive(b)[0]:
        return ntpath.normcase(ntpath.normpath(a.replace('/', '\\'))) == ntpath.normcase(ntpath.normpath(b.replace('/', '\\')))
    return str(Path(a).resolve(strict=False)).casefold() == str(Path(b).resolve(strict=False)).casefold()


def saved_job_decision(jobs, *, selected_job_id: str | None, actual_active_id: str | None,
                       source: str, work: str, draft: bool, edited: bool,
                       metadata_dirty: bool) -> str:
    """Return 'reuse', 'restore', 'register' or 'blocked'.

    'restore' only applies when both displayed paths belong to a *different*
    registered job and there are no user edits.  Never accept an arbitrary
    changed path as a stale form, or adopt a Work without identity checks.
    """
    if draft or not selected_job_id:
        return 'register'
    if selected_job_id != actual_active_id:
        return 'blocked'
    selected = next((j for j in jobs if str(getattr(j, 'job_id', '')) == selected_job_id), None)
    if selected is None:
        return 'blocked'
    other = next((j for j in jobs if j is not selected and
                  same_storage_path(source, getattr(j, 'source_extraction', None)) and
                  same_storage_path(work, getattr(j, 'effective_work_operations', None)
                                     or getattr(j, 'work_operations', None))), None)
    if other is not None and not edited and not metadata_dirty:
        return 'restore'
    if edited or metadata_dirty:
        return 'register'
    current_source = same_storage_path(source, getattr(selected, 'source_extraction', None))
    current_work = same_storage_path(work, getattr(selected, 'effective_work_operations', None)
                                    or getattr(selected, 'work_operations', None))
    if current_source and current_work:
        return 'reuse'
    return 'blocked'
