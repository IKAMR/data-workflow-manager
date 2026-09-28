from __future__ import annotations

from .depot_result_center_a16_26 import DepotResultCenterDialogA16_26


class DepotResultCenterDialogA16_29(DepotResultCenterDialogA16_26):
    """a16.29: keep summary pair cards scoped to the selected archive part.

    This deliberately builds directly on a16.26.  The abandoned a16.27
    multiselect experiment and a16.28 are not part of this runtime chain.
    """

    _PAIR_TITLES = {
        "Mapper / saker": ("folder_count", "case_folder_count"),
        "Registreringer / journalposter": ("registration_count", "journalpost_count"),
        "Dok.beskrivelser / objekter": ("document_description_count", "document_object_count"),
    }

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        self._a1629_refresh_selected_pair_cards(index)

        # Some inherited CTk layers finish their own redraw on idle.  Repeat the
        # small header-only refresh after that redraw so the visible cards always
        # follow the archive part that remains selected.
        try:
            self.after_idle(lambda i=index: self._a1629_refresh_selected_pair_cards(i))
            self.after(40, lambda i=index: self._a1629_refresh_selected_pair_cards(i))
        except Exception:
            pass

    def _a1629_pair_values_for_row(self, row: dict) -> dict[tuple[str, str], str]:
        values: dict[tuple[str, str], str] = {}
        for _title, (left, right) in self._PAIR_TITLES.items():
            left_value = row.get(left)
            if left == "folder_count" and right == "case_folder_count":
                right_value = self._case_count_for_row(row)
            else:
                right_value = row.get(right)
            values[(left, right)] = (
                f"{self._fmt_count(left_value)} / {self._fmt_count(right_value)}"
            )
        return values

    def _a1629_refresh_selected_pair_cards(self, index: int) -> None:
        parts = getattr(self, "_archive_parts", None) or []
        if not (0 <= index < len(parts)):
            return

        # Do not let an old/delayed callback overwrite the current selection.
        current = getattr(self, "_archive_index", index)
        if current != index:
            return

        row = parts[index]
        pair_values = self._a1629_pair_values_for_row(row)

        # Primary route: update the exact widgets created by the a16 summary
        # surface.  This covers both "Alle arkivdeler" and individual parts.
        widgets = getattr(self, "_a1618_pair_values", None) or {}
        for pair, text in pair_values.items():
            widget = widgets.get(pair)
            if widget is not None:
                try:
                    widget.configure(text=text)
                except Exception:
                    pass

        # Defensive route: locate the visible cards by their headings.  This
        # protects the fix against older inherited layers retaining a stale
        # widget reference while the visible card itself has been recreated.
        tabs = getattr(self, "_a10_tabs", None)
        if tabs is None:
            return
        try:
            root = tabs.tab("Sammendrag")
        except Exception:
            return

        title_to_text = {
            title: pair_values[pair]
            for title, pair in self._PAIR_TITLES.items()
        }

        stack = [root]
        while stack:
            parent = stack.pop()
            try:
                children = list(parent.winfo_children())
            except Exception:
                continue
            stack.extend(children)
            for child in children:
                try:
                    title = str(child.cget("text") or "")
                except Exception:
                    continue
                if title not in title_to_text:
                    continue
                card = getattr(child, "master", None)
                if card is None:
                    continue
                try:
                    siblings = list(card.winfo_children())
                except Exception:
                    continue
                for sibling in siblings:
                    if sibling is child:
                        continue
                    try:
                        shown = str(sibling.cget("text") or "")
                    except Exception:
                        continue
                    if "/" in shown or shown in {"–", "– / –"}:
                        try:
                            sibling.configure(text=title_to_text[title])
                        except Exception:
                            pass
                        break
