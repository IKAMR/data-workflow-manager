from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a14_2 import DepotResultCenterDialogA14_2
from . import depot_result_views_a24 as _a24_window_layer
from . import depot_result_views_a26 as _a26_window_layer
from .window_placement import present_child_over_parent, release_parent_work_window
from .window_geometry import apply_result_review_opening_mode


class DepotResultCenterDialogA14_4(DepotResultCenterDialogA14_2):
    _defer_initial_show = True
    """v0.1.6-a14: technical details, PRONOM table, stable initial overview."""

    def __init__(self, master, **kwargs) -> None:
        # Build the complete inherited result centre while it is hidden.  Older
        # result-view layers normally present the Toplevel during construction;
        # suppress those calls here so Windows never sees an intermediate view.
        saved = (
            _a24_window_layer.present_native_work_window,
            _a26_window_layer.release_parent_work_window,
            _a26_window_layer.present_native_work_window,
            _a26_window_layer.present_child_over_parent,
            _a26_window_layer.apply_result_review_opening_mode,
        )
        try:
            _a24_window_layer.present_native_work_window = lambda *_a, **_k: None
            _a26_window_layer.release_parent_work_window = lambda *_a, **_k: None
            _a26_window_layer.present_native_work_window = lambda *_a, **_k: None
            _a26_window_layer.present_child_over_parent = lambda *_a, **_k: None
            _a26_window_layer.apply_result_review_opening_mode = lambda *_a, **_k: None
            super().__init__(master, **kwargs)
        finally:
            (
                _a24_window_layer.present_native_work_window,
                _a26_window_layer.release_parent_work_window,
                _a26_window_layer.present_native_work_window,
                _a26_window_layer.present_child_over_parent,
                _a26_window_layer.apply_result_review_opening_mode,
            ) = saved

        tabs = self._root_tabview()
        if tabs is None:
            return

        tabs.add("Teknisk")
        self._build_technical_tab(tabs.tab("Teknisk"))
        try:
            tabs.delete("Noark 5")
        except Exception:
            pass

        order = ["Oversikt", "Arkivdeler", "Depotvurdering", "Filformater", "Rapporter", "Teknisk"]
        # Reorder through CTkTabview itself.  Updating its private name list or
        # only the segmented button can leave the selected button detached from
        # the frame that is actually mapped.
        for index, name in enumerate(order):
            try:
                tabs.move(index, name)
            except Exception:
                # Compatibility fallback for older CustomTkinter versions.
                try:
                    tabs._segmented_button.configure(values=order)
                except Exception:
                    pass
                break

        self._replace_pronom_text_with_table(tabs.tab("Filformater"))

        # Map the completed window invisibly first.  CTkTabview needs one real
        # mapped layout pass on Windows before the selected page is reliable.
        # Keeping alpha at zero prevents the user from seeing the inherited
        # intermediate tab structure while that mapping/layout settles.
        try:
            self.attributes("-alpha", 0.0)
        except Exception:
            pass
        self.deiconify()
        self.update_idletasks()
        try:
            self.update()
        except Exception:
            pass

        apply_result_review_opening_mode(self, wide_ratio=2.0)
        self.update_idletasks()

        # CTkTabview does not reliably map the initially selected page until
        # Tk has entered the real event loop.  Keep the completed window hidden
        # and perform the same transition that works on a manual tab change
        # from an idle callback.  Only then make the window visible.
        self.after(100, lambda: self._finish_initial_show(master, tabs))


    def _finish_initial_show(self, master, tabs) -> None:
        self._activate_initial_overview(tabs)
        self.update_idletasks()
        try:
            self.attributes("-alpha", 1.0)
        except Exception:
            pass
        release_parent_work_window(master)
        present_child_over_parent(self, master)

    def _activate_initial_overview(self, tabs) -> None:
        # Use the same CTkTabview callback path as a real user click.  Calling
        # tabs.set() alone can leave the segmented button selected while the
        # corresponding frame is still unmapped on the first Windows layout.
        try:
            callback = getattr(tabs, "_segmented_button_callback", None)
            segmented = getattr(tabs, "_segmented_button", None)
            if callable(callback) and segmented is not None:
                segmented.set("Arkivdeler")
                callback("Arkivdeler")
                self.update_idletasks()
                segmented.set("Oversikt")
                callback("Oversikt")
                self.update_idletasks()
            else:
                tabs.set("Arkivdeler")
                self.update_idletasks()
                tabs.set("Oversikt")
                self.update_idletasks()
        except Exception:
            pass

    def _activate_archive_parts_tab(self) -> None:
        # a22 schedules this virtual method with after_idle().  In the final
        # result centre the initial page is Oversikt, so make that delayed call
        # perform the same real transition after the window has entered the Tk
        # event loop.  This is the last point at which CTkTabview can otherwise
        # end up with a highlighted Oversikt button and no mapped content frame.
        tabs = self._root_tabview()
        if tabs is not None:
            self._activate_initial_overview(tabs)

    def _build_technical_tab(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            tab,
            text="Teknisk resultatgrunnlag",
            anchor="w",
            font=theme.font(theme.HEADER_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        inner = ctk.CTkTabview(tab)
        inner.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        for name in ("Noark 5-tester", "Vurderingspunkter", "Arkade 5"):
            inner.add(name)
        self._fill_readonly_text(inner.tab("Noark 5-tester"), self._technical_text())
        self._fill_readonly_text(inner.tab("Vurderingspunkter"), self._review_text())
        self._fill_readonly_text(inner.tab("Arkade 5"), self._arkade_text())

    def _replace_pronom_text_with_table(self, tab) -> None:
        old = getattr(self, "_a14_pronom_text", None)
        if old is not None:
            try:
                old.destroy()
            except Exception:
                pass

        tab.grid_rowconfigure(1, weight=1)
        panel = ctk.CTkFrame(tab, fg_color="transparent")
        panel.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        arkade = ((self.model.get("external_validation") or {}).get("arkade5") or {})
        summary = arkade.get("pronom_summary") or {}
        imports = list(arkade.get("imports") or [])
        ctk.CTkLabel(
            panel,
            text=(
                f"Statistikksett: {summary.get('statistics_imports', 0)}   |   "
                f"Rader: {summary.get('statistics_rows', 0)}   |   "
                f"Filer: {summary.get('total_files', 0)}   |   "
                f"Unike Format-ID: {summary.get('unique_format_ids', 0)}"
            ),
            anchor="w",
            text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        table = ctk.CTkScrollableFrame(panel)
        table.grid(row=1, column=0, sticky="nsew")
        headers = ("Format-ID / PUID", "Filtype", "Formatversjon", "RAF-220301", "Antall")
        weights = (0, 1, 0, 0, 0)
        for col, (heading, weight) in enumerate(zip(headers, weights)):
            table.grid_columnconfigure(col, weight=weight, minsize=(135 if col == 0 else 90))
            ctk.CTkLabel(
                table, text=heading, anchor="w",
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(row=0, column=col, sticky="ew", padx=6, pady=(4, 7))

        row_no = 1
        for item in imports:
            pronom = item.get("pronom") or {}
            if not pronom.get("available"):
                continue
            stats = pronom.get("statistics") or {}
            for data in list(stats.get("rows") or []):
                values = (
                    data.get("format_id") or "–",
                    data.get("file_type") or "–",
                    data.get("format_version") or "–",
                    data.get("raf_220301") or "–",
                    data.get("count") if data.get("count") is not None else "–",
                )
                for col, value in enumerate(values):
                    ctk.CTkLabel(
                        table,
                        text=str(value),
                        anchor="w" if col < 4 else "e",
                        justify="left",
                        font=theme.font(theme.SMALL_SIZE),
                    ).grid(row=row_no, column=col, sticky="ew", padx=6, pady=2)
                row_no += 1

        if row_no == 1:
            ctk.CTkLabel(
                table,
                text="Ingen PRONOM-statistikk er materialisert i depotrapporten.",
                anchor="w",
                text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=1, column=0, columnspan=5, sticky="ew", padx=6, pady=8)
