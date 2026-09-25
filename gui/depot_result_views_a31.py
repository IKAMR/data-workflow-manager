from __future__ import annotations

import tkinter as tk
import customtkinter as ctk

from . import theme
from .depot_result_views_a30 import DepotResultViewsDialogA30
from .depot_result_views_a29 import _missing_archive_fields
from .depot_result_views_a22 import _identity


class DepotResultViewsDialogA31(DepotResultViewsDialogA30):
    """v0.1.6-a11: operational depot dashboard over the a10 archive-part view."""

    REVIEW_NOT_STARTED = "Ikke vurdert"

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._install_a11_dashboard()
        self._refresh_a11_dashboard()
        self._refresh_a11_archive_cards()
        if getattr(self, "_archive_parts", None):
            self._render_a11_archive_part(self._archive_index)

    def _install_a11_dashboard(self) -> None:
        detail = getattr(self, "_detail", None)
        if detail is None:
            return

        # a11 only changes presentation. The a10 tabs/model stay authoritative.
        for widget_name in ("_archive_title", "_archive_subtitle", "_a10_tabs"):
            widget = getattr(self, widget_name, None)
            if widget is None:
                continue
            try:
                info = widget.grid_info()
                widget.grid_configure(row=int(info.get("row", 0)) + 2)
            except Exception:
                pass

        self._a11_dashboard = ctk.CTkFrame(detail)
        self._a11_dashboard.grid(
            row=0, column=0, sticky="ew", padx=16, pady=(12, 8)
        )
        self._a11_dashboard.grid_columnconfigure(1, weight=1)

        chart_frame = ctk.CTkFrame(self._a11_dashboard)
        chart_frame.grid(
            row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 8)
        )
        ctk.CTkLabel(
            chart_frame,
            text="Datagrunnlag",
            anchor="w",
            font=theme.font(theme.SMALL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(9, 2))

        self._a11_chart = tk.Canvas(
            chart_frame,
            width=210,
            height=104,
            bg=theme.PANEL_BG,
            highlightthickness=0,
            bd=0,
        )
        self._a11_chart.grid(row=1, column=0, padx=10, pady=(2, 8))

        cards = ctk.CTkFrame(self._a11_dashboard, fg_color="transparent")
        cards.grid(row=0, column=1, sticky="ew", pady=(0, 6))
        for col in range(4):
            cards.grid_columnconfigure(col, weight=1)

        self._a11_cards = {}
        for col, (key, label) in enumerate((
            ("archive_parts", "Arkivdeler"),
            ("complete", "Komplett data"),
            ("missing", "Mangler data"),
            ("review_points", "Vurderingspunkter"),
        )):
            card = ctk.CTkFrame(cards)
            card.grid(row=0, column=col, sticky="nsew", padx=4)
            value = ctk.CTkLabel(
                card,
                text="0",
                font=theme.font(theme.TITLE_SIZE, weight="bold"),
            )
            value.grid(row=0, column=0, padx=10, pady=(8, 1))
            ctk.CTkLabel(
                card,
                text=label,
                text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=1, column=0, padx=10, pady=(0, 8))
            self._a11_cards[key] = value

        self._a11_extract_status = ctk.CTkLabel(
            self._a11_dashboard,
            text="",
            anchor="w",
            justify="left",
            wraplength=900,
            text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE),
        )
        self._a11_extract_status.grid(
            row=1, column=1, sticky="ew", padx=4, pady=(0, 4)
        )

        # Explicit treatment state in the archive-part summary. It is kept
        # separate from technical/data status.
        try:
            tab = self._a10_tabs.tab("Sammendrag")
            treatment = ctk.CTkFrame(tab)
            treatment.grid(row=2, column=0, sticky="ew", padx=4, pady=(0, 8))
            treatment.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                treatment,
                text="Behandlingsstatus",
                anchor="w",
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(row=0, column=0, sticky="w", padx=(12, 8), pady=8)

            self._a11_treatment_status = ctk.CTkLabel(
                treatment,
                text=self.REVIEW_NOT_STARTED,
                anchor="w",
                text_color=theme.TEXT_SUB,
                font=theme.font(theme.SMALL_SIZE),
            )
            self._a11_treatment_status.grid(
                row=0, column=1, sticky="ew", padx=8, pady=8
            )

            for child in tab.winfo_children():
                if child is treatment:
                    continue
                try:
                    info = child.grid_info()
                except Exception:
                    continue
                if str(info.get("row")) == "2":
                    child.grid_configure(row=3)
            tab.grid_rowconfigure(3, weight=1)
            tab.grid_rowconfigure(2, weight=0)
        except Exception:
            pass

    def _dashboard_counts(self) -> dict[str, int]:
        parts = list(getattr(self, "_archive_parts", []) or [])
        complete = sum(1 for row in parts if not _missing_archive_fields(row))
        missing = len(parts) - complete

        deviations = list(self.model.get("deviations") or [])
        review_points = sum(
            1 for item in deviations if bool(item.get("requires_review", True))
        )

        external = (
            (self.model.get("external_validation") or {}).get("arkade5") or {}
        )
        arkade_runs = len(external.get("imports") or [])

        return {
            "archive_parts": len(parts),
            "complete": complete,
            "missing": missing,
            "review_points": review_points,
            "arkade_runs": arkade_runs,
        }

    def _refresh_a11_dashboard(self) -> None:
        if not hasattr(self, "_a11_cards"):
            return

        counts = self._dashboard_counts()
        for key in ("archive_parts", "complete", "missing", "review_points"):
            self._a11_cards[key].configure(text=str(counts[key]))

        if counts["archive_parts"] == 0:
            status = "Ingen arkivdeler er materialisert i depotrapporten."
        elif counts["missing"] == 0:
            status = (
                "Alle arkivdeler har komplett nøkkeldatagrunnlag. "
                "Dette er ikke det samme som faglig godkjenning."
            )
        else:
            status = (
                f"{counts['missing']} av {counts['archive_parts']} arkivdeler "
                "mangler ett eller flere nøkkelfelt. "
                "Bruk køen til venstre for detaljert gjennomgang."
            )

        status += (
            f"  |  Arkade 5-kjøringer: {counts['arkade_runs']}."
            f"  |  Depotbehandling per arkivdel: {self.REVIEW_NOT_STARTED}."
        )
        self._a11_extract_status.configure(text=status)
        self._draw_a11_chart(counts["complete"], counts["missing"])

    def _draw_a11_chart(self, complete: int, missing: int) -> None:
        canvas = getattr(self, "_a11_chart", None)
        if canvas is None:
            return

        canvas.delete("all")
        total = complete + missing
        if total <= 0:
            canvas.create_text(
                105, 48,
                text="Ingen data",
                fill=theme.TEXT_MUTED,
                font=(theme.FONT_FAMILY, 9),
            )
            return

        x0, y0, x1, y1 = 12, 8, 92, 88
        start = 90.0
        complete_extent = 360.0 * (complete / total)

        if complete:
            canvas.create_arc(
                x0, y0, x1, y1,
                start=start,
                extent=-complete_extent,
                fill=theme.BLUE,
                outline=theme.APP_BG,
                width=2,
            )
        if missing:
            canvas.create_arc(
                x0, y0, x1, y1,
                start=start - complete_extent,
                extent=-(360.0 - complete_extent),
                fill=theme.DANGER_TEXT,
                outline=theme.APP_BG,
                width=2,
            )

        canvas.create_text(
            110, 30,
            text=f"Komplett {complete}",
            anchor="w",
            fill=theme.TEXT,
            font=(theme.FONT_FAMILY, 8),
        )
        canvas.create_text(
            110, 56,
            text=f"Mangler {missing}",
            anchor="w",
            fill=theme.TEXT,
            font=(theme.FONT_FAMILY, 8),
        )

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        if hasattr(self, "_a11_dashboard"):
            self._render_a11_archive_part(index)

    def _render_a11_archive_part(self, index: int) -> None:
        row = self._archive_parts[index]
        missing = _missing_archive_fields(row)

        if hasattr(self, "_a11_treatment_status"):
            self._a11_treatment_status.configure(
                text=f"{self.REVIEW_NOT_STARTED} · ikke lagret som egen status i a11"
            )

        lines = [
            "DEPOTETS BEHANDLING",
            "",
            f"Behandlingsstatus: {self.REVIEW_NOT_STARTED}",
            "Ingen automatisk godkjenning gjøres av denne visningen.",
            "",
        ]

        if missing:
            lines.append(f"Datagrunnlag: {len(missing)} av 9 nøkkelfelt mangler.")
            lines.append("Mangler:")
            for _field_id, label in missing:
                lines.append(f"  • {label}")
        else:
            lines.append("Datagrunnlag: alle 9 nøkkelfelt er materialisert.")

        non_ok = []
        for section in self._sections_for_index(index):
            for field in section.get("fields") or []:
                status = str(field.get("status") or "value_missing")
                if status != "ok":
                    non_ok.append((
                        field.get("label") or field.get("id") or "Felt",
                        status,
                    ))

        if non_ok:
            lines.extend(("", "Kontrollgrunnlag som krever oppmerksomhet:"))
            for label, status in non_ok:
                lines.append(f"  • {label}: {status}")
        else:
            lines.extend((
                "",
                "Kontrollgrunnlag: ingen ikke-OK feltstatus er materialisert "
                "for denne arkivdelen.",
            ))

        lines.extend((
            "",
            "Kommentarer lagres med eksisterende depotannotasjoner.",
            "Egen vedvarende behandlingsstatus innføres først når "
            "statusmodell og livsløp er fastlagt.",
        ))
        self._set_text(self._a10_review, "\n".join(lines))

    def _refresh_a11_archive_cards(self) -> None:
        for index, button in enumerate(getattr(self, "_archive_buttons", [])):
            row = self._archive_parts[index]
            system_id, title = _identity(row, index)
            missing = _missing_archive_fields(row)
            data_line = (
                f"Datagrunnlag: mangler {len(missing)}"
                if missing
                else "Datagrunnlag: komplett"
            )
            button.configure(
                text=(
                    f"{system_id}\n"
                    f"{title}\n"
                    f"{data_line}  |  Behandling: {self.REVIEW_NOT_STARTED}"
                ),
                height=88,
            )
