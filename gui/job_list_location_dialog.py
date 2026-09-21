from __future__ import annotations

from pathlib import Path
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

from . import theme


class JobListLocationDialog(ctk.CTkToplevel):
    """Choose a job-list file directly when opening, or a directory when saving."""

    def __init__(
        self,
        master,
        *,
        title: str,
        mode: str,
        default_dir: Path,
        recent_dirs: list[Path],
        recent_files: list[Path] | None = None,
        project_dir: Path | None = None,
        on_choose_dir: Callable[[Path], None] | None = None,
        on_choose_file: Callable[[Path], None] | None = None,
        on_remove_recent_file: Callable[[Path], None] | None = None,
    ) -> None:
        super().__init__(master)
        if mode not in {"open", "save"}:
            raise ValueError("mode must be 'open' or 'save'")

        self.title(title)
        self.transient(master)
        self.grab_set()
        self._mode = mode
        self._default_dir = Path(default_dir)
        self._project_dir = Path(project_dir) if project_dir is not None else None
        self._recent_dirs = [Path(p) for p in recent_dirs]
        self._recent_files = [Path(p) for p in (recent_files or [])]
        self._on_choose_dir = on_choose_dir
        self._on_choose_file = on_choose_file
        self._on_remove_recent_file = on_remove_recent_file

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            self,
            text="JOBBLISTE – ÅPNE" if mode == "open" else "JOBBLISTE – LAGRE SOM",
            font=theme.font(theme.TITLE_SIZE, "bold"),
            text_color=theme.BLUE,
        ).grid(row=0, column=0, padx=24, pady=(20, 6), sticky="w")

        help_text = (
            "Åpne en kjent jobbliste direkte, eller velg en annen fil."
            if mode == "open"
            else "Velg mappe først. Deretter velger du filnavn i Lagre som-dialogen."
        )
        ctk.CTkLabel(
            self, text=help_text,
            font=theme.font(theme.SMALL_SIZE), text_color=theme.TEXT_MUTED,
        ).grid(row=1, column=0, padx=24, pady=(0, 10), sticky="w")

        body = ctk.CTkScrollableFrame(self, fg_color=theme.PANEL_BG)
        body.grid(row=2, column=0, padx=20, pady=8, sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        self._body = body

        if mode == "open":
            self._build_open_rows()
        else:
            self._build_save_rows()

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, padx=20, pady=(8, 18), sticky="ew")
        ctk.CTkButton(
            footer,
            text="Annen fil..." if mode == "open" else "Annen mappe...",
            command=self._browse_file if mode == "open" else self._browse_dir,
            width=130,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).pack(side="left")
        ctk.CTkButton(
            footer, text="Avbryt", command=self.destroy, width=110,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).pack(side="right")

        self._size_for_paths()

    def _size_for_paths(self) -> None:
        values = [str(self._default_dir)]
        if self._project_dir is not None:
            values.append(str(self._project_dir))
        values.extend(str(p) for p in self._recent_dirs)
        values.extend(str(p) for p in self._recent_files)
        longest = max((len(value) for value in values), default=70)
        self.update_idletasks()
        screen_width = max(900, self.winfo_screenwidth())
        desired = max(1100, min(screen_width - 70, 420 + longest * 9))
        self.geometry(f"{desired}x560")
        self.minsize(min(900, desired), 440)

    def _project_job_file(self) -> Path | None:
        if self._project_dir is None or not self._project_dir.is_dir():
            return None
        candidates = sorted(self._project_dir.glob("*.n5jobs"))
        if len(candidates) == 1:
            return candidates[0]
        return None

    @staticmethod
    def _recent_label(index: int) -> str:
        # Only one item can actually be "last used". Older entries are history;
        # keeping the label column blank avoids repeating a false status.
        return "Sist brukt" if index == 0 else ""

    def _build_open_rows(self) -> None:
        row = 0
        project_file = self._project_job_file()
        if project_file is not None:
            self._add_file_row(row, "Arbeid", project_file, primary=True, removable=False)
            row += 1

        seen: set[Path] = set()
        if project_file is not None:
            seen.add(project_file)

        recent_index = 0
        for path in self._recent_files:
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            self._add_file_row(
                row,
                self._recent_label(recent_index),
                path,
                removable=True,
            )
            recent_index += 1
            row += 1

        self._add_dir_row(
            row, "Standard", self._default_dir,
            button_text="Velg fil...", primary=(row == 0),
            choose=self._open_from_dir,
        )
        row += 1

        if self._project_dir is not None and project_file is None:
            self._add_dir_row(
                row, "Arbeid", self._project_dir,
                button_text="Velg fil...",
                choose=self._open_from_dir,
            )

    def _build_save_rows(self) -> None:
        self._add_dir_row(
            0, "Standard", self._default_dir,
            button_text="Bruk standard", primary=True,
            choose=self._choose_dir,
        )
        next_row = 1
        recent_index = 0
        if self._project_dir is not None and self._project_dir != self._default_dir:
            self._add_dir_row(
                next_row, "Arbeid", self._project_dir,
                button_text="Velg", choose=self._choose_dir,
            )
            next_row += 1
        for path in self._recent_dirs:
            if path in {self._default_dir, self._project_dir}:
                continue
            self._add_dir_row(
                next_row,
                self._recent_label(recent_index),
                path,
                button_text="Velg",
                choose=self._choose_dir,
            )
            recent_index += 1
            next_row += 1

    def _add_file_row(
        self,
        row: int,
        label: str,
        path: Path,
        *,
        primary: bool = False,
        removable: bool = False,
    ) -> None:
        ctk.CTkLabel(
            self._body, text=label, width=90, anchor="w",
            font=theme.font(theme.SMALL_SIZE, "bold" if primary else "normal"),
            text_color=theme.BLUE if primary else theme.TEXT_SUB,
        ).grid(row=row, column=0, padx=(10, 8), pady=6, sticky="w")
        ctk.CTkLabel(
            self._body, text=str(path), anchor="w", font=theme.font(theme.SMALL_SIZE),
        ).grid(row=row, column=1, padx=8, pady=6, sticky="ew")
        ctk.CTkButton(
            self._body, text="Åpne", width=76,
            command=lambda p=path: self._choose_file(p),
            fg_color=theme.BLUE_DIM if primary else theme.BUTTON_BG,
            hover_color=theme.BLUE if primary else theme.BUTTON_HOVER,
        ).grid(row=row, column=2, padx=(8, 4), pady=6)
        if removable:
            ctk.CTkButton(
                self._body, text="Slett fra historikk", width=120,
                command=lambda p=path: self._remove_recent_file(p),
                fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
            ).grid(row=row, column=3, padx=(4, 10), pady=6)

    def _add_dir_row(
        self,
        row: int,
        label: str,
        path: Path,
        *,
        button_text: str,
        choose: Callable[[Path], None],
        primary: bool = False,
    ) -> None:
        ctk.CTkLabel(
            self._body, text=label, width=90, anchor="w",
            font=theme.font(theme.SMALL_SIZE, "bold" if primary else "normal"),
            text_color=theme.BLUE if primary else theme.TEXT_SUB,
        ).grid(row=row, column=0, padx=(10, 8), pady=6, sticky="w")
        ctk.CTkLabel(
            self._body, text=str(path), anchor="w", font=theme.font(theme.SMALL_SIZE),
        ).grid(row=row, column=1, padx=8, pady=6, sticky="ew")
        ctk.CTkButton(
            self._body, text=button_text, width=112 if primary else 86,
            command=lambda p=path: choose(p),
            fg_color=theme.BLUE_DIM if primary else theme.BUTTON_BG,
            hover_color=theme.BLUE if primary else theme.BUTTON_HOVER,
        ).grid(row=row, column=2, padx=(8, 10), pady=6)

    def _choose_dir(self, path: Path) -> None:
        self.destroy()
        if self._on_choose_dir is not None:
            self._on_choose_dir(path)

    def _choose_file(self, path: Path) -> None:
        self.destroy()
        if self._on_choose_file is not None:
            self._on_choose_file(path)

    def _remove_recent_file(self, path: Path) -> None:
        if self._on_remove_recent_file is not None:
            self._on_remove_recent_file(path)
        self.destroy()

    def _open_from_dir(self, directory: Path) -> None:
        filename = filedialog.askopenfilename(
            title="Åpne jobbliste",
            initialdir=str(directory),
            filetypes=[("Workflow-jobbliste", "*.n5jobs"), ("Alle filer", "*.*")],
        )
        if filename:
            self._choose_file(Path(filename))

    def _browse_file(self) -> None:
        kwargs = {
            "title": "Åpne jobbliste",
            "filetypes": [("Workflow-jobbliste", "*.n5jobs"), ("Alle filer", "*.*")],
        }
        if self._default_dir.is_dir():
            kwargs["initialdir"] = str(self._default_dir)
        filename = filedialog.askopenfilename(**kwargs)
        if filename:
            self._choose_file(Path(filename))

    def _browse_dir(self) -> None:
        kwargs = {"title": "Velg mappe for jobblister"}
        if self._default_dir.is_dir():
            kwargs["initialdir"] = str(self._default_dir)
        folder = filedialog.askdirectory(**kwargs)
        if folder:
            self._choose_dir(Path(folder))
