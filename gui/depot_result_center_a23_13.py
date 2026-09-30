from __future__ import annotations

from .depot_result_center_a23_12 import DepotResultCenterDialogA23_12


class DepotResultCenterDialogA23_13(DepotResultCenterDialogA23_12):
    """a23.13: show systemID for All archive parts and reset evidence scroll per control."""

    def _a232_clear(self, frame) -> None:
        super()._a232_clear(frame)

        # A new control must always start at the top of Resultat og evidens.
        # This is especially important on smaller screens where the user may
        # have scrolled far down before pressing Neste/Forrige kontroll.
        def _scroll_top():
            try:
                canvas = getattr(frame, "_parent_canvas", None)
                if canvas is not None:
                    canvas.yview_moveto(0.0)
                    return
            except Exception:
                pass
            try:
                frame._parent_canvas.yview_moveto(0.0)
            except Exception:
                pass

        try:
            frame.after_idle(_scroll_top)
        except Exception:
            _scroll_top()

    def _a222_control_items(self, index: int) -> list[dict]:
        items = list(super()._a222_control_items(index))
        parts = getattr(self, "_archive_parts", None) or []
        if not (0 <= index < len(parts)):
            return items

        row = parts[index]
        if not row.get("is_all_archive_parts"):
            return items

        # Now that systemID has a scope-aware aggregate view, expose it in the
        # left control list for the default All archive parts selection too.
        if any(str(item.get("label") or "") == "systemID" for item in items):
            return items

        scope_rows = self._a2311_scope_rows(index)
        total, missing, duplicates = self._a2311_systemid_summary(scope_rows)
        present = max(0, total - missing)
        control_status = "OK" if missing == 0 and duplicates == 0 else "OBS"
        value = (
            f"{present} systemID av {total} arkivdeler"
            f" · mangler: {missing}"
            f" · duplikater: {duplicates}"
        )

        system_item = {
            "section": "Arkiv / arkivdeler",
            "label": "systemID",
            "value": value,
            "source": "arkivstruktur.xml",
            "control_status": control_status,
        }

        insert_at = 0
        for pos, item in enumerate(items):
            if str(item.get("section") or "") == "Arkiv / arkivdeler":
                insert_at = pos + 1
            elif insert_at:
                break
        items.insert(insert_at, system_item)
        return items
