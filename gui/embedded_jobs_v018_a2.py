"""v0.1.8-a2: compact, single-window CustomTkinter workbench.

This is an adapter above the existing GUI/runtime, NOT a second job engine.
It never scans the source or reads reports while rendering job rows.
The original full job list remains available for advanced operations.
"""
from __future__ import annotations

import customtkinter as ctk
from tkinter import TclError

from app.workbench_snapshot_v018_a2 import clamp_geometry, elide_path, job_rows
from . import theme


_MENU_ACTIONS = (
    "Handlinger ...", "Mapper", "Standard", "Setup", "Mottak / Ingest",
    "Metadata", "KDRS Query", "Rapport", "Innstillinger", "Full jobbliste",
)


class EmbeddedJobsMixin:
    """Adds a reusable embedded Jobs view without changing historical runners."""

    def _a2_install_workbench(self) -> None:
        if getattr(self, "_a2_installed", False):
            return
        self._a2_installed = True
        self._a2_page = "workflow"
        self._a2_legacy_visible = False
        self._a2_rows = {}
        self._a2_row_ids = ()

        # Preserve the historical header and its actions, but make it optional.
        self._a2_legacy_header = self.active_job_label.master
        self._a2_legacy_header.grid_configure(row=1, column=0, columnspan=2)
        self._a2_legacy_header.grid_remove()

        # Existing panels remain intact, merely moved down one grid row.
        self.left.grid_configure(row=2)
        self.right.grid_configure(row=2)
        self.status_bar.grid_configure(row=3)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=0)

        bar = ctk.CTkFrame(self, fg_color=theme.SURFACE_BG, corner_radius=0)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        bar.grid_columnconfigure(1, weight=1)
        self._a2_bar = bar
        ctk.CTkLabel(
            bar, text="DWM  v0.1.8-a2", font=theme.font(theme.NORMAL_SIZE, "bold"),
            text_color=theme.BLUE,
        ).grid(row=0, column=0, padx=(12, 12), pady=8, sticky="w")
        self._a2_active_label = ctk.CTkLabel(
            bar, text="Jobbliste", anchor="w", text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE),
        )
        self._a2_active_label.grid(row=0, column=1, padx=4, pady=8, sticky="ew")
        self._a2_jobs_tab = ctk.CTkButton(
            bar, text="Jobber", width=88, command=self._a2_show_jobs,
            fg_color=theme.BLUE_DIM, hover_color=theme.BLUE,
        )
        self._a2_jobs_tab.grid(row=0, column=2, padx=3, pady=7)
        self._a2_flow_tab = ctk.CTkButton(
            bar, text="Arbeidsflyt", width=102, command=self._a2_show_workflow,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        )
        self._a2_flow_tab.grid(row=0, column=3, padx=3, pady=7)
        self._a2_menu = ctk.CTkOptionMenu(
            bar, values=list(_MENU_ACTIONS), width=130,
            command=self._a2_menu_action,
        )
        self._a2_menu.grid(row=0, column=4, padx=(8, 3), pady=7)
        self._a2_menu.set(_MENU_ACTIONS[0])
        self._a2_header_button = ctk.CTkButton(
            bar, text="Vis full topplinje", width=134,
            command=self._a2_toggle_legacy_header,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        )
        self._a2_header_button.grid(row=0, column=5, padx=(3, 12), pady=7)

        panel = ctk.CTkFrame(self, fg_color=theme.APP_BG, corner_radius=0)
        panel.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=10, pady=4)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(2, weight=1)
        self._a2_jobs_panel = panel
        label = ctk.CTkLabel(
            panel, text="JOBBER", font=theme.font(theme.TITLE_SIZE, "bold"),
            text_color=theme.BLUE, anchor="w",
        )
        label.grid(row=0, column=0, padx=8, pady=(6, 1), sticky="ew")
        self._a2_list_path_label = ctk.CTkLabel(
            panel, text="Ingen jobbliste", anchor="w", text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE),
        )
        self._a2_list_path_label.grid(row=1, column=0, padx=8, pady=(0, 6), sticky="ew")

        listing = ctk.CTkScrollableFrame(panel, fg_color=theme.APP_BG, corner_radius=0)
        listing.grid(row=2, column=0, sticky="nsew", padx=4, pady=2)
        listing.grid_columnconfigure(0, weight=1)
        self._a2_listing = listing

        footer = ctk.CTkFrame(panel, fg_color=theme.SURFACE_BG, corner_radius=6)
        footer.grid(row=3, column=0, sticky="ew", padx=4, pady=(6, 2))
        self._a2_new_list_button = self._a2_footer_button(footer, "Ny jobbliste", self._a2_new_list)
        self._a2_open_list_button = self._a2_footer_button(footer, "Åpne ...", self._a2_open_list)
        self._a2_save_button = self._a2_footer_button(footer, "Lagre", self._a2_save_list)
        self._a2_new_job_button = self._a2_footer_button(footer, "+ Ny jobb", self._a2_create_job)
        self._a2_full_list_button = self._a2_footer_button(footer, "Full jobbliste", self._open_jobs)
        self._a2_start_button = self._a2_footer_button(footer, "Start alle", self._start_all_jobs, primary=True)
        self._a2_stop_button = self._a2_footer_button(footer, "Stopp", self._stop_batch)

        # Show the integrated view by default. Advanced Jobbliste is opt-in.
        self._a2_show_jobs()
        self.after(800, self._a2_fit_main_window)
        self.after(1000, self._a2_poll)

    def _a2_footer_button(self, parent, text, callback, *, primary=False):
        button = ctk.CTkButton(
            parent, text=text, width=94 if len(text) <= 10 else 112,
            command=callback, fg_color=theme.BLUE_DIM if primary else theme.BUTTON_BG,
            hover_color=theme.BLUE if primary else theme.BUTTON_HOVER,
        )
        button.pack(side="left", padx=(5, 0), pady=8)
        return button

    def _a2_toggle_legacy_header(self):
        self._a2_legacy_visible = not self._a2_legacy_visible
        if self._a2_legacy_visible:
            self._a2_legacy_header.grid()
            self._a2_header_button.configure(text="Skjul full topplinje")
        else:
            self._a2_legacy_header.grid_remove()
            self._a2_header_button.configure(text="Vis full topplinje")

    def _a2_menu_action(self, selection: str) -> None:
        self._a2_menu.set(_MENU_ACTIONS[0])
        if selection == "Full jobbliste":
            self._open_jobs()
            return
        # Invoke the existing button rather than duplicate historical logic.
        for child in self._a2_legacy_header.winfo_children():
            if isinstance(child, ctk.CTkButton):
                try:
                    label = str(child.cget("text"))
                except Exception:
                    continue
                if label == selection:
                    child.invoke()
                    return
        self.status_bar.set_status(f"Handling kan åpnes fra full topplinje: {selection}")
        if not self._a2_legacy_visible:
            self._a2_toggle_legacy_header()

    def _a2_show_jobs(self):
        self._a2_page = "jobs"
        self.left.grid_remove()
        self.right.grid_remove()
        self._a2_jobs_panel.grid()
        self._a2_jobs_tab.configure(fg_color=theme.BLUE_DIM)
        self._a2_flow_tab.configure(fg_color=theme.BUTTON_BG)
        self._a2_refresh_jobs()

    def _a2_show_workflow(self):
        self._a2_page = "workflow"
        self._a2_jobs_panel.grid_remove()
        self.left.grid()
        self.right.grid()
        self._a2_jobs_tab.configure(fg_color=theme.BUTTON_BG)
        self._a2_flow_tab.configure(fg_color=theme.BLUE_DIM)

    def _a2_open_job(self, job_id: str):
        job = self.jobs.get(job_id)
        if job is None:
            self._a2_refresh_jobs()
            return
        self._open_job(job)
        self._a2_show_workflow()
        self._a2_refresh_jobs()

    def _a2_create_job(self):
        self._create_job(None)
        self._a2_refresh_jobs()

    def _a2_new_list(self):
        self._new_job_list()
        self._a2_refresh_jobs()

    def _a2_open_list(self):
        self._open_job_list_dialog()
        self._a2_refresh_jobs()

    def _a2_save_list(self):
        self._save_job_list()
        self._a2_refresh_jobs()

    def _a2_refresh_jobs(self):
        if not getattr(self, "_a2_installed", False):
            return
        active = getattr(self, "current_job", None)
        active_id = active.job_id if active is not None else None
        snapshots = job_rows(self.jobs.jobs(), active_id)
        self._a2_active_label.configure(
            text=f"Aktiv: {active_id}  |  {active.name}" if active_id else "Ingen aktiv jobb"
        )
        path = getattr(self, "job_list_path", None)
        self._a2_list_path_label.configure(
            text=f"Jobbliste: {elide_path(str(path), 130)}" if path else "Jobbliste: (ikke lagret)"
        )
        if self._a2_page != "jobs":
            return
        ids = tuple(j.job_id for j in snapshots)
        if ids != self._a2_row_ids:
            for child in self._a2_listing.winfo_children():
                child.destroy()
            self._a2_rows.clear()
            for position, item in enumerate(snapshots):
                self._a2_rows[item.job_id] = self._a2_build_row(position, item)
            self._a2_row_ids = ids

        for item in snapshots:
            view = self._a2_rows[item.job_id]
            view["card"].configure(
                border_color=theme.BLUE if item.active else theme.CARD_BORDER,
                border_width=2 if item.active else 1,
            )
            view["name"].configure(text=elide_path(item.name, 60))
            view["status"].configure(text=f"{item.status}   {item.percentage}%")
            view["paths"].configure(
                text=f"Source: {elide_path(item.source, 100)}\n"
                     f"Work operations: {elide_path(item.work_operations, 100)}"
            )
            view["button"].configure(text="Åpne arbeidsflyt" if item.active else "Velg / åpne")

        running = bool(getattr(self, "batch_running", False)) or any(
            item.status == "Kjører" for item in snapshots
        )
        for button in (self._a2_new_list_button, self._a2_open_list_button,
                       self._a2_new_job_button, self._a2_start_button):
            button.configure(state="disabled" if running else "normal")
        self._a2_stop_button.configure(state="normal" if running else "disabled")

    def _a2_build_row(self, position, item):
        card = ctk.CTkFrame(
            self._a2_listing, fg_color=theme.CARD_BG, border_width=1,
            border_color=theme.CARD_BORDER, corner_radius=8,
        )
        card.grid(row=position, column=0, sticky="ew", padx=6, pady=4)
        card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            card, text=item.job_id, width=90, anchor="w",
            font=theme.font(theme.NORMAL_SIZE, "bold"),
            text_color=theme.TEXT,
        ).grid(row=0, column=0, padx=(12, 4), pady=(8, 2), sticky="w")
        name = ctk.CTkLabel(card, text="", anchor="w", text_color=theme.TEXT,
                            font=theme.font(theme.NORMAL_SIZE))
        name.grid(row=0, column=1, padx=4, pady=(8, 2), sticky="ew")
        status = ctk.CTkLabel(card, text="", width=145, anchor="e",
                              text_color=theme.TEXT_SUB, font=theme.font(theme.SMALL_SIZE))
        status.grid(row=0, column=2, padx=4, pady=(8, 2), sticky="e")
        button = ctk.CTkButton(
            card, text="Velg / åpne", width=130,
            command=lambda jid=item.job_id: self._a2_open_job(jid),
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        )
        button.grid(row=0, column=3, padx=(5, 12), pady=(8, 2))
        paths = ctk.CTkLabel(card, text="", anchor="w", justify="left",
                             text_color=theme.TEXT_MUTED,
                             font=theme.font(theme.SMALL_SIZE))
        paths.grid(row=1, column=0, columnspan=4, padx=12, pady=(0, 9), sticky="ew")
        return {"card": card, "name": name, "status": status, "button": button, "paths": paths}

    def _a2_poll(self):
        try:
            if not self.winfo_exists():
                return
            self._a2_refresh_jobs()
            self.after(1000, self._a2_poll)
        except TclError:
            return

    def _a2_fit_main_window(self):
        """Initial/monitor-change safety; never resize a maximized window."""
        try:
            if not self.winfo_exists():
                return
            from .window_geometry import current_monitor_work_area
            area = current_monitor_work_area(self)
            # Update minimum size even when maximized. A later restore must
            # remain usable on a small laptop screen.
            self.minsize(min(860, max(1, area.width - 24)),
                         min(540, max(1, area.height - 24)))
            if self.state() in ("zoomed", "iconic"):
                return
            x, y, w, h = clamp_geometry(
                int(self.winfo_x()), int(self.winfo_y()),
                max(1, int(self.winfo_width())), max(1, int(self.winfo_height())),
                monitor_x=area.x, monitor_y=area.y,
                monitor_width=area.width, monitor_height=area.height,
            )
            if (x, y, w, h) != (
                self.winfo_x(), self.winfo_y(), self.winfo_width(), self.winfo_height()
            ):
                self.geometry(f"{w}x{h}{x:+d}{y:+d}")
        except Exception:
            # A monitor/DPI transition must never prevent startup.
            return
