from __future__ import annotations

import customtkinter as ctk

from . import theme
from .settings_dialog_a26_3 import SettingsDialog as A26_3SettingsDialog


class SettingsDialog(A26_3SettingsDialog):
    """Arkade subfolder and a15 resource-planning settings."""

    def __init__(self, master, settings: dict, on_save):
        super().__init__(master, settings, on_save)
        self.arkade5_output_subfolder_var = ctk.StringVar(
            value=str(settings.get("arkade5_output_subfolder", "arkade5_<ver>") or "arkade5_<ver>")
        )
        self.a15_xpath_workers_var = ctk.StringVar(value=str(settings.get('noark5_xpath_workers', 0)))
        self.a15_document_workers_var = ctk.StringVar(value=str(settings.get('document_analysis_workers', 0)))
        self.a15_xpath_timeout_var = ctk.StringVar(value=str(settings.get('xpath_timeout_minutes', 0)))
        self.a15_document_timeout_var = ctk.StringVar(value=str(settings.get('document_timeout_minutes', 0)))
        self._a268_append_output_subfolder()
        self._a15_append_resource_settings()

    def _a268_append_output_subfolder(self) -> None:
        body = self._a263_find_scrollable_body(self)
        if body is None:
            return
        row = self._a263_next_grid_row(body)

        ctk.CTkLabel(
            body, text="Arkade 5 output-undermappe", font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=row, column=0, padx=12, pady=8, sticky="w")
        ctk.CTkEntry(
            body, textvariable=self.arkade5_output_subfolder_var,
            font=theme.font(theme.NORMAL_SIZE), placeholder_text="arkade5_<ver>",
        ).grid(row=row, column=1, padx=12, pady=8, sticky="ew")

        row += 1
        ctk.CTkLabel(
            body,
            text=(
                "Relativ undermappe under Work - operations. <ver> erstattes med "
                "oppdaget versjon, f.eks. arkade5_<ver> → arkade5_v2.13.1."
            ),
            font=theme.font(theme.SMALL_SIZE), text_color=theme.TEXT_MUTED,
            anchor="w", justify="left", wraplength=760,
        ).grid(row=row, column=1, padx=12, pady=(0, 12), sticky="ew")

    def _a15_append_resource_settings(self) -> None:
        body = self._a263_find_scrollable_body(self)
        if body is None:
            return
        row = self._a263_next_grid_row(body)
        ctk.CTkLabel(body, text='Ressurser for analyse (a15)',
                     font=theme.font(theme.NORMAL_SIZE, 'bold')).grid(
                         row=row, column=0, columnspan=2, padx=12, pady=(10, 6), sticky='w')
        rows = (
            ('XPath-arbeidere (0=auto)', self.a15_xpath_workers_var),
            ('Dokumentanalyse-arbeidere (0=auto)', self.a15_document_workers_var),
            ('XPath tidsgrense i minutter (0=ingen)', self.a15_xpath_timeout_var),
            ('Dokumentanalyse tidsgrense (0=ingen)', self.a15_document_timeout_var),
        )
        for label, var in rows:
            row += 1
            ctk.CTkLabel(body, text=label, font=theme.font(theme.NORMAL_SIZE)).grid(
                row=row, column=0, padx=12, pady=6, sticky='w')
            ctk.CTkEntry(body, textvariable=var, width=140).grid(
                row=row, column=1, padx=12, pady=6, sticky='w')
        row += 1
        ctk.CTkLabel(body, text=(
            'a15.1: Parametere lagres, men parallell skanning aktiveres ikke ennå. '
            'Auto gir inntil videre 1 arbeider. Parallelle jobber: 1.'),
            font=theme.font(theme.SMALL_SIZE), text_color=theme.TEXT_MUTED,
            anchor='w', justify='left', wraplength=760).grid(
                row=row, column=0, columnspan=2, padx=12, pady=(0, 12), sticky='w')

    def _collect(self) -> dict:
        from app.analysis_resources_a15 import validate_resource_settings
        updated = super()._collect()
        updated["arkade5_output_subfolder"] = (
            self.arkade5_output_subfolder_var.get().strip() or "arkade5_<ver>"
        )
        updated.update(validate_resource_settings({
            'noark5_xpath_workers': self.a15_xpath_workers_var.get(),
            'document_analysis_workers': self.a15_document_workers_var.get(),
            'xpath_timeout_minutes': self.a15_xpath_timeout_var.get(),
            'document_timeout_minutes': self.a15_document_timeout_var.get(),
        }))
        return updated

    def _load_vars(self, settings: dict) -> None:
        super()._load_vars(settings)
        if hasattr(self, "arkade5_output_subfolder_var"):
            self.arkade5_output_subfolder_var.set(
                str(settings.get("arkade5_output_subfolder", "arkade5_<ver>") or "arkade5_<ver>")
            )
        for name, key in (
            ('a15_xpath_workers_var', 'noark5_xpath_workers'),
            ('a15_document_workers_var', 'document_analysis_workers'),
            ('a15_xpath_timeout_var', 'xpath_timeout_minutes'),
            ('a15_document_timeout_var', 'document_timeout_minutes'),
        ):
            if hasattr(self, name):
                getattr(self, name).set(str(settings.get(key, 0)))
