from __future__ import annotations

import customtkinter as ctk

from version import APP_NAME, VERSION
from . import theme
from .workflow_status import STATUS_SPECS


class InfoPanel(ctk.CTkFrame):
    """Collapsible right-side information surface for contextual help.

    The panel is deliberately generic. a14.3 uses it for workflow status help,
    while later versions can add job/result/context information without taking
    permanent space from the main work area.
    """

    WIDTH = 325

    def __init__(self, master, *, on_close=None) -> None:
        super().__init__(master, fg_color=theme.SURFACE_BG, corner_radius=8, width=self.WIDTH)
        self.on_close = on_close
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=10, pady=(8, 4), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="INFO",
            font=theme.font(theme.TITLE_SIZE, "bold"),
            text_color=theme.BLUE,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            header,
            text="×",
            width=30,
            height=26,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self._close,
        ).grid(row=0, column=1, padx=(6, 0))

        self.tabs = ctk.CTkSegmentedButton(
            self,
            values=["Statusikoner", "Hjelp", "Om"],
            command=self._show_tab,
            font=theme.font(theme.SMALL_SIZE),
        )
        self.tabs.grid(row=1, column=0, padx=10, pady=(2, 6), sticky="ew")
        self.tabs.set("Statusikoner")

        self.body = ctk.CTkScrollableFrame(
            self,
            fg_color=theme.PANEL_BG_DARK,
            corner_radius=6,
        )
        self.body.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.body.grid_columnconfigure(0, weight=1)
        self._show_tab("Statusikoner")

    def _close(self) -> None:
        if callable(self.on_close):
            self.on_close()

    def _clear(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()

    def _show_tab(self, name: str) -> None:
        self._clear()
        if name == "Hjelp":
            self._render_help()
        elif name == "Om":
            self._render_about()
        else:
            self._render_statuses()

    def _render_statuses(self) -> None:
        ctk.CTkLabel(
            self.body,
            text="Statusikoner i workflow",
            font=theme.font(theme.SECTION_SIZE, "bold"),
            text_color=theme.TEXT_MAIN,
            anchor="w",
        ).grid(row=0, column=0, padx=8, pady=(8, 2), sticky="ew")
        ctk.CTkLabel(
            self.body,
            text="Ikonet til venstre for operasjonen viser gjeldende status. Hold musen over ikonet for forklaring.",
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_SUB,
            anchor="w",
            justify="left",
            wraplength=270,
        ).grid(row=1, column=0, padx=8, pady=(0, 8), sticky="ew")

        order = ["ok", "not_run", "running", "stale", "failed", "review", "skipped", "cancelled", "partial"]
        for row, key in enumerate(order, start=2):
            spec = STATUS_SPECS[key]
            item = ctk.CTkFrame(self.body, fg_color=theme.CARD_BG, corner_radius=6)
            item.grid(row=row, column=0, padx=6, pady=3, sticky="ew")
            item.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(
                item,
                text=spec.symbol,
                width=28,
                height=28,
                corner_radius=14,
                fg_color=spec.color,
                text_color="#ffffff",
                font=theme.font(theme.NORMAL_SIZE, "bold"),
            ).grid(row=0, column=0, rowspan=2, padx=(7, 8), pady=7)
            ctk.CTkLabel(
                item,
                text=spec.label,
                font=theme.font(theme.SMALL_SIZE, "bold"),
                text_color=theme.TEXT_MAIN,
                anchor="w",
            ).grid(row=0, column=1, padx=(0, 6), pady=(6, 0), sticky="ew")
            ctk.CTkLabel(
                item,
                text=spec.tooltip,
                font=theme.font(theme.SMALL_SIZE),
                text_color=theme.TEXT_SUB,
                anchor="w",
                justify="left",
                wraplength=215,
            ).grid(row=1, column=1, padx=(0, 6), pady=(0, 6), sticky="ew")

    def _render_help(self) -> None:
        text = (
            "Arbeidsflate\n\n"
            "• F9 eller knappen i topplinjen viser/skjuler dette infopanelet.\n"
            "• Panelet kan holdes skjult på mindre skjermer slik at midtfeltet får full bredde.\n"
            "• Hold musen over statusikonet ved en workflow-operasjon for detaljert status.\n• Klikk statusikonet for å åpne resultatversjoner og historikk for operasjonen.\n"
            "• Regenerer foreldede kjører bare operasjoner som er markert foreldet, i workflow-rekkefølge.\n\n"
            "Dette panelet er en generell informasjonsflate og kan senere brukes til mer kontekst for jobb, resultater og vurdering."
        )
        ctk.CTkLabel(
            self.body,
            text=text,
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_SUB,
            anchor="nw",
            justify="left",
            wraplength=270,
        ).grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

    def _render_about(self) -> None:
        text = (
            f"{APP_NAME}\n"
            f"Versjon {VERSION}\n\n"
            "Infopanelet ble innført i a14.3 som en sammenleggbar, generell høyreflate. "
            "Statusikonene bruker stabil operation_id som identitet; plasseringen i workflowen er bare visuell rekkefølge."
        )
        ctk.CTkLabel(
            self.body,
            text=text,
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_SUB,
            anchor="nw",
            justify="left",
            wraplength=270,
        ).grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
