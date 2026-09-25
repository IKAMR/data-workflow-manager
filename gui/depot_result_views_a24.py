from __future__ import annotations

import json
from pathlib import Path

import customtkinter as ctk

from . import theme
from .window_placement import enable_native_work_window, present_native_work_window
from .depot_result_views_a23 import DepotResultViewsDialogA23
from .depot_result_views_a22 import (
    _PRIMARY_FIELDS,
    _SECONDARY_FIELDS,
    _display,
    _identity,
)


_STATUS_LABELS = {
    "ok": "Tilgjengelig",
    "archive_part_missing": "Mangler for arkivdelen",
    "value_missing": "Ikke materialisert",
    "source_missing": "Kildetest mangler",
}

_FALLBACK_LABELS = dict(_PRIMARY_FIELDS + _SECONDARY_FIELDS)


def _value_text(value) -> str:
    if value is None:
        return "Ikke materialisert"
    if isinstance(value, dict):
        if not value:
            return "Ingen verdier"
        return "  |  ".join(f"{key}: {val}" for key, val in value.items())
    if isinstance(value, list):
        if not value:
            return "Ingen verdier"
        return ", ".join(str(item) for item in value)
    return str(value)


class DepotResultViewsDialogA24(DepotResultViewsDialogA23):
    """v0.1.6-a4: richer archive-part assessment over materialized views."""

    def __init__(self, master, **kwargs):
        self._presentation_parts: dict[str, dict] = {}
        self._presentation_load_note = ""
        super().__init__(master, **kwargs)
        self.title("Vurdering av uttrekk – Noark 5")
        self.geometry("1320x860")
        self.minsize(980, 680)
        enable_native_work_window(self)
        self._load_materialized_archive_part_details()
        self._replace_traceability_with_assessment_surface()
        if getattr(self, "_archive_parts", None):
            self._render_archive_part_assessment(self._archive_index)
        present_native_work_window(self)

    def _source_presentation_path(self) -> Path | None:
        evidence = self.model.get("evidence") or {}
        raw = str(evidence.get("source_presentation_file") or "").strip()
        if not raw:
            return None
        path = Path(raw)
        if path.is_file():
            return path
        if self.report_path:
            candidate = Path(self.report_path).parent / path
            if candidate.is_file():
                return candidate
        return None

    def _load_materialized_archive_part_details(self) -> None:
        source = self._source_presentation_path()
        if source is None:
            self._presentation_load_note = (
                "Detaljert kildepresentasjon er ikke tilgjengelig. "
                "Visningen bruker depotrapportens materialiserte sammendrag."
            )
            return
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except Exception as exc:
            self._presentation_load_note = (
                f"Kildepresentasjonen kunne ikke leses: {exc}"
            )
            return

        archive_view = next(
            (
                view
                for view in payload.get("views", [])
                if view.get("id") == "archive_part_overview"
            ),
            None,
        )
        if not archive_view:
            self._presentation_load_note = (
                "Kildepresentasjonen mangler archive_part_overview."
            )
            return

        for row in archive_view.get("archive_parts", []):
            identity = row.get("archive_part") or {}
            system_id = str(identity.get("system_id") or "").strip()
            if system_id:
                self._presentation_parts[system_id] = row

        self._presentation_load_note = (
            f"Detaljene leses fra eksisterende materialisert presentasjon: {source}"
        )

    def _replace_traceability_with_assessment_surface(self) -> None:
        trace = getattr(self, "_traceability", None)
        if trace is not None:
            try:
                trace.grid_remove()
            except Exception:
                pass

        detail = getattr(self, "_detail", None)
        if detail is None:
            return

        self._assessment_surface = ctk.CTkScrollableFrame(detail)
        self._assessment_surface.grid(
            row=4, column=0, sticky="nsew", padx=16, pady=(0, 8)
        )
        self._assessment_surface.grid_columnconfigure(0, weight=1)

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        if hasattr(self, "_assessment_surface"):
            self._render_archive_part_assessment(index)

    def _fallback_sections(self, row: dict) -> list[dict]:
        sources = row.get("sources") or {}

        def fields(specs):
            result = []
            for field_id, label in specs:
                source = sources.get(field_id) or {}
                value = row.get(field_id)
                result.append({
                    "id": field_id,
                    "label": label,
                    "status": "ok" if value is not None else "value_missing",
                    "value": value,
                    "source_test_id": source.get("test_id"),
                    "source_path": source.get("path"),
                })
            return result

        return [
            {
                "id": "content_summary",
                "label": "Innhold og omfang",
                "fields": fields(_PRIMARY_FIELDS),
            },
            {
                "id": "preservation_summary",
                "label": "Bevaring, skjerming og kassasjon",
                "fields": fields(_SECONDARY_FIELDS),
            },
        ]

    def _sections_for_index(self, index: int) -> list[dict]:
        row = self._archive_parts[index]
        system_id, _title = _identity(row, index)
        detailed = self._presentation_parts.get(system_id)
        if detailed:
            return list(detailed.get("sections") or [])
        return self._fallback_sections(row)

    def _render_archive_part_assessment(self, index: int) -> None:
        frame = self._assessment_surface
        for widget in frame.winfo_children():
            widget.destroy()

        row = self._archive_parts[index]
        system_id, title = _identity(row, index)

        ctk.CTkLabel(
            frame,
            text="Vurderingsgrunnlag for valgt arkivdel",
            anchor="w",
            font=theme.font(theme.SECTION_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=4, pady=(2, 2))

        ctk.CTkLabel(
            frame,
            text=(
                "Viser allerede materialiserte data og feltstatus. "
                "Ingen XML/XPath-analyse kjøres når du bytter arkivdel."
            ),
            anchor="w",
            justify="left",
            wraplength=820,
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 10))

        row_no = 2
        for section in self._sections_for_index(index):
            section_frame = ctk.CTkFrame(frame)
            section_frame.grid(
                row=row_no, column=0, sticky="ew", padx=4, pady=(0, 10)
            )
            section_frame.grid_columnconfigure(1, weight=1)
            row_no += 1

            ctk.CTkLabel(
                section_frame,
                text=section.get("label") or section.get("id") or "Kontroller",
                anchor="w",
                font=theme.font(theme.NORMAL_SIZE, weight="bold"),
            ).grid(
                row=0, column=0, columnspan=3, sticky="ew",
                padx=12, pady=(10, 7)
            )

            fields = list(section.get("fields") or [])
            if not fields:
                ctk.CTkLabel(
                    section_frame,
                    text="Ingen materialiserte felt i denne seksjonen.",
                    anchor="w",
                    text_color=theme.TEXT_MUTED,
                    font=theme.font(theme.SMALL_SIZE),
                ).grid(row=1, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 10))
                continue

            for field_no, field in enumerate(fields, start=1):
                field_id = field.get("id") or ""
                label = (
                    field.get("label")
                    or _FALLBACK_LABELS.get(field_id)
                    or field_id
                    or "Felt"
                )
                status = str(field.get("status") or "value_missing")
                value = field.get("value")
                value_text = _value_text(value) if status == "ok" else _STATUS_LABELS.get(status, status)
                source_test = field.get("source_test_id") or field.get("source_test") or "–"
                source_path = field.get("source_path") or "–"

                ctk.CTkLabel(
                    section_frame,
                    text=label,
                    anchor="w",
                    font=theme.font(theme.SMALL_SIZE),
                ).grid(row=field_no, column=0, sticky="nw", padx=(12, 8), pady=3)

                ctk.CTkLabel(
                    section_frame,
                    text=value_text,
                    anchor="w",
                    justify="left",
                    wraplength=450,
                    text_color=(
                        theme.TEXT
                        if status == "ok"
                        else theme.TEXT_MUTED
                    ),
                    font=theme.font(theme.SMALL_SIZE),
                ).grid(row=field_no, column=1, sticky="new", padx=8, pady=3)

                ctk.CTkLabel(
                    section_frame,
                    text=f"{source_test} · {source_path}",
                    anchor="w",
                    justify="left",
                    wraplength=280,
                    text_color=theme.TEXT_MUTED,
                    font=theme.font(theme.SMALL_SIZE),
                ).grid(row=field_no, column=2, sticky="ne", padx=(8, 12), pady=3)

        provenance = ctk.CTkFrame(frame)
        provenance.grid(row=row_no, column=0, sticky="ew", padx=4, pady=(0, 8))
        provenance.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            provenance,
            text="Sporbarhet",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 3))

        ctk.CTkLabel(
            provenance,
            text=(
                f"{title} · systemID {system_id}\n"
                f"{self._presentation_load_note}"
            ),
            anchor="w",
            justify="left",
            wraplength=820,
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
