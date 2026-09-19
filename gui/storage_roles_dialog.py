from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from app.storage_layouts import storage_layout_by_id, suggest_storage_roles
from noark5_workflow.core.job import Job
from settings import load_config, save_config
from . import theme
from .source_location_dialog import LocationChoice, StorageLocationDialog

_FIELDS = (
    ("source_root", "Source – hovedmappe", "dir"),
    ("source_tar", "Source – TAR", "file"),
    ("source_unzipped", "Source – utpakket", "dir"),
    ("source_extraction", "Source – uttrekksmappe", "dir"),
    ("work_root", "Arbeid – hovedmappe", "dir"),
    ("work_content", "Arbeid – content", "dir"),
    ("work_operations", "Arbeid – operasjoner", "dir"),
    ("archive_root", "Arkiv – hovedmappe", "dir"),
)
_LABELS = {attr: label for attr, label, _kind in _FIELDS}


class StorageRolesDialog(ctk.CTkToplevel):
    """Edit generic storage roles with role-aware suggestions."""

    def __init__(
        self,
        master,
        job: Job,
        on_save,
        *,
        blank_fallback_source_root: bool = False,
    ) -> None:
        super().__init__(master)
        self.job = job
        self.on_save = on_save
        self.vars = {}
        self.settings = load_config()
        self._location_dialog = None
        self._location_dialog_open = False
        self._choose_buttons = []

        self.title(f"Mapper – {job.job_id}")
        self.geometry("1380x660")
        self.minsize(1120, 560)
        self.configure(fg_color=theme.APP_BG)
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)

        ctk.CTkLabel(
            self,
            text="MAPPE-ROLLER",
            font=theme.font(theme.TITLE_SIZE, "bold"),
            text_color=theme.BLUE,
        ).grid(
            row=0,
            column=0,
            columnspan=3,
            padx=18,
            pady=(16, 4),
            sticky="w",
        )
        ctk.CTkLabel(
            self,
            text=(
                "Roller per jobb. Ingen fysisk DIAS- eller depotstruktur tvinges av feltene. "
                "Valgt mappeprofil kan brukes til å foreslå roller fra Source root eller "
                "Source extraction."
            ),
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
        ).grid(
            row=1,
            column=0,
            columnspan=3,
            padx=18,
            pady=(0, 8),
            sticky="w",
        )

        suggestion_bar = ctk.CTkFrame(self, fg_color="transparent")
        suggestion_bar.grid(
            row=2,
            column=0,
            columnspan=3,
            padx=18,
            pady=(0, 8),
            sticky="ew",
        )
        suggestion_bar.grid_columnconfigure(0, weight=1)

        layout_id = str(
            self.settings.get("storage_layout_profile", "ikamr_standard")
            or "none"
        )
        layout = storage_layout_by_id(layout_id)
        ctk.CTkLabel(
            suggestion_bar,
            text=f"Mappeprofil: {layout.label}",
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_SUB,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self.fill_suggestions_button = ctk.CTkButton(
            suggestion_bar,
            text="Fyll ut forslag",
            width=120,
            fg_color=theme.BLUE_DIM,
            hover_color=theme.BLUE,
            command=self._fill_suggestions,
        )
        self.fill_suggestions_button.grid(
            row=0,
            column=1,
            padx=(12, 0),
            sticky="e",
        )

        for row, (attr, label, kind) in enumerate(_FIELDS, start=3):
            ctk.CTkLabel(
                self,
                text=label,
                width=210,
                font=theme.font(theme.SMALL_SIZE),
                anchor="w",
            ).grid(
                row=row,
                column=0,
                padx=(18, 8),
                pady=5,
                sticky="w",
            )

            value = getattr(job, attr)
            if (
                blank_fallback_source_root
                and attr == "source_root"
                and job.source_extraction is not None
                and value == job.source_extraction
            ):
                value = None

            var = ctk.StringVar(value=str(value) if value else "")
            self.vars[attr] = var
            ctk.CTkEntry(
                self,
                textvariable=var,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(
                row=row,
                column=1,
                padx=4,
                pady=5,
                sticky="ew",
            )

            button = ctk.CTkButton(
                self,
                text="Velg...",
                width=76,
                fg_color=theme.BUTTON_BG,
                hover_color=theme.BUTTON_HOVER,
                command=lambda a=attr, k=kind: self._choose(a, k),
            )
            button.grid(
                row=row,
                column=2,
                padx=(8, 18),
                pady=5,
            )
            self._choose_buttons.append(button)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(
            row=21,
            column=0,
            columnspan=3,
            padx=18,
            pady=18,
            sticky="e",
        )
        ctk.CTkButton(
            buttons,
            text="Avbryt",
            width=90,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self.destroy,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            buttons,
            text="Lagre",
            width=90,
            fg_color=theme.BLUE_DIM,
            hover_color=theme.BLUE,
            command=self._save,
        ).pack(side="left", padx=4)

    def _set_choose_buttons_state(self, state: str) -> None:
        for button in self._choose_buttons:
            try:
                button.configure(state=state)
            except Exception:
                pass

    def _role_history(self, attr: str) -> list[Path]:
        raw = self.settings.get("recent_storage_role_paths", {})
        values = raw.get(attr, []) if isinstance(raw, dict) else []
        result = []
        for value in values if isinstance(values, list) else []:
            path = Path(str(value))
            if path.exists() and path not in result:
                result.append(path)
        return result[:10]

    def _remember_role(self, attr: str, value: Path) -> None:
        raw = self.settings.get("recent_storage_role_paths", {})
        history = dict(raw) if isinstance(raw, dict) else {}
        current = [str(item) for item in history.get(attr, []) if str(item)]
        text = str(value)
        current = [item for item in current if item != text]
        current.insert(0, text)
        history[attr] = current[:10]
        self.settings["recent_storage_role_paths"] = history
        save_config({"recent_storage_role_paths": history})

    def _forget_role(self, attr: str, path: Path) -> None:
        raw = self.settings.get("recent_storage_role_paths", {})
        history = dict(raw) if isinstance(raw, dict) else {}
        values = [
            str(item)
            for item in history.get(attr, [])
            if str(item) != str(path)
        ]
        history[attr] = values
        self.settings["recent_storage_role_paths"] = history
        save_config({"recent_storage_role_paths": history})
        kind = dict((a, k) for a, _l, k in _FIELDS)[attr]
        self.after_idle(lambda a=attr, k=kind: self._choose(a, k))

    def _current_path(self, attr: str) -> Path | None:
        value = self.vars[attr].get().strip()
        return Path(value) if value else None

    def _layout_suggestions(self) -> dict[str, Path]:
        layout_id = str(
            self.settings.get("storage_layout_profile", "ikamr_standard")
            or "none"
        )
        return suggest_storage_roles(
            source_root=self._current_path("source_root"),
            extraction_root=self._current_path("source_extraction"),
            layout_id=layout_id,
        )

    def _fill_suggestions(self) -> None:
        suggestions = self._layout_suggestions()
        if not suggestions:
            messagebox.showinfo(
                "Noark 5 Workflow Manager",
                "Ingen forslag kan beregnes.\n\n"
                "Velg Source – hovedmappe eller Source – uttrekksmappe først.",
                parent=self,
            )
            return

        changes = []
        conflicts = []
        for attr, suggested in suggestions.items():
            if attr not in self.vars:
                continue
            current = self._current_path(attr)
            if current is None:
                changes.append((attr, suggested))
            elif current != suggested:
                conflicts.append((attr, current, suggested))

        if not changes and not conflicts:
            messagebox.showinfo(
                "Noark 5 Workflow Manager",
                "Alle beregnede roller er allerede utfylt.",
                parent=self,
            )
            return

        replace_conflicts = False
        if conflicts:
            lines = [
                "Noen eksisterende verdier avviker fra mappeprofilens forslag:",
                "",
            ]
            for attr, current, suggested in conflicts[:6]:
                lines.append(
                    f"{_LABELS.get(attr, attr)}\n"
                    f"  Nå: {current}\n"
                    f"  Forslag: {suggested}"
                )
            if len(conflicts) > 6:
                lines.append(f"... og {len(conflicts) - 6} til")
            lines.extend(
                [
                    "",
                    "Ja = erstatt også avvikende eksisterende verdier.",
                    "Nei = fyll bare tomme felt og behold eksisterende verdier.",
                ]
            )
            replace_conflicts = messagebox.askyesno(
                "Fyll ut forslag",
                "\n".join(lines),
                parent=self,
            )

        for attr, suggested in changes:
            self.vars[attr].set(str(suggested))

        if replace_conflicts:
            for attr, _current, suggested in conflicts:
                self.vars[attr].set(str(suggested))

    def _suggestions(self, attr: str) -> list[Path]:
        """Safe convenience suggestions; never write these without user choice."""
        suggestions = []
        layout_value = self._layout_suggestions().get(attr)
        if layout_value is not None:
            suggestions.append(layout_value)

        work_root = self._current_path("work_root")
        if work_root:
            if attr == "work_content":
                suggestions.append(work_root / "content")
            elif attr == "work_operations":
                suggestions.append(work_root / "repository_operations")
            elif attr == "archive_root":
                suggestions.append(work_root / "aip")

        result = []
        for path in suggestions:
            if path not in result:
                result.append(path)
        return result

    def _choices(self, attr: str) -> list[LocationChoice]:
        choices = []
        current = self._current_path(attr)
        if current:
            choices.append(LocationChoice("Gjeldende", current, False))
        for path in self._suggestions(attr):
            choices.append(LocationChoice("Forslag", path, False))
        for path in self._role_history(attr):
            choices.append(LocationChoice("Sist brukt", path, True))
        return choices

    def _initial_for_role(self, attr: str, kind: str) -> Path | None:
        current = self._current_path(attr)
        if current:
            return current
        suggestions = self._suggestions(attr)
        if suggestions:
            return suggestions[0]
        history = self._role_history(attr)
        return history[0] if history else None

    def _choose(self, attr: str, kind: str) -> None:
        if self._location_dialog_open:
            dialog = self._location_dialog
            if dialog is not None:
                try:
                    if dialog.winfo_exists():
                        dialog.focus()
                        dialog.lift()
                except Exception:
                    pass
            return

        self._location_dialog_open = True
        self._set_choose_buttons_state("disabled")
        label = _LABELS[attr]

        try:
            dialog = StorageLocationDialog(
                self,
                title=f"Velg {label}",
                heading=label.upper(),
                description=(
                    "Velg gjeldende, foreslått eller tidligere sted. "
                    "Bruk «Annen mappe/fil» for vanlig filsystemvalg."
                ),
                choices=self._choices(attr),
                initial_path=self._initial_for_role(attr, kind),
                kind=kind,
                on_choose=lambda path, a=attr: self._role_chosen(a, path),
                on_remove=lambda path, a=attr: self._forget_role(a, path),
                filetypes=(
                    [("TAR", "*.tar"), ("Alle filer", "*.*")]
                    if kind == "file"
                    else None
                ),
            )
            self._location_dialog = dialog
            dialog.bind(
                "<Destroy>",
                lambda event, d=dialog: self._location_closed(d, event),
                add="+",
            )
        except Exception:
            self._location_dialog = None
            self._location_dialog_open = False
            self._set_choose_buttons_state("normal")
            raise

    def _location_closed(self, dialog, event=None) -> None:
        if event is not None and getattr(event, "widget", None) is not dialog:
            return
        if self._location_dialog is dialog:
            self._location_dialog = None
        self._location_dialog_open = False
        self._set_choose_buttons_state("normal")

    def _role_chosen(self, attr: str, path: Path) -> None:
        self.vars[attr].set(str(path))
        self._remember_role(attr, path)

    def _save(self) -> None:
        values = {
            name: (Path(text) if (text := var.get().strip()) else None)
            for name, var in self.vars.items()
        }
        self.on_save(values)
        self.destroy()
