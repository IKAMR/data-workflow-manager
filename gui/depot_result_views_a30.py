from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_views_a29 import DepotResultViewsDialogA29, _missing_archive_fields
from .depot_result_views_a22 import _PRIMARY_FIELDS, _SECONDARY_FIELDS


def _fmt(value) -> str:
    if value is None:
        return "–"
    try:
        return f"{int(value):,}".replace(",", " ")
    except (TypeError, ValueError):
        return str(value)


class DepotResultViewsDialogA30(DepotResultViewsDialogA29):
    """v0.1.6-a10: first archive-part step toward the target GUI."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._install_a10_target_archive_surface()
        if getattr(self, "_archive_parts", None):
            self._render_a10_archive_part(self._archive_index)

    def _install_a10_target_archive_surface(self) -> None:
        detail = getattr(self, "_detail", None)
        if detail is None or not getattr(self, "_archive_parts", None):
            return

        # Hide the layered a4-a9 right-side surfaces. Their data/model logic is
        # retained; a10 only replaces presentation for the selected archive part.
        for widget in (
            getattr(self, "_kpi_frame", None),
            getattr(self, "_secondary", None),
            getattr(self, "_health_frame", None),
            getattr(self, "_missing_data_frame", None),
            getattr(self, "_assessment_surface", None),
        ):
            if widget is not None:
                try:
                    widget.grid_remove()
                except Exception:
                    pass

        # Hide the inherited bottom archive annotation row; the action is
        # reintroduced in the Vurderingspunkter tab.
        inherited_annotation = getattr(self, "archive_annotation_button", None)
        if inherited_annotation is not None:
            try:
                inherited_annotation.master.grid_remove()
            except Exception:
                pass

        detail.grid_rowconfigure(4, weight=1)

        self._a10_tabs = ctk.CTkTabview(detail)
        self._a10_tabs.grid(
            row=2,
            column=0,
            rowspan=5,
            sticky="nsew",
            padx=16,
            pady=(0, 12),
        )

        for name in ("Sammendrag", "Kontroller", "Vurderingspunkter"):
            self._a10_tabs.add(name)

        self._build_summary_tab(self._a10_tabs.tab("Sammendrag"))
        self._build_controls_tab(self._a10_tabs.tab("Kontroller"))
        self._build_review_tab(self._a10_tabs.tab("Vurderingspunkter"))
        self._a10_tabs.set("Sammendrag")

    def _build_summary_tab(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        kpis = ctk.CTkFrame(tab, fg_color="transparent")
        kpis.grid(row=0, column=0, sticky="ew", padx=4, pady=(8, 8))
        for col in range(3):
            kpis.grid_columnconfigure(col, weight=1)

        self._a10_kpi_labels = {}
        for col, (field_id, label) in enumerate((
            ("registration_count", "Registreringer"),
            ("journalpost_count", "Journalposter"),
            ("document_object_count", "Dokumentobjekter"),
        )):
            card = ctk.CTkFrame(kpis)
            card.grid(row=0, column=col, sticky="nsew", padx=4)

            value = ctk.CTkLabel(
                card,
                text="–",
                font=theme.font(theme.TITLE_SIZE, weight="bold"),
            )
            value.grid(row=0, column=0, padx=12, pady=(10, 1))

            ctk.CTkLabel(
                card,
                text=label,
                text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=1, column=0, padx=12, pady=(0, 10))

            self._a10_kpi_labels[field_id] = value

        status = ctk.CTkFrame(tab)
        status.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 8))
        status.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            status,
            text="Datagrunnlag",
            anchor="w",
            font=theme.font(theme.SMALL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=(12, 8), pady=8)

        self._a10_data_status = ctk.CTkLabel(
            status,
            text="",
            anchor="w",
            text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE),
        )
        self._a10_data_status.grid(row=0, column=1, sticky="ew", padx=8, pady=8)

        body = ctk.CTkScrollableFrame(tab)
        body.grid(row=2, column=0, sticky="nsew", padx=4, pady=(0, 6))
        body.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            body,
            text="Manglende datagrunnlag",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 3))

        self._a10_missing = ctk.CTkLabel(
            body,
            text="",
            anchor="w",
            justify="left",
            wraplength=850,
            text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE),
        )
        self._a10_missing.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        ctk.CTkLabel(
            body,
            text="Innhold og omfang",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=2, column=0, sticky="ew", padx=10, pady=(6, 3))

        self._a10_content = ctk.CTkLabel(
            body,
            text="",
            anchor="w",
            justify="left",
            wraplength=850,
            text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE),
        )
        self._a10_content.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))

    def _build_controls_tab(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            tab,
            text="Kontroller for valgt arkivdel",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

        self._a10_controls = ctk.CTkTextbox(
            tab,
            wrap="word",
            font=theme.font(theme.SMALL_SIZE),
        )
        self._a10_controls.grid(
            row=1, column=0, sticky="nsew", padx=12, pady=(0, 12)
        )

    def _build_review_tab(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            tab,
            text="Depotets behandling av valgt arkivdel",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

        self._a10_review = ctk.CTkTextbox(
            tab,
            wrap="word",
            font=theme.font(theme.SMALL_SIZE),
        )
        self._a10_review.grid(
            row=1, column=0, sticky="nsew", padx=12, pady=(0, 8)
        )

        self._a10_comment_button = ctk.CTkButton(
            tab,
            text="Kommentarer til arkivdel...",
            width=180,
            state="normal" if self.report_path else "disabled",
            command=self._open_archive_part_annotations,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        )
        self._a10_comment_button.grid(
            row=2, column=0, sticky="e", padx=12, pady=(0, 12)
        )

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        if hasattr(self, "_a10_tabs"):
            self._render_a10_archive_part(index)

    def _render_a10_archive_part(self, index: int) -> None:
        row = self._archive_parts[index]
        missing = _missing_archive_fields(row)

        for field_id, widget in self._a10_kpi_labels.items():
            widget.configure(text=_fmt(row.get(field_id)))

        if missing:
            self._a10_data_status.configure(
                text=f"{9 - len(missing)} av 9 nøkkelfelt tilgjengelig · mangler {len(missing)}"
            )
            sources = row.get("sources") or {}
            lines = []
            for field_id, label in missing:
                source = sources.get(field_id) or {}
                lines.append(
                    f"• {label} — test {source.get('test_id') or '–'}"
                    f" · sti {source.get('path') or '–'}"
                )
            self._a10_missing.configure(text="\n".join(lines))
        else:
            self._a10_data_status.configure(text="Alle 9 nøkkelfelt tilgjengelig")
            self._a10_missing.configure(text="Ingen manglende nøkkelfelt.")

        self._a10_content.configure(
            text="\n".join(
                f"{label}: {_fmt(row.get(field_id))}"
                for field_id, label in (_PRIMARY_FIELDS + _SECONDARY_FIELDS)
            )
        )

        control_lines = [
            "Materialiserte kontroller/felt for valgt arkivdel.",
            "Ingen ny XML/XPath-analyse kjøres i denne visningen.",
            "",
        ]

        for section in self._sections_for_index(index):
            control_lines.append(
                str(section.get("label") or section.get("id") or "Kontroller")
            )
            for field in section.get("fields") or []:
                label = field.get("label") or field.get("id") or "Felt"
                status = str(field.get("status") or "value_missing")
                value = field.get("value")
                shown = _fmt(value) if status == "ok" else status
                source_test = (
                    field.get("source_test_id")
                    or field.get("source_test")
                    or "–"
                )
                control_lines.append(
                    f"  {label}: {shown} · kilde {source_test}"
                )
            control_lines.append("")

        self._set_text(
            self._a10_controls,
            "\n".join(control_lines).rstrip(),
        )

        review_lines = [
            "Dette er depotets behandlingslag og er adskilt fra teknisk teststatus.",
            "",
            "a10 etablerer selve arbeidsflaten fra målbildet.",
            "Egen lagret behandlingsstatus per arkivdel innføres i et senere inkrement.",
        ]
        if missing:
            review_lines.extend(
                (
                    "",
                    f"Datagrunnlag: {len(missing)} nøkkelfelt mangler materialisering.",
                )
            )

        self._set_text(self._a10_review, "\n".join(review_lines))

    @staticmethod
    def _set_text(widget, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")
