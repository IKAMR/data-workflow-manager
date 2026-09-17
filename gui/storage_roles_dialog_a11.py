from __future__ import annotations

from pathlib import Path

from . import storage_roles_dialog as _base


# a11: user-facing generic storage vocabulary.
# The application model is Source -> Work -> Storage. The rest of the GUI may
# remain Norwegian; these role names are deliberately stable English terms.
_FIELDS = (
    ("source_root", "Source - root", "dir"),
    ("source_tar", "Source - TAR", "file"),
    ("source_unzipped", "Source - unpacked", "dir"),
    ("source_extraction", "Source - extraction", "dir"),
    ("work_root", "Work - root", "dir"),
    ("work_content", "Work - content", "dir"),
    ("work_operations", "Work - operations", "dir"),
    ("archive_root", "Storage - root", "dir"),
)

# StorageRolesDialog in the established runtime reads these module-level tables
# from gui.storage_roles_dialog. Replace the display contract at import time so
# every chooser/history label follows Source / Work / Storage consistently.
_base._FIELDS = _FIELDS
_base._LABELS = {attr: label for attr, label, _kind in _FIELDS}


class StorageRolesDialog(_base.StorageRolesDialog):
    """a11 role dialog using the generic Source / Work / Storage vocabulary."""

    def _suggestions(self, attr: str) -> list[Path]:
        """Only suggest paths that are intrinsic to Work.

        Storage is a peer role, not an assumed subdirectory of Work, so a11 no
        longer proposes the old Work/aip location for Storage.
        """
        work_root = self._current_path("work_root")
        suggestions: list[Path] = []
        if work_root:
            if attr == "work_content":
                suggestions.append(work_root / "content")
            elif attr == "work_operations":
                suggestions.append(work_root / "repository_operations")
        return suggestions
