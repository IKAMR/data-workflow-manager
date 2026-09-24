from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_views import archive_part_label, archive_part_target
from .depot_result_views_a21 import DepotResultViewsDialogA21


_PRIMARY_FIELDS = (
    ("folder_count", "Mapper"),
    ("registration_count", "Registreringer"),
    ("journalpost_count", "Journalposter"),
    ("document_description_count", "Dok.beskrivelser"),
    ("document_object_count", "Dok.objekter"),
)

_SECONDARY_FIELDS = (
    ("screening_count", "Skjerminger"),
    ("disposal_decision_count", "Kassasjonsvedtak"),
    ("performed_disposal_count", "Utført kassasjon"),
    ("deletion_count", "Slettinger"),
)


def _display(value) -> str:
    return "–" if value in (None, "") else str(value)


def _identity(row: dict, index: int) -> tuple[str, str]:
    identity = row.get("archive_part") or {}
    system_id = str(identity.get("system_id") or "").strip()
    title = str(identity.get("title") or identity.get("name") or "").strip()
    if not system_id:
        system_id = f"Arkivdel {index + 1}"
    if not title:
        title = "Uten tittel"
    return system_id, title


class DepotResultViewsDialogA22(DepotResultViewsDialogA21):
    """v0.1.6-a2: archive-part-first review surface for Noark 5 results."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.title("Vurdering av uttrekk – Noark 5")
        self.geometry("1180x800")
        self.minsize(900, 640)
        self.after_idle(self._activate_archive_parts_tab)

    def _activate_archive_parts_tab(self) -> None:
        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child, ctk.CTkTabview):
                    return child
                found = walk(child)
                if found is not None:
                    return found
            return None

        tabs = walk(self)
        if tabs is not None:
            try:
                tabs.set("Arkivdeler")
            except Exception:
                pass

    def _build_archive_parts_tab(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=0, minsize=330)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        self._archive_parts = list(self.model.get("archive_parts") or [])
        self._archive_labels = [
            archive_part_label(row, index)
            for index, row in enumerate(self._archive_parts)
        ]
        self._archive_index = 0
        self._archive_buttons: list[ctk.CTkButton] = []

        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 10))
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

        if not self._archive_parts:
            ctk.CTkLabel(
                tab,
                text="Ingen arkivdelsresultater er materialisert i rapporten.",
                anchor="w",
                text_color=theme.TEXT_MUTED,
            ).grid(row=1, column=0, columnspan=2, sticky="nw", padx=8, pady=8)
            return

        navigation = ctk.CTkScrollableFrame(tab, width=320)
        navigation.grid(row=1, column=0, sticky="nsew", padx=(8, 5), pady=(0, 8))
        navigation.grid_columnconfigure(0, weight=1)

        for index, row in enumerate(self._archive_parts):
            system_id, title = _identity(row, index)
            compact = (
                f"{system_id}\n{title}\n"
                f"Mapper {_display(row.get('folder_count'))}  |  "
                f"Reg. {_display(row.get('registration_count'))}  |  "
                f"Dok.obj. {_display(row.get('document_object_count'))}"
            )
            button = ctk.CTkButton(
                navigation,
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

        self._detail = ctk.CTkFrame(tab)
        self._detail.grid(row=1, column=1, sticky="nsew", padx=(5, 8), pady=(0, 8))
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
            wraplength=760,
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

    def _show_archive_part(self, index: int) -> None:
        if not self._archive_parts:
            return
        self._archive_index = index
        row = self._archive_parts[index]
        system_id, title = _identity(row, index)

        self._archive_title.configure(text=title)
        self._archive_subtitle.configure(
            text=f"systemID: {system_id}   |   Arkivdel {index + 1} av {len(self._archive_parts)}"
        )

        for widget in self._kpi_frame.winfo_children():
            widget.destroy()
        for col, (field, label) in enumerate(_PRIMARY_FIELDS):
            card = ctk.CTkFrame(self._kpi_frame)
            card.grid(row=0, column=col, sticky="nsew", padx=4, pady=2)
            ctk.CTkLabel(
                card,
                text=_display(row.get(field)),
                font=theme.font(theme.TITLE_SIZE, weight="bold"),
            ).grid(row=0, column=0, padx=10, pady=(10, 2))
            ctk.CTkLabel(
                card,
                text=label,
                text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=1, column=0, padx=10, pady=(0, 10))

        self._secondary.configure(
            text="   |   ".join(
                f"{label}: {_display(row.get(field))}"
                for field, label in _SECONDARY_FIELDS
            )
        )

        sources = row.get("sources") or {}
        lines = [
            "SPORBARHET",
            "Nøkkeltallene over kommer fra den materialiserte depotrapporten; "
            "denne visningen kjører ingen ny analyse.",
            "",
        ]
        if sources:
            for field, label in _PRIMARY_FIELDS + _SECONDARY_FIELDS:
                source = sources.get(field)
                if not source:
                    continue
                lines.append(
                    f"{label}: test {source.get('test_id') or '–'} | "
                    f"sti {source.get('path') or '–'}"
                )
        else:
            lines.append("Ingen feltspesifikke kildereferanser er materialisert for denne arkivdelen.")

        self._traceability.configure(state="normal")
        self._traceability.delete("1.0", "end")
        self._traceability.insert("1.0", "\n".join(lines))
        self._traceability.configure(state="disabled")

        for button_no, button in enumerate(self._archive_buttons):
            try:
                button.configure(
                    fg_color=theme.BLUE_DIM if button_no == index else theme.BUTTON_BG
                )
            except Exception:
                pass

    def _open_archive_part_annotations(self) -> None:
        if not self._archive_parts:
            return
        target_id, target_label = archive_part_target(
            self._archive_parts[self._archive_index], self._archive_index
        )
        self._open_annotations(
            view_id="archive_parts",
            target_type="archive_part",
            target_id=target_id,
            target_label=target_label,
        )
