from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.operation_metadata import VISIBILITY_LABELS, visibility_label, visibility_value
from app.settings_portable import export_settings, import_settings, reset_settings
from app.work_output_layout import AppWorkSubfolderError, validate_app_work_subfolder
from app.workspace import run_log_dir, setup_dir, job_list_dir
from settings import save_config
from . import theme


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, master, settings: dict, on_save):
        super().__init__(master)
        self.title("Globale innstillinger")
        self.geometry("820x620")
        self.minsize(700, 520)
        self.transient(master)
        self.grab_set()
        self.settings = dict(settings)
        self.on_save = on_save

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self,
            text="Globale innstillinger",
            font=theme.font(theme.TITLE_SIZE, "bold"),
            text_color=theme.BLUE,
        ).grid(row=0, column=0, padx=24, pady=(20, 10), sticky="w")

        body = ctk.CTkScrollableFrame(self, fg_color=theme.PANEL_BG)
        body.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        body.grid_columnconfigure(1, weight=1)

        self.temp_var = ctk.StringVar(value=self.settings.get("temp_dir", ""))
        self.backend_var = ctk.StringVar(value=self.settings.get("execution_backend", "local"))
        self.endpoint_var = ctk.StringVar(value=self.settings.get("remote_endpoint", ""))
        self.storage_var = ctk.StringVar(value=self.settings.get("shared_storage_root", ""))
        self.visibility_var = ctk.StringVar(
            value=visibility_label(self.settings.get("operation_visibility", 2))
        )
        self.run_log_dir_var = ctk.StringVar(value=str(self.settings.get("run_log_dir", "")))
        self.setup_dir_var = ctk.StringVar(value=str(self.settings.get("setup_dir", "")))
        self.job_list_dir_var = ctk.StringVar(value=str(self.settings.get("job_list_dir", "")))
        self.app_work_subfolder_var = ctk.StringVar(
            value=str(self.settings.get("app_work_subfolder", "dwm"))
        )

        row = 0
        ctk.CTkLabel(
            body, text="Generelt",
            font=theme.font(theme.SECTION_SIZE, "bold"),
            text_color=theme.BLUE,
        ).grid(row=row, column=0, columnspan=2, padx=12, pady=(12, 8), sticky="w")

        row += 1
        ctk.CTkLabel(
            body, text="Temp-mappe", font=theme.font(theme.NORMAL_SIZE)
        ).grid(row=row, column=0, padx=12, pady=8, sticky="w")
        ctk.CTkEntry(
            body, textvariable=self.temp_var, font=theme.font(theme.NORMAL_SIZE)
        ).grid(row=row, column=1, padx=12, pady=8, sticky="ew")

        row += 1
        ctk.CTkLabel(
            body, text="Kjøring",
            font=theme.font(theme.SECTION_SIZE, "bold"),
            text_color=theme.BLUE,
        ).grid(row=row, column=0, columnspan=2, padx=12, pady=(20, 8), sticky="w")

        row += 1
        ctk.CTkLabel(
            body, text="Execution backend", font=theme.font(theme.NORMAL_SIZE)
        ).grid(row=row, column=0, padx=12, pady=8, sticky="w")
        ctk.CTkOptionMenu(
            body,
            variable=self.backend_var,
            values=["local", "server"],
            command=self._backend_changed,
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=row, column=1, padx=12, pady=8, sticky="ew")

        row += 1
        ctk.CTkLabel(
            body, text="Server-endepunkt", font=theme.font(theme.NORMAL_SIZE)
        ).grid(row=row, column=0, padx=12, pady=8, sticky="w")
        self.endpoint_entry = ctk.CTkEntry(
            body, textvariable=self.endpoint_var, font=theme.font(theme.NORMAL_SIZE)
        )
        self.endpoint_entry.grid(row=row, column=1, padx=12, pady=8, sticky="ew")

        row += 1
        ctk.CTkLabel(
            body, text="Delt lagringsrot", font=theme.font(theme.NORMAL_SIZE)
        ).grid(row=row, column=0, padx=12, pady=8, sticky="w")
        self.storage_entry = ctk.CTkEntry(
            body, textvariable=self.storage_var, font=theme.font(theme.NORMAL_SIZE)
        )
        self.storage_entry.grid(row=row, column=1, padx=12, pady=8, sticky="ew")

        row += 1
        ctk.CTkLabel(
            body,
            text="Operasjoner-synlighet",
            font=theme.font(theme.SECTION_SIZE, "bold"),
            text_color=theme.BLUE,
        ).grid(row=row, column=0, columnspan=2, padx=12, pady=(20, 8), sticky="w")

        row += 1
        ctk.CTkLabel(
            body, text="Vis operasjoner", font=theme.font(theme.NORMAL_SIZE)
        ).grid(row=row, column=0, padx=12, pady=8, sticky="w")
        ctk.CTkOptionMenu(
            body,
            variable=self.visibility_var,
            values=list(VISIBILITY_LABELS.values()),
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=row, column=1, padx=12, pady=8, sticky="ew")

        row += 1
        ctk.CTkLabel(
            body,
            text=(
                "Alpha = eksperimentell | Beta = under utvikling/testing | "
                "Stabil = klar for normal bruk"
            ),
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
        ).grid(row=row, column=0, columnspan=2, padx=12, pady=(0, 16), sticky="w")

        row += 1
        ctk.CTkLabel(
            body,
            text="Standardmapper i app-arbeidsområdet",
            font=theme.font(theme.SECTION_SIZE, "bold"),
            text_color=theme.BLUE,
        ).grid(row=row, column=0, columnspan=2, padx=12, pady=(20, 8), sticky="w")

        row += 1
        ctk.CTkLabel(body, text="Overordnet kjørelogg", font=theme.font(theme.NORMAL_SIZE)).grid(
            row=row, column=0, padx=12, pady=8, sticky="w"
        )
        run_log_dir_row = ctk.CTkFrame(body, fg_color="transparent")
        run_log_dir_row.grid(row=row, column=1, padx=12, pady=8, sticky="ew")
        run_log_dir_row.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(
            run_log_dir_row,
            textvariable=self.run_log_dir_var,
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            run_log_dir_row,
            text="Velg…",
            width=68,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=lambda: self._browse_standard_dir("run_log_dir", self.run_log_dir_var),
        ).grid(row=0, column=1, padx=(6, 4))
        ctk.CTkButton(
            run_log_dir_row,
            text="Bruk standard",
            width=105,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=lambda: self._use_default_dir("run_log_dir", self.run_log_dir_var),
        ).grid(row=0, column=2)
        ctk.CTkLabel(
            body,
            text=f"Standard: {run_log_dir(self._settings_with_current_temp())}",
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
        ).grid(row=row + 1, column=1, padx=12, pady=(0, 4), sticky="w")
        row += 1

        row += 1
        ctk.CTkLabel(body, text="Setup standardmappe", font=theme.font(theme.NORMAL_SIZE)).grid(
            row=row, column=0, padx=12, pady=8, sticky="w"
        )
        setup_dir_row = ctk.CTkFrame(body, fg_color="transparent")
        setup_dir_row.grid(row=row, column=1, padx=12, pady=8, sticky="ew")
        setup_dir_row.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(
            setup_dir_row,
            textvariable=self.setup_dir_var,
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            setup_dir_row,
            text="Velg…",
            width=68,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=lambda: self._browse_standard_dir("setup_dir", self.setup_dir_var),
        ).grid(row=0, column=1, padx=(6, 4))
        ctk.CTkButton(
            setup_dir_row,
            text="Bruk standard",
            width=105,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=lambda: self._use_default_dir("setup_dir", self.setup_dir_var),
        ).grid(row=0, column=2)
        ctk.CTkLabel(
            body,
            text=f"Standard: {setup_dir(self._settings_with_current_temp())}",
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
        ).grid(row=row + 1, column=1, padx=12, pady=(0, 4), sticky="w")
        row += 1

        row += 1
        ctk.CTkLabel(body, text="Jobblister standardmappe", font=theme.font(theme.NORMAL_SIZE)).grid(
            row=row, column=0, padx=12, pady=8, sticky="w"
        )
        job_list_dir_row = ctk.CTkFrame(body, fg_color="transparent")
        job_list_dir_row.grid(row=row, column=1, padx=12, pady=8, sticky="ew")
        job_list_dir_row.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(
            job_list_dir_row,
            textvariable=self.job_list_dir_var,
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            job_list_dir_row,
            text="Velg…",
            width=68,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=lambda: self._browse_standard_dir("job_list_dir", self.job_list_dir_var),
        ).grid(row=0, column=1, padx=(6, 4))
        ctk.CTkButton(
            job_list_dir_row,
            text="Bruk standard",
            width=105,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=lambda: self._use_default_dir("job_list_dir", self.job_list_dir_var),
        ).grid(row=0, column=2)
        ctk.CTkLabel(
            body,
            text=f"Standard: {job_list_dir(self._settings_with_current_temp())}",
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
        ).grid(row=row + 1, column=1, padx=12, pady=(0, 4), sticky="w")
        row += 1

        row += 1
        ctk.CTkLabel(
            body,
            text="Work-output",
            font=theme.font(theme.SECTION_SIZE, "bold"),
            text_color=theme.BLUE,
        ).grid(row=row, column=0, columnspan=2, padx=12, pady=(20, 8), sticky="w")

        row += 1
        ctk.CTkLabel(
            body,
            text="App-undermappe i Work",
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=row, column=0, padx=12, pady=8, sticky="w")
        ctk.CTkEntry(
            body,
            textvariable=self.app_work_subfolder_var,
            placeholder_text="dwm",
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=row, column=1, padx=12, pady=8, sticky="ew")

        row += 1
        ctk.CTkLabel(
            body,
            text=(
                "Standard: dwm | Blank = bruk Work - operations direkte | "
                "Jobblistens undermappe-regel legges under dette nivået."
            ),
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
        ).grid(row=row, column=0, columnspan=2, padx=12, pady=(0, 16), sticky="w")

        row += 1
        ctk.CTkLabel(
            body,
            text="Tom verdi eller «Bruk standard» = bruk standard undermappe under Temp-mappe.",
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
        ).grid(row=row, column=0, columnspan=2, padx=12, pady=(0, 16), sticky="w")

        tools = ctk.CTkFrame(self, fg_color="transparent")
        tools.grid(row=2, column=0, padx=20, pady=(2, 6), sticky="ew")
        ctk.CTkButton(
            tools, text="Eksporter setup…", command=self._export, width=130,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            tools, text="Importer setup…", command=self._import, width=130,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            tools, text="Nullstill setup", command=self._reset, width=120,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).pack(side="left", padx=6)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=3, column=0, padx=20, pady=(4, 18), sticky="e")
        ctk.CTkButton(
            buttons, text="Avbryt", command=self.destroy, width=110,
            font=theme.font(theme.NORMAL_SIZE),
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=0, padx=5)
        ctk.CTkButton(
            buttons, text="Lagre", command=self._save, width=130,
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=0, column=1, padx=5)

        self._backend_changed(self.backend_var.get())

    def _load_vars(self, settings: dict) -> None:
        self.temp_var.set(str(settings.get("temp_dir", "")))
        self.backend_var.set(str(settings.get("execution_backend", "local")))
        self.endpoint_var.set(str(settings.get("remote_endpoint", "")))
        self.storage_var.set(str(settings.get("shared_storage_root", "")))
        self.visibility_var.set(visibility_label(settings.get("operation_visibility", 2)))
        self.run_log_dir_var.set(str(settings.get("run_log_dir", "")))
        self.setup_dir_var.set(str(settings.get("setup_dir", "")))
        self.job_list_dir_var.set(str(settings.get("job_list_dir", "")))
        self.app_work_subfolder_var.set(str(settings.get("app_work_subfolder", "dwm")))

    def _backend_changed(self, value: str) -> None:
        state = "normal" if value == "server" else "disabled"
        if hasattr(self, "endpoint_entry"):
            self.endpoint_entry.configure(state=state)
            self.storage_entry.configure(state=state)

    def _collect(self) -> dict:
        updated = dict(self.settings)
        backend = self.backend_var.get()
        if backend == "server":
            backend = "local"
        updated.update(
            {
                "temp_dir": self.temp_var.get().strip(),
                "execution_backend": backend,
                "remote_endpoint": self.endpoint_var.get().strip(),
                "shared_storage_root": self.storage_var.get().strip(),
                "operation_visibility": visibility_value(self.visibility_var.get()),
                "run_log_dir": self.run_log_dir_var.get().strip(),
                "setup_dir": self.setup_dir_var.get().strip(),
                "job_list_dir": self.job_list_dir_var.get().strip(),
                "app_work_subfolder": validate_app_work_subfolder(
                    self.app_work_subfolder_var.get()
                ),
            }
        )
        return updated

    def _save(self) -> None:
        try:
            self.settings = self._collect()
        except AppWorkSubfolderError as exc:
            messagebox.showerror("Data Workflow Manager", str(exc))
            return
        self.on_save(self.settings)
        self.destroy()

    def _settings_with_current_temp(self) -> dict:
        current = dict(self.settings)
        current["temp_dir"] = self.temp_var.get().strip()
        current["run_log_dir"] = self.run_log_dir_var.get().strip()
        current["setup_dir"] = self.setup_dir_var.get().strip()
        current["job_list_dir"] = self.job_list_dir_var.get().strip()
        current["app_work_subfolder"] = self.app_work_subfolder_var.get().strip()
        return current

    def _browse_standard_dir(self, key: str, variable: ctk.StringVar) -> None:
        current = variable.get().strip()
        initialdir = current if current and Path(current).is_dir() else None
        if not initialdir:
            settings = self._settings_with_current_temp()
            fallback = {
                "run_log_dir": run_log_dir(settings),
                "setup_dir": setup_dir(settings),
                "job_list_dir": job_list_dir(settings),
            }[key]
            if fallback.is_dir():
                initialdir = str(fallback)
        kwargs = {"title": "Velg standardmappe"}
        if initialdir:
            kwargs["initialdir"] = initialdir
        folder = filedialog.askdirectory(**kwargs)
        if folder:
            variable.set(folder)

    def _use_default_dir(self, key: str, variable: ctk.StringVar) -> None:
        variable.set("")

    def _setup_initial_dir(self) -> str | None:
        settings = self._settings_with_current_temp()
        configured = setup_dir(settings)
        if configured.is_dir():
            return str(configured)
        value = str(self.settings.get("last_setup_dir", "")).strip()
        if value and Path(value).is_dir():
            return value
        return None

    def _remember_setup_dir(self, path: Path) -> None:
        folder = str(Path(path).parent)
        self.settings["last_setup_dir"] = folder
        save_config({"last_setup_dir": folder})

    def _export(self) -> None:
        kwargs = {
            "title": "Eksporter applikasjonsoppsett",
            "defaultextension": ".json",
            "filetypes": [("JSON", "*.json")],
        }
        initialdir = self._setup_initial_dir()
        if initialdir:
            kwargs["initialdir"] = initialdir
        filename = filedialog.asksaveasfilename(**kwargs)
        if not filename:
            return
        self.on_save(self._collect())
        path = export_settings(Path(filename))
        self._remember_setup_dir(path)
        messagebox.showinfo(
            "Data Workflow Manager", f"Setup eksportert til:\n{path}"
        )

    def _import(self) -> None:
        kwargs = {
            "title": "Importer applikasjonsoppsett",
            "filetypes": [("JSON", "*.json"), ("Alle filer", "*.*")],
        }
        initialdir = self._setup_initial_dir()
        if initialdir:
            kwargs["initialdir"] = initialdir
        filename = filedialog.askopenfilename(**kwargs)
        if not filename:
            return
        try:
            imported = import_settings(Path(filename))
        except (OSError, ValueError, TypeError) as exc:
            messagebox.showerror(
                "Data Workflow Manager", f"Kunne ikke importere setup:\n{exc}"
            )
            return
        self.settings = imported
        self._remember_setup_dir(Path(filename))
        self.settings["last_setup_dir"] = str(Path(filename).parent)
        self._load_vars(self.settings)
        self._backend_changed(self.backend_var.get())
        self.on_save(imported)
        messagebox.showinfo("Data Workflow Manager", "Setup importert.")

    def _reset(self) -> None:
        if not messagebox.askyesno(
            "Data Workflow Manager",
            "Nullstille alle applikasjonsinnstillinger til standardverdier?\n\n"
            "Dette inkluderer sist brukte mapper og jobbliste-referanser.",
        ):
            return
        defaults = reset_settings()
        self.settings = defaults
        self._load_vars(defaults)
        self._backend_changed(self.backend_var.get())
        self.on_save(defaults)
        messagebox.showinfo(
            "Data Workflow Manager", "Setup er nullstilt til standardverdier."
        )
