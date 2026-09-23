
from __future__ import annotations

import os
import shutil
from pathlib import Path

import customtkinter as ctk

from . import theme


class StatusBar(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(
            master,
            fg_color=theme.APP_BG,
            corner_radius=0,
            height=theme.STATUS_HEIGHT,
        )
        self.grid_columnconfigure(1, weight=1)
        self.left_var = ctk.StringVar(value="Jobbliste: [ikke lagret]")
        self.status_var = ctk.StringVar(value="Klar")
        self.right_var = ctk.StringVar(value="")

        self._status_text = "Klar"
        self._work_text = ""
        self._runtime_text = self._default_runtime_text()
        self._user_text = "Bruker: --"
        self._refresh_status()
        self._refresh_right()

        self.left_label = ctk.CTkLabel(
            self,
            textvariable=self.left_var,
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        self.left_label.grid(row=0, column=0, padx=10, pady=3, sticky="w")

        ctk.CTkLabel(
            self,
            textvariable=self.status_var,
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT,
        ).grid(row=0, column=1, padx=10, pady=3)

        ctk.CTkLabel(
            self,
            textvariable=self.right_var,
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
        ).grid(row=0, column=2, padx=10, pady=3, sticky="e")

    def _default_runtime_text(self, detection: str = "--") -> str:
        return (
            f"Tråder: {os.cpu_count() or 1} | "
            f"Deteksjon: {detection} | Backend: lokal"
        )

    def _refresh_status(self) -> None:
        if self._work_text:
            self.status_var.set(
                f"Arbeid: {self._work_text} | {self._status_text}"
            )
        else:
            self.status_var.set(self._status_text)

    def _refresh_right(self) -> None:
        self.right_var.set(f"{self._user_text} | {self._runtime_text}")

    def set_status(self, text: str) -> None:
        self._status_text = str(text or "")
        self._refresh_status()

    def set_work_operations(
        self,
        base: str | Path | None,
        effective: str | Path | None,
    ) -> None:
        if effective is None:
            self._work_text = ""
            self._refresh_status()
            return

        path = Path(effective)
        parts = list(path.parts)
        shown = ""

        # Prefer the meaningful path below repository_operations.
        for index, part in enumerate(parts):
            if part.casefold() == "repository_operations":
                relative = parts[index + 1 :]
                if relative:
                    shown = str(Path(*relative))
                break

        if not shown and base is not None:
            try:
                shown = str(path.relative_to(Path(base).parent))
            except (ValueError, OSError):
                pass

        if not shown:
            shown = str(path)

        self._work_text = shown
        self._refresh_status()

    def set_job_list(self, path: str | Path | None) -> None:
        """Show the authoritative active job-list file in the persistent left field."""
        if path:
            self.left_var.set(f"Jobbliste: {Path(path)}")
        else:
            self.left_var.set("Jobbliste: [ikke lagret]")

    def set_user(self, username: str | None) -> None:
        """Show the human-facing username in the persistent status area."""
        value = (username or "").strip()
        self._user_text = f"Bruker: {value}" if value else "Bruker: --"
        self._refresh_right()

    def set_temp(self, temp_dir: str | None) -> None:
        """Backward-compatible no-op.

        The temp directory is configuration, not active work context, and is
        available through Settings. Older runtime layers may still call this.
        """
        return None

    def update_storage(
        self,
        path: str | Path | None,
        detection: str = "Noark 5",
    ) -> None:
        threads = os.cpu_count() or 1
        if not path:
            self._runtime_text = (
                f"Tråder: {threads} | Deteksjon: {detection} | Backend: lokal"
            )
            self._refresh_right()
            return

        try:
            usage = shutil.disk_usage(str(path))
            free_gib = usage.free / (1024 ** 3)
            self._runtime_text = (
                f"Ledig: {free_gib:,.1f} GB | Tråder: {threads} | "
                f"Deteksjon: {detection} | Backend: lokal"
            )
        except OSError:
            self._runtime_text = (
                f"Tråder: {threads} | Deteksjon: {detection} | Backend: lokal"
            )
        self._refresh_right()
