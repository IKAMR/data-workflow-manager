from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_views import archive_part_label, archive_part_target
from .depot_result_views_a22 import (
    DepotResultViewsDialogA22,
    _PRIMARY_FIELDS,
    _SECONDARY_FIELDS,
    _display,
    _identity,
)


class DepotResultViewsDialogA23(DepotResultViewsDialogA22):
    """v0.1.6-a3: faster archive-part navigation for large Noark 5 extracts."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.title("Vurdering av uttrekk – Noark 5")
        self.geometry("1240x820")
        self.minsize(940, 650)

    def _build_archive_parts_tab(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=0, minsize=350)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        self._archive_parts = list(self.model.get("archive_parts") or [])
        self._archive_labels = [
            archive_part_label(row, index)
            for index, row in enumerate(self._archive_parts)
        ]
        self._archive_index = 0
        self._archive_buttons: list[ctk.CTkButton] = []
        self._archive_search_text: list[str] = []

        technical = self.model.get("technical_validation") or {}
        deviations = [
            item for item in (self.model.get("deviations") or [])
            if bool(item.get("requires_review"))
        ]
        external = (self.model.get("external_validation") or {}).get("arkade5") or {}
        external_count = len(external.get("imports") or [])

        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 6))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Arkivdeler – vurderingsoversikt",
            anchor="w",
            font=theme.font(theme.HEADER_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew")

        ctk.CTkLabel(
            header,
            text=f"{len(self._archive_parts)} arkivdel(er)",
            anchor="e",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0, column=1, sticky="e")

        status_text = (
            f"Teknisk status: {_display(technical.get('status')).upper()}   |   "
            f"Vurderingspunkter: {len(deviations)}   |   "
            f"Arkade-kjøringer: {external_count}"
        )
        ctk.CTkLabel(
            header,
            text=status_text,
            anchor="w",
            justify="left",
            text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))

        search = ctk.CTkFrame(tab, fg_color="transparent")
        search.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
        search.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            search,
            text="Finn arkivdel",
            anchor="w",
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))

        self._archive_search_var = ctk.StringVar(value="")
        self._archive_search_entry = ctk.CTkEntry(
            search,
            textvariable=self._archive_search_var,
            placeholder_text="systemID eller tittel",
        )
        self._archive_search_entry.grid(row=0, column=1, sticky="ew")
        self._archive_search_entry.bind("<KeyRelease>", lambda _event: self._filter_archive_parts())

        ctk.CTkButton(
            search,
            text="Nullstill",
            width=86,
            command=self._clear_archive_filter,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=2, padx=(8, 0))

        if not self._archive_parts:
            ctk.CTkLabel(
                tab,
                text="Ingen arkivdelsresultater er materialisert i rapporten.",
                anchor="w",
                text_color=theme.TEXT_MUTED,
            ).grid(row=2, column=0, columnspan=2, sticky="nw", padx=8, pady=8)
            return

        self._archive_navigation = ctk.CTkScrollableFrame(tab, width=340)
        self._archive_navigation.grid(
            row=2, column=0, sticky="nsew", padx=(8, 5), pady=(0, 8)
        )
        self._archive_navigation.grid_columnconfigure(0, weight=1)

        self._archive_no_match = ctk.CTkLabel(
            self._archive_navigation,
            text="Ingen arkivdeler samsvarer med søket.",
            anchor="w",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        )

        for index, row in enumerate(self._archive_parts):
            system_id, title = _identity(row, index)
            compact = (
                f"{system_id}\n{title}\n"
                f"Mapper {_display(row.get('folder_count'))}  |  "
                f"Reg. {_display(row.get('registration_count'))}  |  "
                f"Dok.obj. {_display(row.get('document_object_count'))}"
            )
            button = ctk.CTkButton(
                self._archive_navigation,
                text=compact,
                anchor="w",
                height=72,
                command=lambda i=index: self._show_archive_part(i),
                fg_color=theme.BUTTON_BG,
                hover_color=theme.BUTTON_HOVER,
                font=theme.font(theme.SMALL_SIZE),
            )
            button.grid(row=index, column=0, sticky="ew", padx=4, pady=3)
            self._archive_buttons.append(button)
            self._archive_search_text.append(
                f"{system_id} {title}".casefold()
            )

        self._detail = ctk.CTkFrame(tab)
        self._detail.grid(row=2, column=1, sticky="nsew", padx=(5, 8), pady=(0, 8))
        self._detail.grid_columnconfigure(0, weight=1)
        self._detail.grid_rowconfigure(4, weight=1)

        self._archive_title = ctk.CTkLabel(
            self._detail,
            text="",
            anchor="w",
            justify="left",
            font=theme.font(theme.SECTION_SIZE, weight="bold"),
        )
        self._archive_title.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 2))

        self._archive_subtitle = ctk.CTkLabel(
            self._detail,
            text="",
            anchor="w",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        )
        self._archive_subtitle.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 12))

        self._kpi_frame = ctk.CTkFrame(self._detail, fg_color="transparent")
        self._kpi_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))
        for col in range(len(_PRIMARY_FIELDS)):
            self._kpi_frame.grid_columnconfigure(col, weight=1)

        self._secondary = ctk.CTkLabel(
            self._detail,
            text="",
            anchor="w",
            justify="left",
            wraplength=790,
            text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE),
        )
        self._secondary.grid(row=3, column=0, sticky="ew", padx=16, pady=(2, 8))

        self._traceability = ctk.CTkTextbox(
            self._detail,
            wrap="word",
            height=110,
            font=theme.font(theme.SMALL_SIZE),
        )
        self._traceability.grid(row=4, column=0, sticky="nsew", padx=16, pady=(0, 8))

        bottom = ctk.CTkFrame(self._detail, fg_color="transparent")
        bottom.grid(row=5, column=0, sticky="ew", padx=16, pady=(0, 14))
        bottom.grid_columnconfigure(0, weight=1)
        self.archive_annotation_button = ctk.CTkButton(
            bottom,
            text="Kommentarer til arkivdel...",
            width=180,
            state="normal" if self.report_path else "disabled",
            command=self._open_archive_part_annotations,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        )
        self.archive_annotation_button.grid(row=0, column=1, sticky="e")

        self._show_archive_part(0)

    def _filter_archive_parts(self) -> None:
        if not getattr(self, "_archive_buttons", None):
            return
        needle = self._archive_search_var.get().strip().casefold()
        visible = 0
        first_match = None

        for index, (button, searchable) in enumerate(
            zip(self._archive_buttons, self._archive_search_text)
        ):
            match = not needle or needle in searchable
            if match:
                button.grid()
                visible += 1
                if first_match is None:
                    first_match = index
            else:
                button.grid_remove()

        if visible:
            self._archive_no_match.grid_remove()
            if first_match is not None and needle:
                self._show_archive_part(first_match)
        else:
            self._archive_no_match.grid(
                row=len(self._archive_buttons) + 1,
                column=0,
                sticky="ew",
                padx=6,
                pady=10,
            )

    def _clear_archive_filter(self) -> None:
        self._archive_search_var.set("")
        self._filter_archive_parts()

    def _open_archive_part_annotations(self) -> None:
        if not self._archive_parts:
            return
        target_id, target_label = archive_part_target(
            self._archive_parts[self._archive_index],
            self._archive_index,
        )
        self._open_annotations(
            view_id="archive_parts",
            target_type="archive_part",
            target_id=target_id,
            target_label=target_label,
        )
