from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a18_8 import _overview_metrics
from .depot_result_center_a18_9 import _control_distribution
from .depot_result_center_a19_1 import _correspondence_profile
from .depot_result_center_a20_1 import DepotResultCenterDialogA20_1


class DepotResultCenterDialogA21_1(DepotResultCenterDialogA20_1):
    """a21.1: refreshed extraction-level overview using the established a20 visual language.

    The overview remains presentation-only: it reads the already materialized depot report,
    period assessment and imported PRONOM statistics. No Noark source analysis is started here.
    """

    _A211_DOMAIN_COLORS = (
        theme.TEXT_SUB,
        theme.BLUE,
        theme.CATEGORY_COLORS["Innhold"],
        theme.CATEGORY_COLORS["Metadata"],
    )

    def _build_overview_tab(self, tab) -> None:
        metrics = _overview_metrics(self.model)
        distribution = _control_distribution(self.model)
        correspondence = _correspondence_profile(self.model)
        period = self._a211_period_summary()
        top_formats = self._a211_top_formats()
        review_points = self._a211_review_points()

        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(6, weight=1)

        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 5))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="Oversikt",
            anchor="w",
            font=theme.font(theme.HEADER_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text="Hele uttrekket · rask orientering og vurderingsstøtte",
            anchor="e",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0, column=1, sticky="e", padx=(12, 0))

        domains = ctk.CTkFrame(tab, fg_color="transparent")
        domains.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        for col in range(4):
            domains.grid_columnconfigure(col, weight=1, uniform="a211domains")

        archive_detail = ""
        try:
            archive_count = int(metrics.get("archive_count") or 0)
            if archive_count > 1:
                archive_detail = f"{self._fmt_count(archive_count)} arkiv"
        except (TypeError, ValueError):
            pass

        domain_specs = (
            (metrics.get("archive_part_count"), "Arkivdel", archive_detail),
            (metrics.get("folder_count"), "Mappe / sak", ""),
            (metrics.get("registration_count"), "Registrering / JP", ""),
            (metrics.get("document_description_count"), "Dokument", "Dokumentbeskrivelse"),
        )
        for col, (value, label, detail) in enumerate(domain_specs):
            self._a211_domain_card(
                domains,
                col,
                self._fmt_count(value),
                label,
                detail,
                self._A211_DOMAIN_COLORS[col],
            )

        upper = ctk.CTkFrame(tab, fg_color="transparent")
        upper.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))
        upper.grid_columnconfigure(0, weight=3, uniform="a211upper")
        upper.grid_columnconfigure(1, weight=2, uniform="a211upper")

        self._a211_control_card(upper, 0, distribution)
        self._a211_archive_health_card(upper, 1, metrics)

        self._a211_correspondence_card(tab, row=3, profile=correspondence)

        middle = ctk.CTkFrame(tab, fg_color="transparent")
        middle.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 8))
        middle.grid_columnconfigure(0, weight=3, uniform="a211middle")
        middle.grid_columnconfigure(1, weight=2, uniform="a211middle")
        middle.grid_columnconfigure(2, weight=2, uniform="a211middle")

        self._a211_period_card(middle, 0, period)
        self._a211_formats_card(middle, 1, top_formats, metrics)
        self._a211_review_card(middle, 2, review_points, metrics)

        actions = ctk.CTkFrame(tab)
        actions.grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 8))
        actions.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            actions,
            text="Videre arbeid",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 6))
        button_row = ctk.CTkFrame(actions, fg_color="transparent")
        button_row.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 9))
        for col, (label, tab_name, width) in enumerate((
            ("Arkivdeler", "Arkivdeler", 112),
            ("Depotvurdering", "Depotvurdering", 132),
            ("Filformater", "Filformater", 112),
            ("Rapporter", "Rapporter", 104),
        )):
            ctk.CTkButton(
                button_row,
                text=label,
                width=width,
                command=lambda name=tab_name: self._a188_show_tab(name),
            ).grid(row=0, column=col, padx=(0, 7))

        # Flexible bottom space keeps the dashboard calm on large displays while the
        # compact cards remain fully visible at the +2 font size used during design QA.
        ctk.CTkFrame(tab, fg_color="transparent").grid(row=6, column=0, sticky="nsew")

    def _a211_domain_card(self, parent, column: int, value: str, label: str, detail: str, color: str) -> None:
        card = ctk.CTkFrame(parent, border_width=1, border_color=theme.CARD_BORDER, corner_radius=7)
        card.grid(row=0, column=column, sticky="nsew", padx=4)
        card.grid_columnconfigure(0, weight=1)
        accent = ctk.CTkFrame(card, height=4, fg_color=color, corner_radius=2)
        accent.grid(row=0, column=0, sticky="ew", padx=9, pady=(8, 4))
        accent.grid_propagate(False)
        ctk.CTkLabel(
            card,
            text=value,
            anchor="w",
            font=theme.font(theme.TITLE_SIZE + 1, weight="bold"),
        ).grid(row=1, column=0, sticky="ew", padx=11, pady=(0, 0))
        ctk.CTkLabel(
            card,
            text=label,
            anchor="w",
            text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE, weight="bold"),
        ).grid(row=2, column=0, sticky="ew", padx=11, pady=(0, 0))
        ctk.CTkLabel(
            card,
            text=detail or " ",
            anchor="w",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=3, column=0, sticky="ew", padx=11, pady=(0, 8))

    def _a211_control_card(self, parent, column: int, distribution: dict[str, int]) -> None:
        card = ctk.CTkFrame(parent, border_width=1, border_color=theme.CARD_BORDER, corner_radius=7)
        card.grid(row=0, column=column, sticky="nsew", padx=(0, 5))
        card.grid_columnconfigure(0, weight=1)
        total = int(distribution.get("total") or 0)
        ok = int(distribution.get("ok") or 0)
        pct = round((ok / total) * 100) if total else 0
        ctk.CTkLabel(
            card,
            text="Kontrollresultat – DWM",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 2))
        ctk.CTkLabel(
            card,
            text=f"{pct}% OK",
            anchor="w",
            text_color=theme.CATEGORY_COLORS.get("Kontroll", theme.TEXT_SUB),
            font=theme.font(theme.TITLE_SIZE + 1, weight="bold"),
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 4))

        bar = ctk.CTkFrame(card, height=14, fg_color=theme.PANEL_BG_DARK, corner_radius=4)
        bar.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 5))
        bar.grid_propagate(False)
        specs = (
            ("ok", theme.CATEGORY_COLORS.get("Kontroll", theme.BLUE)),
            ("error", theme.CATEGORY_COLORS.get("Feil", theme.TEXT_SUB)),
            ("not_run", theme.TEXT_MUTED),
            ("other", theme.CARD_BORDER),
        )
        visible = 0
        for key, color in specs:
            value = int(distribution.get(key) or 0)
            if value <= 0:
                continue
            bar.grid_columnconfigure(visible, weight=value)
            segment = ctk.CTkFrame(bar, fg_color=color, corner_radius=0)
            segment.grid(row=0, column=visible, sticky="nsew")
            visible += 1
        if visible == 0:
            bar.grid_columnconfigure(0, weight=1)

        labels = ctk.CTkFrame(card, fg_color="transparent")
        labels.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 8))
        for col, (key, label) in enumerate((
            ("ok", "OK"), ("error", "Feil"), ("not_run", "Ikke kjørt"), ("other", "Annet")
        )):
            labels.grid_columnconfigure(col, weight=1, uniform="a211dist")
            value = int(distribution.get(key) or 0)
            ctk.CTkLabel(
                labels,
                text=f"{label}: {value}",
                anchor="w",
                text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=0, column=col, sticky="ew", padx=4)

    def _a211_archive_health_card(self, parent, column: int, metrics: dict[str, object]) -> None:
        card = ctk.CTkFrame(parent, border_width=1, border_color=theme.CARD_BORDER, corner_radius=7)
        card.grid(row=0, column=column, sticky="nsew", padx=(5, 0))
        card.grid_columnconfigure(0, weight=1)
        total = int(metrics.get("archive_part_count") or 0)
        complete = int(metrics.get("complete_archive_parts") or 0)
        missing = int(metrics.get("missing_archive_parts") or 0)
        review = int(metrics.get("review_points") or 0)
        ratio = complete / total if total else 0.0
        ctk.CTkLabel(
            card,
            text="Arkivdelstatus",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 3))
        ctk.CTkLabel(
            card,
            text=f"{complete} / {total} komplett datagrunnlag",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 3))
        progress = ctk.CTkProgressBar(card, height=9)
        progress.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 5))
        progress.set(max(0.0, min(1.0, ratio)))
        ctk.CTkLabel(
            card,
            text=f"{missing} med manglende datagrunnlag  ·  {review} vurderingspunkter",
            anchor="w",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 8))

    def _a211_correspondence_card(self, tab, *, row: int, profile: dict[str, int]) -> None:
        card = ctk.CTkFrame(tab, border_width=1, border_color=theme.CARD_BORDER, corner_radius=7)
        card.grid(row=row, column=0, sticky="ew", padx=12, pady=(0, 8))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            card,
            text="Korrespondanseprofil – journalposter",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 5))
        total = sum(int(v or 0) for v in profile.values())
        if total <= 0:
            ctk.CTkLabel(
                card,
                text="Ikke tilgjengelig i materialisert kontrollgrunnlag.",
                anchor="w",
                text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
            return

        cells = ctk.CTkFrame(card, fg_color="transparent")
        cells.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        specs = (
            ("incoming", "Inngående", theme.BLUE),
            ("outgoing", "Utgående", theme.CATEGORY_COLORS["Innhold"]),
            ("note", "Notat", theme.CATEGORY_COLORS["Metadata"]),
            ("other", "Andre", theme.TEXT_MUTED),
        )
        for col, (key, label, color) in enumerate(specs):
            cells.grid_columnconfigure(col, weight=1, uniform="a211corr")
            value = int(profile.get(key) or 0)
            percent = round((value / total) * 100) if total else 0
            cell = ctk.CTkFrame(cells, fg_color="transparent")
            cell.grid(row=0, column=col, sticky="ew", padx=4)
            cell.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                cell,
                text=f"{label}  {percent}%  ·  {self._fmt_count(value)}",
                anchor="w",
                text_color=theme.TEXT_SUB,
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(row=0, column=0, sticky="ew", pady=(0, 3))
            track = ctk.CTkProgressBar(cell, height=8, progress_color=color, fg_color=theme.PANEL_BG_DARK)
            track.grid(row=1, column=0, sticky="ew")
            track.set(max(0.0, min(1.0, value / total)))

    def _a211_period_summary(self) -> dict[str, object]:
        summary = self.model.get("all_archive_parts_summary") or {}
        declared = summary.get("declared_period") or {}
        observed = summary.get("observed_period") or {}
        result = {
            "declared_start": self._a211_year(declared.get("start_date")),
            "declared_end": self._a211_year(declared.get("end_date")),
            "observed_start": observed.get("first_year"),
            "observed_end": observed.get("last_year"),
            "reviewed_start": None,
            "reviewed_end": None,
            "reviewed_source": "",
            "outliers": [],
        }
        try:
            aggregate = self._aggregate_row(summary)
            start, end, source = self._effective_period(aggregate, 0)
            result["reviewed_start"] = start
            result["reviewed_end"] = end
            result["reviewed_source"] = source
        except Exception:
            pass

        findings = summary.get("cross_source_year_findings") or []
        years = []
        for item in findings:
            try:
                years.append(int(item.get("year")))
            except (TypeError, ValueError, AttributeError):
                continue
        result["outliers"] = sorted(set(years))
        return result

    @staticmethod
    def _a211_year(value):
        text = str(value or "").strip()
        if len(text) >= 4 and text[:4].isdigit():
            return int(text[:4])
        return None

    def _a211_period_card(self, parent, column: int, period: dict[str, object]) -> None:
        card = ctk.CTkFrame(parent, border_width=1, border_color=theme.CARD_BORDER, corner_radius=7)
        card.grid(row=0, column=column, sticky="nsew", padx=(0, 5))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            card,
            text="Tidsprofil – hele uttrekket",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 4))
        declared = self._a211_span(period.get("declared_start"), period.get("declared_end"))
        observed = self._a211_span(period.get("observed_start"), period.get("observed_end"))
        reviewed = self._a211_span(period.get("reviewed_start"), period.get("reviewed_end"))
        ctk.CTkLabel(
            card,
            text=f"Oppgitt  {declared}\nObservert  {observed}\nVurdert  {reviewed}",
            anchor="w",
            justify="left",
            text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE, weight="bold"),
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 4))
        outliers = period.get("outliers") or []
        note = "Ingen materialiserte årspunkter utenfor hovedbildet."
        if outliers:
            shown = ", ".join(str(y) for y in outliers[:5])
            if len(outliers) > 5:
                shown += " …"
            note = f"År som bør ses nærmere på: {shown}"
        ctk.CTkLabel(
            card,
            text=note,
            anchor="w",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))

    @staticmethod
    def _a211_span(start, end) -> str:
        return f"{start if start is not None else '–'}–{end if end is not None else '–'}"

    def _a211_top_formats(self) -> list[tuple[str, int]]:
        arkade = ((self.model.get("external_validation") or {}).get("arkade5") or {})
        totals: dict[str, int] = {}
        for item in arkade.get("imports") or []:
            stats = ((item.get("pronom") or {}).get("statistics") or {})
            for row in stats.get("rows") or []:
                key = str(row.get("format_id") or row.get("file_type") or "Ukjent").strip()
                try:
                    count = int(row.get("count") or 0)
                except (TypeError, ValueError):
                    count = 0
                totals[key] = totals.get(key, 0) + count
        return sorted(totals.items(), key=lambda item: (-item[1], item[0]))[:4]

    def _a211_formats_card(self, parent, column: int, formats: list[tuple[str, int]], metrics: dict[str, object]) -> None:
        card = ctk.CTkFrame(parent, border_width=1, border_color=theme.CARD_BORDER, corner_radius=7)
        card.grid(row=0, column=column, sticky="nsew", padx=5)
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            card,
            text="Filformater",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 4))
        if formats:
            text = "\n".join(f"{name}  ·  {self._fmt_count(count)}" for name, count in formats)
        else:
            text = f"PRONOM-statistikkrader: {self._fmt_count(metrics.get('pronom_rows'))}\nIngen toppformater materialisert."
        ctk.CTkLabel(
            card,
            text=text,
            anchor="nw",
            justify="left",
            text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))

    def _a211_review_points(self) -> list[str]:
        raw = self.model.get("review_points") or self.model.get("deviations") or []
        if not isinstance(raw, list):
            return []
        rows = []
        for item in raw:
            if isinstance(item, str):
                text = item.strip()
            elif isinstance(item, dict):
                text = ""
                for key in ("title", "name", "message", "description", "test_id", "kind", "status"):
                    value = item.get(key)
                    if value not in (None, "", [], {}):
                        text = str(value).strip()
                        break
            else:
                text = str(item).strip()
            if text:
                rows.append(text)
        return rows

    def _a211_review_card(self, parent, column: int, points: list[str], metrics: dict[str, object]) -> None:
        card = ctk.CTkFrame(parent, border_width=1, border_color=theme.CARD_BORDER, corner_radius=7)
        card.grid(row=0, column=column, sticky="nsew", padx=(5, 0))
        card.grid_columnconfigure(0, weight=1)
        count = int(metrics.get("review_points") or len(points))
        ctk.CTkLabel(
            card,
            text=f"Vurderingspunkter  ·  {count}",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 4))
        if points:
            shown = points[:3]
            text = "\n".join(f"• {item[:72]}" for item in shown)
            if len(points) > 3:
                text += f"\n• + {len(points) - 3} flere"
        elif count:
            text = "Vurderingspunkter finnes i rapporten. Åpne Depotvurdering for detaljer."
        else:
            text = "Ingen materialiserte vurderingspunkter i depotrapporten."
        ctk.CTkLabel(
            card,
            text=text,
            anchor="nw",
            justify="left",
            text_color=theme.TEXT_SUB if count else theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
