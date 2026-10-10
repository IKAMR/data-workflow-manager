from __future__ import annotations

from tkinter import messagebox
import customtkinter as ctk
from .kdrs_query_results_a4 import KdrsQueryResultsDialog, DirectEvidenceSelector
from noark5_workflow.external_evidence.arkade5 import infer_work_operations_from_depot_report

from .depot_result_center_a16_16 import DepotResultCenterDialogA16_16
from .depot_result_center_a19_5 import DepotResultCenterDialogA19_5
from .work_window_state_v017_a1 import install_work_window_state, job_window_state_key


class V017A1DepotResultCenterDialog(DepotResultCenterDialogA19_5):
    """Result window, including explicit KDRS report-value selections."""

    def __init__(self, master, *, display_name: str = "", **kwargs) -> None:
        self._v017_display_name = str(display_name or "").strip() or "Ukjent uttrekk"
        super().__init__(master, **kwargs)
        try:
            self.geometry("1180x720")
        except Exception:
            pass
        self._a5_archive_evidence_enabled = False
        self._install_kdrs_query_tab()
        self._install_a5_archive_evidence()
        self._a5_archive_evidence_enabled = True
        self._apply_v017_identity_title()
        self.bind("<Map>", lambda _event: self._apply_v017_identity_title(), add="+")
        self.after_idle(self._apply_v017_identity_title)
        self.after(250, self._apply_v017_identity_title)
        install_work_window_state(
            self,
            job_window_state_key("resultatvisninger", self._v017_display_name),
            max_width_fraction=0.92,
            max_height_fraction=0.82,
        )
        for widget in self.grid_slaves(row=0, column=0):
            try:
                current = str(widget.cget("text") or "")
            except Exception:
                continue
            if "allerede genererte depotrapporten" in current:
                widget.configure(
                    text=(
                        f"UTTREKK: {self._v017_display_name}\n"
                        "Visningene leser den allerede genererte depotrapporten og kjører ingen ny analyse."
                    )
                )
                break

    def _open_a65_multi_overview(self) -> None:
        from .noark5_multi_overview_a65 import MultiExtractionOverview
        MultiExtractionOverview(self, report_path=self.report_path)

    def _install_kdrs_query_tab(self) -> None:
        """Show external result sources without making KDRS the tab identity."""
        tabs = self._root_tabview()
        if tabs is None:
            return
        tabs.add("Eksterne kilder")
        tab = tabs.tab("Eksterne kilder")
        tab.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            tab, text="Eksterne kilder – importert analysegrunnlag",
            anchor="w", font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 9))
        ctk.CTkLabel(
            tab, text="Resultater fra eksterne analyseverktøy vises med kildehenvisninger. "
                      "Ingen ny import eller analyse utføres her.",
            anchor="w", justify="left",
        ).grid(row=1, column=0, sticky="ew", padx=20, pady=8)
        source = ctk.CTkFrame(tab)
        source.grid(row=2, column=0, sticky="ew", padx=20, pady=10)
        source.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            source, text="KDRS Query – Standard, U1 og U2",
            anchor="w", font=ctk.CTkFont(weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        ctk.CTkLabel(
            source, text="Importerte resultater og valg av rapportgrunnlag.",
            anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 12))
        ctk.CTkButton(
            source, text="Vis KDRS Query-resultater",
            width=235, command=self._open_v017_kdrs_query,
        ).grid(row=0, column=1, rowspan=2, sticky="e", padx=12, pady=12)
        report_actions = ctk.CTkFrame(tab, fg_color="transparent")
        report_actions.grid(row=9, column=0, sticky="w", padx=20, pady=(0, 12))
        ctk.CTkButton(
            report_actions, text="Depotrapporter", width=190,
            command=self._open_a5_report_dialog).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            report_actions, text="Kildesammenligning (HTML)", width=230,
            command=self._open_a5_evidence_html).pack(side="left")
        ctk.CTkButton(
            report_actions, text="Samlet uttrekksoversikt", width=220,
            command=self._open_a65_multi_overview).pack(side="left", padx=(8, 0))
        self._a5_evidence_status = ctk.CTkLabel(
            tab, text="Evidensstatus er ikke kontrollert ennå.", anchor="w", justify="left")
        self._a5_evidence_status.grid(row=3, column=0, sticky="ew", padx=20, pady=(8, 4))
        ctk.CTkButton(
            tab, text="Oppdater evidensgrunnlag", width=230,
            command=self._refresh_a5_evidence).grid(row=4, column=0, sticky="w", padx=20, pady=(4, 16))
        ctk.CTkLabel(tab, text="Arkivdelvis evidens (U2 / DWM)", anchor="w",
                     font=ctk.CTkFont(weight="bold")).grid(row=5, column=0, sticky="w", padx=20, pady=(12, 2))
        selector = ctk.CTkFrame(tab, fg_color="transparent")
        selector.grid(row=6, column=0, sticky="ew", padx=20)
        self._a5_part_labels = {}
        # Controls stay anchored at the left even when an archive name is long.
        # The native dropdown may clip entries; arrows always navigate all parts.
        self._a5_prev_part = ctk.CTkButton(
            selector, text="◀", width=38, command=lambda: self._step_a5_part(-1))
        self._a5_prev_part.pack(side="left", padx=(0, 4), pady=4)
        self._a5_next_part = ctk.CTkButton(
            selector, text="▶", width=38, command=lambda: self._step_a5_part(1))
        self._a5_next_part.pack(side="left", padx=(0, 8), pady=4)
        self._a5_part_menu = ctk.CTkOptionMenu(selector, values=["Ingen arkivdeler"],
                                               width=380, command=self._show_a5_part_evidence)
        self._a5_part_menu.pack(side="left", padx=(0, 8), pady=4)
        self._a5_part_position = ctk.CTkLabel(selector, text="0 / 0 arkivdeler")
        self._a5_part_position.pack(side="left", padx=(0, 8), pady=4)
        # Evidence selection follows the chosen part and an explicit metric.
        self._a5_metric_labels = {
            'Mapper': 'folder_count',
            'Saksmapper': 'case_folder_count',
            'Registreringer': 'registration_count',
            'Journalposter': 'journalpost_count',
            'Dokumentbeskrivelser': 'document_description_count',
            'Dokumentobjekter': 'document_object_count',
            'Korrespondanseparter': 'correspondence_party_count',
        }
        choice_row = ctk.CTkFrame(tab, fg_color='transparent')
        choice_row.grid(row=7, column=0, sticky='w', padx=20, pady=(6, 4))
        ctk.CTkLabel(choice_row, text='Måltall:').pack(side='left', padx=(0, 6))
        self._a5_metric_choice = ctk.CTkOptionMenu(
            choice_row, values=list(self._a5_metric_labels), width=200)
        self._a5_metric_choice.pack(side='left', padx=(0, 8))
        ctk.CTkButton(choice_row, text='Velg evidens for arkivdel', width=220,
                      command=self._choose_a5_part_evidence).pack(side='left')
        self._a5_part_evidence_table = ctk.CTkScrollableFrame(tab, height=290)
        self._a5_part_evidence_table.grid(row=8, column=0, sticky="nsew", padx=20, pady=(4, 8))
        self._a5_part_evidence_table.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(8, weight=1)
        # Build the non-destructive companion after the window layout exists.
        self.after_idle(self._refresh_a5_evidence)

    def _install_a5_archive_evidence(self) -> None:
        """A read-only section inside the inherited Arkivdeler assessment surface."""
        frame = getattr(self, '_assessment_surface', None)
        if frame is None:
            return
        panel = ctk.CTkFrame(frame)
        next_row = max([int(child.grid_info().get('row', 0))
                        for child in frame.winfo_children() if child.grid_info()] + [0]) + 1
        panel.grid(row=next_row, column=0, sticky='ew', padx=4, pady=(2, 12))
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(panel, text='Ekstern evidens – valgt arkivdel',
                     font=ctk.CTkFont(weight='bold'), anchor='w').grid(
                         row=0, column=0, sticky='ew', padx=12, pady=(8, 2))
        self._a5_archive_evidence_label = ctk.CTkLabel(
            panel, text='Ingen valgt ekstern evidens.', anchor='w',
            justify='left', wraplength=940)
        self._a5_archive_evidence_label.grid(row=1, column=0, sticky='ew', padx=12, pady=(0, 10))

    def _render_a5_archive_evidence(self, index: int) -> None:
        label = getattr(self, '_a5_archive_evidence_label', None)
        if label is None:
            return
        from noark5_workflow.external_evidence.archive_part_evidence_a5 import archive_part_summary
        projection = getattr(self, '_a5_effective_projection', {})
        parts = getattr(self, '_archive_parts', [])
        if not projection or not (0 <= index < len(parts)):
            label.configure(text='Ingen tilgjengelig evidens for valgt arkivdel.')
            return
        # The first inherited row may represent a synthetic whole-extract part.
        row = parts[index]
        if row.get('is_all_archive_parts'):
            label.configure(text='Samlet visning: velg en arkivdel for evidens.')
            return
        # Map by system ID/title rather than assuming GUI indexes equal report indexes.
        identity = row.get('archive_part') or {}
        matching = []
        for part_number, entry in (projection.get('archive_parts') or {}).items():
            candidate = entry.get('archive_part') or {}
            sid = str(identity.get('system_id') or '').strip()
            if sid and sid == str(candidate.get('system_id') or '').strip():
                matching.append(int(part_number))
        if len(matching) != 1:
            label.configure(text='Arkivdel kunne ikke kobles entydig til evidens. Ingen verdi brukes.')
            return
        lines = archive_part_summary(projection, matching[0])
        label.configure(text='\n'.join(lines) if lines else 'Ingen valgt ekstern evidens for denne arkivdelen. DWM-verdier beholdes.')

    def _a5_report_html_paths(self):
        """Return current native and derived HTML paths without creating files."""
        from pathlib import Path
        report = Path(getattr(self, 'report_path', '') or '')
        return (
            report.with_name('depot_validation_report.html'),
            report.with_name('depot-derived-evidence-report.html'),
        )

    def _open_a5_report_dialog(self) -> None:
        """One place to open existing report variants, with explicit source identity."""
        import webbrowser
        import sys
        import os

        dialog = ctk.CTkToplevel(self)
        dialog.title('Depotrapporter – DWM og godkjent evidens')
        dialog.geometry('650x290')
        dialog.transient(self)
        dialog.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            dialog, text='Velg depotrapport',
            font=ctk.CTkFont(size=17, weight='bold'), anchor='w',
        ).grid(row=0, column=0, sticky='ew', padx=18, pady=(16, 6))
        ctk.CTkLabel(
            dialog,
            text=('DWM-rapport: opprinnelige analyser og verdier.\n'
                  'Depotrapport med godkjent evidens: viser eksplisitt valgte KDRS-verdier.'),
            anchor='w', justify='left',
        ).grid(row=1, column=0, sticky='ew', padx=18, pady=(0, 12))

        def open_file(path):
            if not path.is_file():
                messagebox.showwarning('Depotrapporter', 'Rapportfilen finnes ikke.', parent=dialog)
                return
            try:
                if sys.platform == 'win32':
                    os.startfile(str(path))
                else:
                    webbrowser.open(path.resolve().as_uri())
            except (OSError, ValueError) as exc:
                messagebox.showerror('Depotrapporter', str(exc), parent=dialog)

        for row, (title, path) in enumerate(zip(
            ('DWM-rapport (opprinnelig)', 'Depotrapport med godkjent evidens'), self._a5_report_html_paths()
        ), start=2):
            ctk.CTkLabel(
                dialog, text=('Tilgjengelig' if path.is_file() else 'Ikke generert'), anchor='w',
            ).grid(row=row, column=0, sticky='w', padx=18, pady=7)
            ctk.CTkButton(
                dialog, text=title, width=190,
                state="normal" if path.is_file() else "disabled",
                command=lambda report_file=path: open_file(report_file),
            ).grid(row=row, column=0, sticky='e', padx=18, pady=7)
        ctk.CTkButton(dialog, text='Lukk', width=110, command=dialog.destroy).grid(
            row=4, column=0, sticky='e', padx=18, pady=(12, 14))

    def _open_a5_evidence_html(self) -> None:
        """Open generated read-only evidence report using the OS default application."""
        import os
        import sys
        import webbrowser
        path = getattr(self, '_a5_evidence_html_path', None)
        if path is None or not path.is_file():
            messagebox.showwarning('Evidensrapport',
                'Ingen evidensrapport finnes. Velg Oppdater evidensgrunnlag først.', parent=self)
            return
        try:
            if sys.platform == 'win32':
                os.startfile(str(path))
            else:
                webbrowser.open(path.as_uri())
        except (OSError, ValueError) as exc:
            messagebox.showerror('Evidensrapport', str(exc), parent=self)

    def _refresh_a5_evidence(self) -> None:
        """Reconcile existing native depot report and external decisions, never rewrite native."""
        from pathlib import Path
        status = getattr(self, '_a5_evidence_status', None)
        if status is None:
            return
        report_path = Path(getattr(self, 'report_path', '') or '')
        if not report_path.is_file():
            status.configure(text='Ingen tilgjengelig depotrapport for evidenssammenligning.')
            return False
        try:
            from noark5_workflow.external_evidence.evidence_report_bridge_a5 import (
                write_depot_evidence_companion,
            )
            from noark5_workflow.external_evidence.arkade5 import infer_work_operations_from_depot_report
            import json
            work = infer_work_operations_from_depot_report(report_path)
            companion = write_depot_evidence_companion(report_path, work)
            from noark5_workflow.external_evidence.evidence_projection_a5 import write_effective_projection
            projection_path = write_effective_projection(report_path, companion)
            from noark5_workflow.external_evidence.effective_depot_report_a5 import write_derived_depot_report
            self._a5_derived_report_path = write_derived_depot_report(report_path, projection_path)
            from noark5_workflow.external_evidence.derived_depot_html_a5 import write_derived_depot_html
            self._a5_derived_html_path = write_derived_depot_html(self._a5_derived_report_path)
            self._a5_effective_projection = json.loads(projection_path.read_text(encoding='utf-8'))
            self._render_a5_archive_evidence(getattr(self, '_archive_index', 0))
            from noark5_workflow.external_evidence.evidence_html_a5 import write_evidence_html
            self._a5_evidence_html_path = write_evidence_html(projection_path)
            data = json.loads(companion.read_text(encoding='utf-8'))
            from noark5_workflow.external_evidence.evidence_status_a5 import coverage_summary
            self._a5_evidence_annex = data
            self._update_a5_part_options()
            status.configure(text=coverage_summary(data))
            return True
        except (OSError, ValueError, TypeError, KeyError) as exc:
            status.configure(text=f'Evidensgrunnlag kunne ikke oppdateres: {exc}')
            return False

    def _update_a5_part_options(self) -> None:
        from noark5_workflow.external_evidence.archive_part_evidence_a5 import available_archive_parts
        parts = available_archive_parts(getattr(self, '_a5_evidence_annex', {}))
        self._a5_part_labels = {f'{index}: {title}': index for index, title in parts}
        menu = getattr(self, '_a5_part_menu', None)
        if menu is None:
            return
        labels = list(self._a5_part_labels) or ['Ingen arkivdeler']
        previous = menu.get()
        menu.configure(values=labels)
        chosen = previous if previous in self._a5_part_labels else labels[0]
        menu.set(chosen)
        self._show_a5_part_evidence(chosen)

    def _step_a5_part(self, step: int) -> None:
        """Move through all archive parts regardless of popup height or scrolling."""
        labels = list(getattr(self, '_a5_part_labels', {}))
        if not labels:
            return
        current = self._a5_part_menu.get()
        index = labels.index(current) if current in labels else 0
        target = (index + step) % len(labels)
        self._a5_part_menu.set(labels[target])
        self._show_a5_part_evidence(labels[target])

    def _show_a5_part_evidence(self, choice: str) -> None:
        """Readable fact table; provenance remains available for every approved choice."""
        from noark5_workflow.external_evidence.archive_part_evidence_a5 import evidence_table_rows
        table = getattr(self, '_a5_part_evidence_table', None)
        if table is None:
            return
        index = self._a5_part_labels.get(choice)
        labels = list(self._a5_part_labels)
        position = labels.index(choice) + 1 if choice in self._a5_part_labels else 0
        counter = getattr(self, '_a5_part_position', None)
        if counter is not None:
            counter.configure(text=f'{position} / {len(labels)} arkivdeler')
        for arrow in (getattr(self, '_a5_prev_part', None), getattr(self, '_a5_next_part', None)):
            if arrow is not None:
                arrow.configure(state='normal' if len(labels) > 1 else 'disabled')
        for child in table.winfo_children():
            child.destroy()
        # A dense table fits the common metrics on a laptop without wasting width.
        # Provenance appears only beneath selected values; never conflate unknown and zero.
        headings = ('Måltall', 'DWM', 'KDRS', 'Valgt', 'Vurdering', '')
        for col, heading in enumerate(headings):
            table.grid_columnconfigure(col, weight=2 if col in (0, 4) else 1)
            ctk.CTkLabel(table, text=heading, anchor='w',
                         font=ctk.CTkFont(size=12, weight='bold')).grid(
                             row=0, column=col, sticky='ew', padx=6, pady=(5, 6))
        rows = evidence_table_rows(getattr(self, '_a5_evidence_annex', {}), index)
        for row_number, item in enumerate(rows, 1):
            metric, dwm, kdrs, chosen, verdict = item['cells']
            values = (metric, dwm, kdrs, chosen, verdict)
            for col, value in enumerate(values):
                ctk.CTkLabel(table, text=value, anchor='w',
                             font=ctk.CTkFont(size=12, weight='bold' if col == 0 or (col == 3 and chosen != 'Ikke valgt') else 'normal')).grid(
                                 row=row_number * 2 - 1, column=col, sticky='ew',
                                 padx=6, pady=(4, 2))
            if metric in self._a5_metric_labels:
                ctk.CTkButton(table, text='Velg', width=52, height=25,
                              command=lambda name=metric: self._choose_a5_metric(name)).grid(
                                  row=row_number * 2 - 1, column=5, sticky='e', padx=4, pady=2)
            # Only approved decisions require multi-line provenance in the table.
            if item['detail'] and chosen != 'Ikke valgt':
                ctk.CTkLabel(table, text=item['detail'], anchor='w', justify='left',
                             wraplength=850, font=ctk.CTkFont(size=11)).grid(
                                 row=row_number * 2, column=0, columnspan=6,
                                 sticky='ew', padx=6, pady=(0, 5))
        if not rows:
            ctk.CTkLabel(table, text='Ingen måltall for denne arkivdelen.', anchor='w').grid(
                row=1, column=0, padx=8, pady=12, sticky='w')

    def _choose_a5_metric(self, metric_label: str) -> None:
        """Select an exact metric in the existing audited decision workflow."""
        if metric_label not in self._a5_metric_labels:
            return
        self._a5_metric_choice.set(metric_label)
        self._choose_a5_part_evidence()

    def _choose_a5_part_evidence(self) -> None:
        """Open documented selection with exactly the visible part and metric."""
        part_label = self._a5_part_menu.get()
        part_index = getattr(self, '_a5_part_labels', {}).get(part_label)
        if part_index is None:
            messagebox.showwarning('Evidens', 'Velg en arkivdel først.', parent=self)
            return
        metric = self._a5_metric_labels.get(self._a5_metric_choice.get())
        try:
            work = infer_work_operations_from_depot_report(self.report_path)
            dialog = DirectEvidenceSelector(self, work_operations=work,
                                            on_evidence_saved=self._refresh_a5_evidence,
                                            report_path=self.report_path)
            dialog._show_evidence_dialog(initial_metric=metric, initial_part=part_index)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            messagebox.showerror('Evidens', str(exc), parent=self)

    def _open_v017_kdrs_query(self) -> None:
        try:
            work = infer_work_operations_from_depot_report(self.report_path)
            KdrsQueryResultsDialog(self, work_operations=work, report_path=self.report_path)
        except Exception as exc:
            messagebox.showerror("KDRS Query", str(exc), parent=self)

    def _a5_evidence_count(self, key: str):
        """Resolve a verified explicit decision; retain original result on errors."""
        aliases = {'case_count': 'case_folder_count'}
        metric = aliases.get(key, key)
        try:
            from noark5_workflow.external_evidence.kdrs_query_mapping import build_mapped_pool
            from noark5_workflow.external_evidence.evidence_decisions_a5 import load_decisions, report_evidence
            work = infer_work_operations_from_depot_report(self.report_path)
            decisions = load_decisions(work)
            if 'whole:' + metric not in decisions:
                return None
            resolved = report_evidence(build_mapped_pool(work), decisions, metric=metric)
            if resolved['status'] == 'external_evidence_selected':
                return resolved['effective_value']
        except (OSError, ValueError, KeyError, TypeError):
            return None
        return None

    def _kdrs_selected_count(self, key: str):
        try:
            from noark5_workflow.external_evidence.arkade5 import infer_work_operations_from_depot_report
            from noark5_workflow.external_evidence.kdrs_query_selection import selected_count
            path = getattr(self, 'report_path', None)
            if path is None:
                return None
            return selected_count(infer_work_operations_from_depot_report(path), key)
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def _summary_value(self, *keys):
        # A source selected by the operator can override the display value;
        # the original DWM master result and report JSON remain unchanged.
        for key in keys:
            selected = self._a5_evidence_count(key)
            if selected is not None:
                return selected
            selected = self._kdrs_selected_count(key)
            if selected is not None:
                return selected
        return super()._summary_value(*keys)

    def _case_count_whole(self):
        selected = self._a5_evidence_count('case_count')
        if selected is None:
            selected = self._kdrs_selected_count('case_count')
        if selected is not None:
            return selected
        return super()._case_count_whole()

    def _apply_v017_identity_title(self) -> None:
        try:
            self.title(f"Resultatvisninger – Noark 5 – {self._v017_display_name}")
        except Exception:
            pass

    def _show_archive_part(self, index: int) -> None:
        if getattr(self, "_a1616_start_var", None) is None or getattr(
            self, "_a1616_end_var", None
        ) is None:
            return super(DepotResultCenterDialogA16_16, self)._show_archive_part(index)
        result = super()._show_archive_part(index)
        if getattr(self, '_a5_archive_evidence_enabled', False):
            self._render_a5_archive_evidence(index)
        return result
