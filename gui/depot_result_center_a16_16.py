from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import customtkinter as ctk

from noark5_workflow.analysis.period_assessment import period_text, suggest_reviewed_period
from . import theme
from .depot_result_center_a16_15 import DepotResultCenterDialogA16_15


class DepotResultCenterDialogA16_16(DepotResultCenterDialogA16_15):
    """a16.16: reviewed-period proposal/editing and real archive-part counts."""

    def __init__(self, master, **kwargs) -> None:
        self._a1616_report_path = Path(kwargs.get("report_path")) if kwargs.get("report_path") else None
        self._a1616_user_identity = dict(kwargs.get("user_identity") or {})
        self._a1616_period_panel = None
        self._a1616_start_var = None
        self._a1616_end_var = None
        self._a1616_period_hint = None
        self._a1616_period_status = None
        self._a1616_loaded = self._load_period_assessments()
        super().__init__(master, **kwargs)
        self._a1616_start_var = ctk.StringVar(master=self, value="")
        self._a1616_end_var = ctk.StringVar(master=self, value="")
        self._install_reviewed_period_panel()
        self._fix_real_archive_counts_everywhere()
        if getattr(self, "_archive_parts", None):
            self._show_archive_part(getattr(self, "_archive_index", 0))

    @property
    def _a1616_real_count(self) -> int:
        return sum(1 for row in getattr(self, "_archive_parts", []) if not row.get("is_all_archive_parts"))

    def _assessment_file(self) -> Path | None:
        if self._a1616_report_path is None:
            return None
        return self._a1616_report_path.with_name("depot_period_assessment.json")

    def _load_period_assessments(self) -> dict:
        path = self._assessment_file()
        if path is None or not path.is_file():
            return {"period_assessment_format_version": 1, "scopes": {}}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                value.setdefault("period_assessment_format_version", 1)
                value.setdefault("scopes", {})
                return value
        except Exception:
            pass
        return {"period_assessment_format_version": 1, "scopes": {}}

    def _scope_key(self, row: dict, index: int) -> str:
        if row.get("is_all_archive_parts"):
            return "__ALL_ARCHIVE_PARTS__"
        identity = row.get("archive_part") or {}
        return str(identity.get("system_id") or f"archive-part-{index}")

    def _saved_period(self, row: dict, index: int) -> tuple[int | None, int | None] | None:
        scope = (self._a1616_loaded.get("scopes") or {}).get(self._scope_key(row, index))
        if not isinstance(scope, dict):
            return None
        try:
            start = int(scope["start_year"]) if scope.get("start_year") not in (None, "") else None
            end = int(scope["end_year"]) if scope.get("end_year") not in (None, "") else None
        except (TypeError, ValueError):
            return None
        return start, end

    def _effective_period(self, row: dict, index: int) -> tuple[int | None, int | None, str]:
        saved = self._saved_period(row, index)
        if saved is not None:
            return saved[0], saved[1], "lagret vurdering"
        start, end = suggest_reviewed_period(row)
        return start, end, "automatisk forslag"

    def _install_reviewed_period_panel(self) -> None:
        tabs = getattr(self, "_a10_tabs", None)
        if tabs is None:
            return
        try:
            tab = tabs.tab("Per år")
        except Exception:
            return

        panel = ctk.CTkFrame(tab)
        panel.grid(row=1, column=1, sticky="new", padx=(10, 4), pady=(0, 4))
        panel.grid_columnconfigure(1, weight=0)
        panel.grid_columnconfigure(3, weight=0)
        panel.grid_columnconfigure(4, weight=1)
        self._a1616_period_panel = panel

        ctk.CTkLabel(
            panel,
            text="Vurdert periode",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, columnspan=5, sticky="ew", padx=12, pady=(9, 4))

        ctk.CTkLabel(panel, text="Startår", font=theme.font(theme.SMALL_SIZE)).grid(
            row=1, column=0, sticky="w", padx=(12, 5), pady=3
        )
        ctk.CTkEntry(panel, width=82, textvariable=self._a1616_start_var).grid(
            row=1, column=1, sticky="w", pady=3
        )
        ctk.CTkLabel(panel, text="Sluttår", font=theme.font(theme.SMALL_SIZE)).grid(
            row=1, column=2, sticky="w", padx=(12, 5), pady=3
        )
        ctk.CTkEntry(panel, width=82, textvariable=self._a1616_end_var).grid(
            row=1, column=3, sticky="w", pady=3
        )

        actions = ctk.CTkFrame(panel, fg_color="transparent")
        actions.grid(row=1, column=4, sticky="e", padx=10, pady=3)
        ctk.CTkButton(
            actions, text="Bruk forslag", width=105, command=self._use_suggested_period,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=0, padx=(0, 6))
        ctk.CTkButton(
            actions, text="Lagre", width=78, command=self._save_reviewed_period,
            fg_color=theme.BLUE, hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=1)

        self._a1616_period_hint = ctk.CTkLabel(
            panel, text="", anchor="w", justify="left", wraplength=620,
            text_color=theme.TEXT_SUB, font=theme.font(theme.SMALL_SIZE),
        )
        self._a1616_period_hint.grid(row=2, column=0, columnspan=5, sticky="ew", padx=12, pady=(2, 2))
        self._a1616_period_status = ctk.CTkLabel(
            panel, text="", anchor="w", text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        )
        self._a1616_period_status.grid(row=3, column=0, columnspan=5, sticky="ew", padx=12, pady=(0, 8))

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        self._fix_real_archive_counts_everywhere()
        if not getattr(self, "_archive_parts", None):
            return
        row = self._archive_parts[index]
        start, end, source = self._effective_period(row, index)
        self._a1616_start_var.set("" if start is None else str(start))
        self._a1616_end_var.set("" if end is None else str(end))
        suggestion = suggest_reviewed_period(row)
        if self._a1616_period_hint is not None:
            self._a1616_period_hint.configure(
                text=(
                    f"Forslag: {period_text(*suggestion)}. Forslaget bruker hovedaktiviteten i "
                    "mapper/saker og journalposter og lar små ytterhaler stå som observasjoner."
                )
            )
        if self._a1616_period_status is not None:
            self._a1616_period_status.configure(text=f"Viser: {period_text(start, end)} ({source})")
        self._append_reviewed_period_to_surfaces(index, start, end, source)
        self._fix_archive_subtitle(index)

    def _append_reviewed_period_to_surfaces(self, index: int, start, end, source: str) -> None:
        reviewed = f"Vurdert: {period_text(start, end)} ({source})"
        period_label = getattr(self, "_a164_period_text", None)
        if period_label is not None:
            try:
                text = str(period_label.cget("text") or "")
                lines = [line for line in text.splitlines() if not line.startswith("Vurdert:")]
                lines.append(reviewed)
                period_label.configure(text="\n".join(lines))
            except Exception:
                pass
        context = getattr(self, "_a1614_year_context", None)
        if context is not None:
            try:
                text = str(context.cget("text") or "")
                lines = [line for line in text.splitlines() if not line.startswith("Vurdert periode:")]
                lines.append(f"Vurdert periode: {period_text(start, end)} ({source})")
                context.configure(text="\n".join(lines))
            except Exception:
                pass

    def _parse_year(self, value: str) -> int | None:
        text = str(value or "").strip()
        if not text:
            return None
        if len(text) != 4 or not text.isdigit():
            raise ValueError("År må være fire siffer.")
        year = int(text)
        if not 1000 <= year <= 2999:
            raise ValueError("År må være mellom 1000 og 2999.")
        return year

    def _use_suggested_period(self) -> None:
        if not getattr(self, "_archive_parts", None):
            return
        row = self._archive_parts[self._archive_index]
        start, end = suggest_reviewed_period(row)
        self._a1616_start_var.set("" if start is None else str(start))
        self._a1616_end_var.set("" if end is None else str(end))
        if self._a1616_period_status is not None:
            self._a1616_period_status.configure(text=f"Forslag satt i feltene: {period_text(start, end)} – lagre for å registrere vurderingen.")

    def _save_reviewed_period(self) -> None:
        if not getattr(self, "_archive_parts", None):
            return
        try:
            start = self._parse_year(self._a1616_start_var.get())
            end = self._parse_year(self._a1616_end_var.get())
            if start is not None and end is not None and start > end:
                raise ValueError("Startår kan ikke være etter sluttår.")
        except ValueError as exc:
            if self._a1616_period_status is not None:
                self._a1616_period_status.configure(text=f"Kan ikke lagre: {exc}")
            return

        path = self._assessment_file()
        if path is None:
            if self._a1616_period_status is not None:
                self._a1616_period_status.configure(text="Kan ikke lagre: rapportsti mangler.")
            return

        row = self._archive_parts[self._archive_index]
        key = self._scope_key(row, self._archive_index)
        suggestion = suggest_reviewed_period(row)
        scopes = self._a1616_loaded.setdefault("scopes", {})
        scopes[key] = {
            "start_year": start,
            "end_year": end,
            "suggested_start_year": suggestion[0],
            "suggested_end_year": suggestion[1],
            "source": "depot_review",
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "updated_by": self._a1616_user_identity,
            "is_all_archive_parts": bool(row.get("is_all_archive_parts")),
        }
        self._a1616_loaded["source_report"] = str(self._a1616_report_path or "")
        try:
            path.write_text(json.dumps(self._a1616_loaded, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception as exc:
            if self._a1616_period_status is not None:
                self._a1616_period_status.configure(text=f"Kunne ikke lagre vurderingen: {exc}")
            return

        if self._a1616_period_status is not None:
            self._a1616_period_status.configure(text=f"Lagret vurdert periode: {period_text(start, end)}")
        self._append_reviewed_period_to_surfaces(self._archive_index, start, end, "lagret vurdering")

    def _fix_archive_subtitle(self, index: int) -> None:
        if not getattr(self, "_archive_parts", None):
            return
        row = self._archive_parts[index]
        if row.get("is_all_archive_parts"):
            return
        identity = row.get("archive_part") or {}
        system_id = str(identity.get("system_id") or "–")
        try:
            self._archive_subtitle.configure(
                text=f"systemID: {system_id}   |   Arkivdel {index} av {self._a1616_real_count}"
            )
        except Exception:
            pass

    def _fix_real_archive_counts_everywhere(self) -> None:
        real = self._a1616_real_count
        synthetic = real + 1
        if real <= 0:
            return
        # Keep model-level totals factual even though the GUI owns one synthetic row.
        try:
            self.model.setdefault("summary", {})["archive_part_count"] = real
            if isinstance(self.model.get("all_archive_parts_summary"), dict):
                self.model["all_archive_parts_summary"]["archive_part_count"] = real
        except Exception:
            pass

        replacements = (
            (f"{synthetic} arkivdel(er)", f"{real} arkivdel(er)"),
            (f"Datagrunnlag: {synthetic} komplett", f"Datagrunnlag: {real} komplett"),
            (f"{synthetic} komplett", f"{real} komplett"),
            (f"Arkivdeler: {synthetic}", f"Arkivdeler: {real}"),
            (f"Arkivdeler {synthetic}", f"Arkivdeler {real}"),
        )

        def walk(widget):
            children = list(widget.winfo_children())
            sibling_texts = []
            for sibling in children:
                if isinstance(sibling, ctk.CTkLabel):
                    try:
                        sibling_texts.append(str(sibling.cget("text") or ""))
                    except Exception:
                        pass
            count_context = any(
                marker in " ".join(sibling_texts)
                for marker in ("Arkivdeler", "Komplett data", "Datagrunnlag")
            )
            for child in children:
                if isinstance(child, ctk.CTkLabel):
                    try:
                        text = str(child.cget("text") or "")
                        new = str(real) if count_context and text.strip() == str(synthetic) else text
                        for old, repl in replacements:
                            new = new.replace(old, repl)
                        if new != text:
                            child.configure(text=new)
                    except Exception:
                        pass
                walk(child)
        try:
            walk(self)
        except Exception:
            pass
