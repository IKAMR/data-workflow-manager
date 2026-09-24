
from __future__ import annotations

import os
import shutil
from pathlib import Path

import customtkinter as ctk

from . import theme


class StatusBar(ctk.CTkFrame):
    """Persistent status bar with priority-based adaptive compression.

    Priority:
      1. Right-side runtime context remains visible.
      2. Effective Work path remains visible.
      3. Job-list path yields first as width decreases.
      4. Transient status text is shortened before runtime context disappears.
    """

    WIDE_MIN = 1900
    STANDARD_MIN = 1500
    COMPACT_MIN = 1280

    def __init__(self, master):
        super().__init__(
            master,
            fg_color=theme.APP_BG,
            corner_radius=0,
            height=theme.STATUS_HEIGHT,
        )

        # Left side is the flexible/yielding area. Middle and right keep their
        # requested width so the job-list path gives way first.
        self.grid_columnconfigure(0, weight=1, minsize=80)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=0)

        # Keep established literal defaults for backwards compatibility/tests.
        self.left_var = ctk.StringVar(value="Jobbliste: [ikke lagret]")
        self.status_var = ctk.StringVar(value="Klar")
        self.right_var = ctk.StringVar(value="")

        self._job_list_path: Path | None = None
        self._status_text = "Klar"
        self._work_text = ""
        self._username = ""
        self._threads = os.cpu_count() or 1
        self._detection = "--"
        self._backend = "lokal"
        self._free_gib: float | None = None
        self._display_mode = "standard"

        self.left_label = ctk.CTkLabel(
            self,
            textvariable=self.left_var,
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        self.left_label.grid(row=0, column=0, padx=(10, 6), pady=3, sticky="ew")

        self.status_label = ctk.CTkLabel(
            self,
            textvariable=self.status_var,
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT,
            anchor="center",
        )
        self.status_label.grid(row=0, column=1, padx=6, pady=3, sticky="e")

        self.right_label = ctk.CTkLabel(
            self,
            textvariable=self.right_var,
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
            anchor="e",
        )
        self.right_label.grid(row=0, column=2, padx=(6, 10), pady=3, sticky="e")

        self.bind("<Configure>", self._on_configure, add="+")
        self._refresh_all()

    @staticmethod
    def _ellipsize(text: str, limit: int) -> str:
        value = str(text or "")
        if len(value) <= limit:
            return value
        if limit <= 3:
            return value[:limit]
        return value[: max(1, limit - 1)].rstrip() + "…"

    @staticmethod
    def _compact_path(path: Path, *, keep_parents: int = 1) -> str:
        parts = path.parts
        if len(parts) <= keep_parents + 1:
            return str(path)
        return str(Path("…", *parts[-(keep_parents + 1):]))

    def _mode_for_width(self_or_width, width: int | None = None) -> str:
        """Support both instance calls and historical direct test calls."""
        actual_width = self_or_width if width is None else width
        if actual_width >= StatusBar.WIDE_MIN:
            return "wide"
        if actual_width >= StatusBar.STANDARD_MIN:
            return "standard"
        if actual_width >= StatusBar.COMPACT_MIN:
            return "compact"
        return "narrow"

    def _on_configure(self, event) -> None:
        width = int(getattr(event, "width", 0) or 0)
        if width <= 1:
            return
        mode = self._mode_for_width(width)
        if mode != self._display_mode:
            self._display_mode = mode
            self._refresh_all()

    def _left_text(self) -> str:
        path = self._job_list_path
        if path is None:
            return (
                "Jobbliste: [ikke lagret]"
                if self._display_mode in {"wide", "standard"}
                else "[ikke lagret]"
            )

        if self._display_mode == "wide":
            return f"Jobbliste: {path}"
        if self._display_mode == "standard":
            return f"Jobbliste: {self._compact_path(path, keep_parents=1)}"
        if self._display_mode == "compact":
            return path.name
        return self._ellipsize(path.name, 26)

    def _middle_text(self) -> str:
        work = f"Arbeid: {self._work_text}" if self._work_text else ""
        status = self._status_text or ""

        if self._display_mode == "wide":
            status_limit = 56
        elif self._display_mode == "standard":
            status_limit = 34
        elif self._display_mode == "compact":
            status_limit = 20
        else:
            status_limit = 12

        status = self._ellipsize(status, status_limit)

        if work and status and status != "Klar":
            return f"{work} | {status}"
        if work:
            return work
        return status

    def _right_text(self) -> str:
        user = self._username or "--"
        detection = self._detection or "--"
        backend = self._backend or "lokal"
        free = f"{self._free_gib:,.1f} GB" if self._free_gib is not None else "-- GB"

        if self._display_mode == "wide":
            return (
                f"Bruker: {user} | Ledig: {free} | Tråder: {self._threads} | "
                f"Deteksjon: {detection} | Backend: {backend}"
            )

        if self._display_mode == "standard":
            return (
                f"{user} | {free} | {self._threads} tr. | "
                f"{detection} | {backend}"
            )

        if self._display_mode == "compact":
            return (
                f"{user} | {free.replace(' GB', 'G')} | {self._threads}t | "
                f"{detection} | {backend}"
            )

        # Even below the supported 1280 px target, keep all runtime categories.
        short_detection = "N5" if detection.casefold() == "noark 5" else self._ellipsize(detection, 6)
        short_backend = "lok" if backend.casefold() == "lokal" else self._ellipsize(backend, 4)
        return (
            f"{self._ellipsize(user, 8)} | "
            f"{free.replace(' GB', 'G')} | {self._threads}t | "
            f"{short_detection} | {short_backend}"
        )

    def _refresh_all(self) -> None:
        self.left_var.set(self._left_text())
        self.status_var.set(self._middle_text())
        self.right_var.set(self._right_text())

    def _default_runtime_text(self, detection: str = "--") -> str:
        """Backward-compatible formatter retained for older runtime layers."""
        return (
            f"Tråder: {self._threads} | "
            f"Deteksjon: {detection} | Backend: {self._backend}"
        )

    def _refresh_status(self) -> None:
        self._refresh_all()

    def _refresh_right(self) -> None:
        self._refresh_all()

    def set_status(self, text: str) -> None:
        self._status_text = str(text or "")
        self._refresh_all()

    def set_work_operations(
        self,
        base: str | Path | None,
        effective: str | Path | None,
    ) -> None:
        if effective is None:
            self._work_text = ""
            self._refresh_all()
            return

        path = Path(effective)
        parts = list(path.parts)
        shown = ""

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
        self._refresh_all()

    def set_job_list(self, path: str | Path | None) -> None:
        """Show the authoritative active job-list file in the persistent left field."""
        # Preserve established literal assignment for backwards compatibility.
        if path:
            self.left_var.set(f"Jobbliste: {Path(path)}")
            self._job_list_path = Path(path)
        else:
            self.left_var.set("Jobbliste: [ikke lagret]")
            self._job_list_path = None
        self._refresh_all()

    def set_user(self, username: str | None) -> None:
        """Show the human-facing username in the persistent status area."""
        self._username = str(username or "").strip()
        self._refresh_all()

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
        self._threads = os.cpu_count() or 1
        self._detection = str(detection or "--")
        self._free_gib = None

        if path:
            try:
                usage = shutil.disk_usage(str(path))
                self._free_gib = usage.free / (1024 ** 3)
            except OSError:
                self._free_gib = None

        self._refresh_all()
