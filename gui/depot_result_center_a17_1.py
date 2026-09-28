from __future__ import annotations

from copy import deepcopy

from . import theme
from .depot_result_center_a16_31 import DepotResultCenterDialogA16_31


class DepotResultCenterDialogA17_1(DepotResultCenterDialogA16_31):
    """a17.1: multi-select archive parts using the existing blue row highlight.

    Normal click selects one archive part. Ctrl+click toggles individual archive
    parts. Shift+click selects a contiguous range from the last anchor. Multiple
    selected archive parts are rendered as a temporary, traceable virtual view;
    the source report and archive-part rows are never modified.
    """

    _SUM_FIELDS = (
        "folder_count",
        "registration_count",
        "journalpost_count",
        "document_description_count",
        "document_object_count",
        "screening_count",
        "disposal_decision_count",
        "performed_disposal_count",
        "deletion_count",
    )
    _YEARLY_KEYS = ("folder", "journal", "document_description", "document_object")

    def __init__(self, master, **kwargs) -> None:
        self._a171_selected: set[int] = set()
        self._a171_anchor: int | None = None
        self._a171_virtual_index: int | None = None
        self._a171_ctrl = False
        self._a171_shift = False
        super().__init__(master, **kwargs)
        self._a171_install_selection_behavior()
        self._a171_sync_initial_selection()

    @property
    def _a1616_real_count(self) -> int:
        return sum(
            1
            for row in getattr(self, "_archive_parts", [])
            if not row.get("is_all_archive_parts") and not row.get("is_virtual_selection")
        )

    def _a171_install_selection_behavior(self) -> None:
        # Keep the existing visual list. Only the selection semantics change.
        for index, button in enumerate(getattr(self, "_archive_buttons", [])):
            button.configure(command=lambda i=index: self._a171_archive_click(i))

        for key in ("Control_L", "Control_R"):
            self.bind(f"<KeyPress-{key}>", lambda _e: self._a171_set_modifier("ctrl", True), add="+")
            self.bind(f"<KeyRelease-{key}>", lambda _e: self._a171_set_modifier("ctrl", False), add="+")
        for key in ("Shift_L", "Shift_R"):
            self.bind(f"<KeyPress-{key}>", lambda _e: self._a171_set_modifier("shift", True), add="+")
            self.bind(f"<KeyRelease-{key}>", lambda _e: self._a171_set_modifier("shift", False), add="+")
        self.bind("<FocusOut>", lambda _e: self._a171_clear_modifiers(), add="+")

    def _a171_set_modifier(self, name: str, value: bool) -> None:
        if name == "ctrl":
            self._a171_ctrl = value
        elif name == "shift":
            self._a171_shift = value

    def _a171_clear_modifiers(self) -> None:
        self._a171_ctrl = False
        self._a171_shift = False

    def _a171_sync_initial_selection(self) -> None:
        parts = getattr(self, "_archive_parts", [])
        index = getattr(self, "_archive_index", 0)
        if 0 <= index < len(parts) and not parts[index].get("is_all_archive_parts"):
            self._a171_selected = {index}
            self._a171_anchor = index
        else:
            self._a171_selected.clear()
            self._a171_anchor = None
        self._a171_update_button_highlights(index)

    def _a171_real_button_indexes(self) -> list[int]:
        parts = getattr(self, "_archive_parts", [])
        limit = len(getattr(self, "_archive_buttons", []))
        return [
            i for i in range(min(limit, len(parts)))
            if not parts[i].get("is_all_archive_parts")
        ]

    def _a171_archive_click(self, index: int) -> None:
        parts = getattr(self, "_archive_parts", [])
        if not (0 <= index < len(parts)):
            return
        if parts[index].get("is_all_archive_parts"):
            self._a171_selected.clear()
            self._a171_anchor = None
            self._a171_remove_virtual_row()
            super()._show_archive_part(index)
            self._a171_update_button_highlights(index)
            return

        if self._a171_shift and self._a171_anchor is not None:
            lo, hi = sorted((self._a171_anchor, index))
            real = set(self._a171_real_button_indexes())
            ranged = {i for i in range(lo, hi + 1) if i in real}
            if self._a171_ctrl:
                self._a171_selected.update(ranged)
            else:
                self._a171_selected = ranged
        elif self._a171_ctrl:
            if index in self._a171_selected:
                self._a171_selected.remove(index)
            else:
                self._a171_selected.add(index)
            self._a171_anchor = index
        else:
            self._a171_selected = {index}
            self._a171_anchor = index

        if not self._a171_selected:
            # Empty selection falls back to the built-in All archive parts row.
            all_index = next(
                (i for i, row in enumerate(parts) if row.get("is_all_archive_parts")),
                0,
            )
            self._a171_remove_virtual_row()
            super()._show_archive_part(all_index)
            self._a171_update_button_highlights(all_index)
            return

        if len(self._a171_selected) == 1:
            chosen = next(iter(self._a171_selected))
            self._a171_remove_virtual_row()
            super()._show_archive_part(chosen)
            self._a171_update_button_highlights(chosen)
            return

        self._a171_render_virtual_selection()

    def _a171_update_button_highlights(self, active_index: int | None = None) -> None:
        parts = getattr(self, "_archive_parts", [])
        for index, button in enumerate(getattr(self, "_archive_buttons", [])):
            selected = index in self._a171_selected
            if not self._a171_selected and 0 <= index < len(parts):
                selected = bool(parts[index].get("is_all_archive_parts")) and index == active_index
            try:
                button.configure(fg_color=theme.BLUE if selected else theme.BUTTON_BG)
            except Exception:
                pass

    def _a171_remove_virtual_row(self) -> None:
        parts = getattr(self, "_archive_parts", None)
        if not parts:
            self._a171_virtual_index = None
            return
        parts[:] = [row for row in parts if not row.get("is_virtual_selection")]
        self._a171_virtual_index = None

    @staticmethod
    def _a171_as_int(value) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _a171_build_virtual_row(self) -> dict:
        parts = getattr(self, "_archive_parts", [])
        selected_rows = [parts[i] for i in sorted(self._a171_selected) if 0 <= i < len(parts)]
        count = len(selected_rows)
        row: dict = {
            "is_virtual_selection": True,
            "archive_part": {
                "system_id": "__VIRTUAL_ARCHIVE_PART_SELECTION__",
                "title": f"{count} valgte arkivdeler",
            },
            "yearly_volume": {key: {} for key in self._YEARLY_KEYS},
        }

        for field in self._SUM_FIELDS:
            row[field] = sum(self._a171_as_int(item.get(field)) for item in selected_rows)

        for key in self._YEARLY_KEYS:
            target = row["yearly_volume"][key]
            for item in selected_rows:
                for year, value in self._series(item, key).items():
                    target[str(year)] = self._a171_as_int(target.get(str(year))) + self._a171_as_int(value)
        return row

    def _a171_render_virtual_selection(self) -> None:
        self._a171_remove_virtual_row()
        parts = getattr(self, "_archive_parts", [])
        virtual = self._a171_build_virtual_row()
        parts.append(virtual)
        index = len(parts) - 1
        self._a171_virtual_index = index
        super()._show_archive_part(index)
        self._a171_update_button_highlights(None)

    def _show_archive_part(self, index: int) -> None:
        # Inherited startup/filter code still calls this method. Keep ordinary
        # single-row behaviour unless a multi-selection is currently active.
        if len(self._a171_selected) > 1 and self._a171_virtual_index is not None:
            if index == self._a171_virtual_index:
                return super()._show_archive_part(index)
        return super()._show_archive_part(index)

    def _fix_archive_subtitle(self, index: int) -> None:
        parts = getattr(self, "_archive_parts", [])
        if 0 <= index < len(parts) and parts[index].get("is_virtual_selection"):
            try:
                self._archive_subtitle.configure(
                    text=f"Virtuelt utvalg   |   {len(self._a171_selected)} valgte arkivdeler"
                )
            except Exception:
                pass
            return
        super()._fix_archive_subtitle(index)

    def _case_count_for_row(self, row: dict):
        if row.get("is_virtual_selection"):
            parts = getattr(self, "_archive_parts", [])
            return sum(
                self._a171_as_int(super(DepotResultCenterDialogA17_1, self)._case_count_for_row(parts[i]))
                for i in self._a171_selected
                if 0 <= i < len(parts) and not parts[i].get("is_virtual_selection")
            )
        return super()._case_count_for_row(row)

    @staticmethod
    def _a171_merge_counter(target: dict, source: dict) -> None:
        if not isinstance(source, dict):
            return
        for key, value in source.items():
            if key == "_archive_parts":
                continue
            if isinstance(value, dict):
                child = target.setdefault(key, {})
                if isinstance(child, dict):
                    DepotResultCenterDialogA17_1._a171_merge_counter(child, value)
            else:
                try:
                    target[key] = int(target.get(key, 0) or 0) + int(value or 0)
                except (TypeError, ValueError):
                    # Non-numeric metadata is intentionally omitted from a
                    # synthetic sum rather than inventing a merged value.
                    pass

    def _values_for_row(self, key: str, row: dict) -> dict:
        if not row.get("is_virtual_selection"):
            return super()._values_for_row(key, row)
        parts = getattr(self, "_archive_parts", [])
        merged: dict = {}
        for index in sorted(self._a171_selected):
            if not (0 <= index < len(parts)) or parts[index].get("is_virtual_selection"):
                continue
            values = super()._values_for_row(key, parts[index])
            self._a171_merge_counter(merged, values)
        return merged

    def _type_data_for_row(self, row: dict):
        if not row.get("is_virtual_selection"):
            return super()._type_data_for_row(row)
        parts = getattr(self, "_archive_parts", [])
        folder_types: dict[str, int] = {}
        registration_types: dict[str, int] = {}
        folder_unspec = 0
        registration_unspec = 0
        for index in sorted(self._a171_selected):
            if not (0 <= index < len(parts)) or parts[index].get("is_virtual_selection"):
                continue
            ft, rt, fu, ru = super()._type_data_for_row(parts[index])
            for name, value in (ft or {}).items():
                folder_types[name] = folder_types.get(name, 0) + self._a171_as_int(value)
            for name, value in (rt or {}).items():
                registration_types[name] = registration_types.get(name, 0) + self._a171_as_int(value)
            folder_unspec += self._a171_as_int(fu)
            registration_unspec += self._a171_as_int(ru)
        return folder_types, registration_types, folder_unspec, registration_unspec

    def _a1629_refresh_selected_pair_cards(self, index: int) -> None:
        # Delayed a16 callbacks must keep the virtual aggregate in the cards.
        if len(self._a171_selected) > 1 and self._a171_virtual_index is not None:
            index = self._a171_virtual_index
        super()._a1629_refresh_selected_pair_cards(index)
