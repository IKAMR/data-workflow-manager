from __future__ import annotations

from tkinter import messagebox
from typing import Callable, Iterable
import threading

import customtkinter as ctk

from noark5_workflow.core.job import Job
from noark5_workflow.reporting.depot_metadata import (
    ALL_EDITABLE_FIELDS,
    acknowledge_metadata,
    job_display_name,
    load_depot_metadata,
    metadata_review_state,
    scan_and_import_info_xml_for_jobs,
    source_values,
    suggest_label,
    update_current_metadata,
)
from version import APP_NAME
from . import theme


_FIELD_LABELS = [
    ("label", "LABEL / uttrekksidentitet"),
    ("system", "Kildesystem"),
    ("system_version", "Systemversjon"),
    ("period_start", "Periode fra"),
    ("period_end", "Periode til"),
    ("owner_org", "Eierorganisasjon (METS)"),
    ("creator", "Skaper / arkivskaper (METS)"),
    ("archivist_org", "Arkivorganisasjon"),
    ("submitter_org", "Avleverende organisasjon"),
    ("submitter_person", "Avleverende person"),
    ("submission_agreement", "Submission Agreement / leveransespesifikasjon"),
    ("archivist_type", "Arkivtype"),
    ("producer_org", "Produsent (org)"),
    ("producer_person", "Produsent (person)"),
    ("producer_software", "Produsent (programvare)"),
    ("preserver", "Bevaringsansvarlig"),
    ("owner_municipalities", "Eierkommune(r)"),
    ("archive_creators", "Arkivskapere / kommuner"),
    ("system_region", "IT-/systemregion"),
    ("delivery_information", "Informasjon om innleveringen / fritekst"),
]


class DepotMetadataDialog(ctk.CTkToplevel):
    """Set-based metadata workspace for all selected jobs."""

    def __init__(
        self,
        master,
        jobs: Iterable[Job],
        *,
        on_saved: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master)
        self._jobs = tuple(jobs)
        self._on_saved = on_saved or (lambda: None)
        self._field_index = 0
        self._vars: dict[str, ctk.StringVar] = {}
        self._edit_widgets: dict[str, object] = {}
        self._field_labels = {key: label for key, label in _FIELD_LABELS}
        self._field_keys = [key for key, _label in _FIELD_LABELS]
        self._label_to_key = {label: key for key, label in _FIELD_LABELS}
        self._scan_running = False
        self._scan_cancel_requested = False

        single_job = len(self._jobs) == 1
        self.title("Depotmetadata - ett uttrekk" if single_job else "Depotmetadata - valgte jobber")
        self.geometry("1380x860")
        self.minsize(1040, 680)
        self.configure(fg_color=theme.APP_BG)
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(
            self,
            text=("DEPOTMETADATA - ETT UTREKK" if len(self._jobs) == 1 else "DEPOTMETADATA - VALGTE JOBBER"),
            font=theme.font(theme.TITLE_SIZE, "bold"),
            text_color=theme.BLUE,
        ).grid(row=0, column=0, padx=22, pady=(18, 4), sticky="w")

        self._summary = ctk.CTkLabel(
            self,
            text="",
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        self._summary.grid(row=1, column=0, padx=22, pady=(0, 8), sticky="ew")

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=2, column=0, padx=22, pady=(0, 8), sticky="ew")
        toolbar.grid_columnconfigure(6, weight=1)

        self._scan_button = ctk.CTkButton(
            toolbar,
            text="Finn metadata...",
            width=170,
            command=self._scan_all,
            fg_color=theme.BLUE_DIM,
            hover_color=theme.BLUE,
        )
        self._scan_button.grid(row=0, column=0, padx=(0, 10), sticky="w")

        self._prev_field_button = ctk.CTkButton(
            toolbar,
            text="Forrige felt",
            width=105,
            command=self._previous_field,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        )
        self._prev_field_button.grid(row=0, column=1, padx=(0, 6), sticky="w")

        self._field_choice = ctk.StringVar(value=_FIELD_LABELS[0][1])
        self._field_menu = ctk.CTkOptionMenu(
            toolbar,
            variable=self._field_choice,
            values=[label for _key, label in _FIELD_LABELS],
            command=self._choose_field,
            width=310,
            fg_color=theme.BUTTON_BG,
            button_color=theme.BLUE_DIM,
            button_hover_color=theme.BLUE,
        )
        self._field_menu.grid(row=0, column=2, padx=(0, 6), sticky="w")

        self._next_field_button = ctk.CTkButton(
            toolbar,
            text="Neste felt",
            width=105,
            command=self._next_field,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        )
        self._next_field_button.grid(row=0, column=3, padx=(0, 10), sticky="w")

        ctk.CTkButton(
            toolbar,
            text="Lagre feltet",
            width=105,
            command=self._save_field,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=4, sticky="w")

        self._suggest_label_button = ctk.CTkButton(
            toolbar,
            text="Foreslå LABEL",
            width=125,
            command=self._suggest_labels_for_visible_rows,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        )
        self._suggest_label_button.grid(row=0, column=5, padx=(10, 0), sticky="w")

        self._status_frame = ctk.CTkScrollableFrame(
            self, fg_color=theme.SURFACE_BG, height=170
        )
        self._status_frame.grid(row=3, column=0, padx=22, pady=(0, 10), sticky="ew")
        self._status_frame.grid_columnconfigure(2, weight=1)

        self._field_frame = ctk.CTkScrollableFrame(self, fg_color=theme.SURFACE_BG)
        self._field_frame.grid(row=4, column=0, padx=22, pady=(0, 10), sticky="nsew")
        self._field_frame.grid_columnconfigure(2, weight=2)
        self._field_frame.grid_columnconfigure(3, weight=3)
        self._field_frame.grid_columnconfigure(4, weight=2)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=5, column=0, padx=22, pady=(0, 18), sticky="e")
        ctk.CTkButton(
            footer,
            text="Lukk",
            width=100,
            command=self.destroy,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            footer,
            text="Lagre feltet",
            width=120,
            command=self._save_field,
            fg_color=theme.BLUE,
            hover_color=theme.BLUE_DIM,
        ).pack(side="left")

        self._refresh_all()

    @property
    def _field_key(self) -> str:
        return self._field_keys[self._field_index]

    def _refresh_all(self) -> None:
        self._refresh_status()
        self._render_field()

    def _refresh_status(self) -> None:
        for child in self._status_frame.winfo_children():
            child.destroy()
        needs_review = 0
        for row, job in enumerate(self._jobs):
            state = metadata_review_state(job)
            required = bool(state["required"])
            if required:
                needs_review += 1
            icon = "⚠" if required else "✓"
            reason = "; ".join(state["reasons"][:2]) if required else "Metadata avklart"
            if required and len(state["reasons"]) > 2:
                reason += f" (+{len(state['reasons']) - 2})"
            ctk.CTkLabel(
                self._status_frame,
                text=icon,
                width=28,
                font=theme.font(theme.NORMAL_SIZE, "bold"),
                text_color=theme.DANGER_TEXT if required else theme.TEXT_SUB,
            ).grid(row=row, column=0, padx=(8, 6), pady=5, sticky="w")
            ctk.CTkLabel(
                self._status_frame,
                text=f"{job.job_id}   {job.name or job.job_id}",
                width=330,
                anchor="w",
                font=theme.font(theme.SMALL_SIZE, "bold"),
                text_color=theme.TEXT_MAIN,
            ).grid(row=row, column=1, padx=(0, 10), pady=5, sticky="w")
            ctk.CTkLabel(
                self._status_frame,
                text=reason,
                anchor="w",
                justify="left",
                font=theme.font(theme.SMALL_SIZE),
                text_color=theme.TEXT_MUTED,
            ).grid(row=row, column=2, padx=(0, 10), pady=5, sticky="ew")
            ctk.CTkLabel(
                self._status_frame,
                text=f"Kilder: {state['source_count']}",
                width=85,
                font=theme.font(theme.SMALL_SIZE),
                text_color=theme.TEXT_MUTED,
            ).grid(row=row, column=3, padx=(0, 8), pady=5)
            button = ctk.CTkButton(
                self._status_frame,
                text="Marker avklart",
                width=115,
                state="normal" if required else "disabled",
                command=lambda j=job: self._acknowledge(j),
                fg_color=theme.BUTTON_BG,
                hover_color=theme.BUTTON_HOVER,
            )
            button.grid(row=row, column=4, padx=(0, 8), pady=5)

        self._summary.configure(
            text=(
                f"{len(self._jobs)} valgte jobber · "
                f"{needs_review} med metadata som må avklares. "
                "Søk finner info.xml under jobbens Source/Work-områder, bevarer alle funn "
                "som dokumentasjon og overskriver ikke etablerte depotverdier."
            )
        )

    def _render_field(self) -> None:
        for child in self._field_frame.winfo_children():
            child.destroy()
        self._vars.clear()
        self._edit_widgets.clear()

        key = self._field_key
        label = self._field_labels[key]
        self._field_choice.set(label)

        ctk.CTkLabel(
            self._field_frame,
            text=label,
            font=theme.font(theme.SECTION_SIZE, "bold"),
            text_color=theme.BLUE,
            anchor="w",
        ).grid(row=0, column=0, columnspan=4, padx=10, pady=(8, 3), sticky="ew")
        ctk.CTkLabel(
            self._field_frame,
            text=(
                "Rediger gjeldende depotverdi for alle valgte jobber i samme visning. "
                "Kildeverdier viser verdier bevart fra importerte METS/info.xml-versjoner. "
                "Manglende LABEL kan få et forslag fra jobb-/kildenavn og lagret vurdert periode; "
                "forslaget lagres aldri uten at du velger det."
            ),
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
            anchor="w",
            justify="left",
        ).grid(row=1, column=0, columnspan=4, padx=10, pady=(0, 10), sticky="ew")

        headers = ("Jobb", "Status", "Gjeldende depotverdi", "Kildeverdier / historikk", "Forslag")
        for col, text in enumerate(headers):
            ctk.CTkLabel(
                self._field_frame,
                text=text,
                font=theme.font(theme.SMALL_SIZE, "bold"),
                text_color=theme.TEXT_SUB,
                anchor="w",
            ).grid(row=2, column=col, padx=8, pady=(0, 5), sticky="ew")

        for row, job in enumerate(self._jobs, start=3):
            payload = load_depot_metadata(job)
            state = metadata_review_state(job)
            current = str(payload["current"].get(key, "") or "")
            values = source_values(payload, key)
            source_text = " | ".join(values) if values else "-"
            if len(source_text) > 320:
                source_text = source_text[:317] + "..."

            ctk.CTkLabel(
                self._field_frame,
                text=f"{job.job_id}\n{job_display_name(job)}",
                font=theme.font(theme.SMALL_SIZE),
                text_color=theme.TEXT_MAIN,
                anchor="w",
                justify="left",
                wraplength=235,
            ).grid(row=row, column=0, padx=8, pady=7, sticky="ew")
            ctk.CTkLabel(
                self._field_frame,
                text="⚠ Avklar" if state["required"] else "✓ Avklart",
                width=90,
                font=theme.font(theme.SMALL_SIZE, "bold"),
                text_color=theme.DANGER_TEXT if state["required"] else theme.TEXT_SUB,
                anchor="w",
            ).grid(row=row, column=1, padx=8, pady=7, sticky="w")

            var = ctk.StringVar(value=current)
            self._vars[job.job_id] = var
            if key == "delivery_information":
                widget = ctk.CTkTextbox(
                    self._field_frame,
                    height=78,
                    wrap="word",
                    font=theme.font(theme.SMALL_SIZE),
                )
                widget.insert("1.0", current)
            else:
                widget = ctk.CTkEntry(
                    self._field_frame,
                    textvariable=var,
                    font=theme.font(theme.SMALL_SIZE),
                )
            widget.grid(row=row, column=2, padx=8, pady=7, sticky="ew")
            self._edit_widgets[job.job_id] = widget

            ctk.CTkLabel(
                self._field_frame,
                text=source_text,
                font=theme.font(theme.SMALL_SIZE),
                text_color=theme.TEXT_MUTED,
                anchor="w",
                justify="left",
                wraplength=470,
            ).grid(row=row, column=3, padx=8, pady=7, sticky="ew")

            if key == "label":
                suggestion = suggest_label(job)
                if suggestion and suggestion != current:
                    ctk.CTkButton(
                        self._field_frame,
                        text="Bruk forslag",
                        width=105,
                        command=lambda jid=job.job_id, value=suggestion: self._use_label_suggestion(jid, value),
                        fg_color=theme.BUTTON_BG,
                        hover_color=theme.BUTTON_HOVER,
                    ).grid(row=row, column=4, padx=(4, 8), pady=(5, 1), sticky="w")
                    ctk.CTkLabel(
                        self._field_frame,
                        text=suggestion,
                        font=theme.font(theme.SMALL_SIZE),
                        text_color=theme.TEXT_MUTED,
                        anchor="w",
                        justify="left",
                        wraplength=260,
                    ).grid(row=row, column=4, padx=(4, 8), pady=(34, 5), sticky="ew")

        self._prev_field_button.configure(
            state="normal" if self._field_index > 0 else "disabled"
        )
        self._next_field_button.configure(
            state="normal" if self._field_index < len(self._field_keys) - 1 else "disabled"
        )
        self._suggest_label_button.configure(
            state="normal" if key == "label" else "disabled"
        )

    def _suggest_labels_for_visible_rows(self) -> None:
        """Find LABEL proposals off the GUI thread and let the operator decide."""
        if self._scan_running:
            return
        if self._field_key != "label":
            self._field_index = self._field_keys.index("label")
            self._render_field()

        current_by_job = {
            job.job_id: (self._vars.get(job.job_id).get().strip() if self._vars.get(job.job_id) else "")
            for job in self._jobs
        }
        self._scan_running = True
        self._suggest_label_button.configure(text="Foreslår 0/%d..." % len(self._jobs), state="disabled")
        self._summary.configure(text=f"Foreslår LABEL: 0 av {len(self._jobs)} jobber ...")

        def worker() -> None:
            proposals: list[tuple[Job, str, str]] = []
            failures: list[str] = []
            for index, job in enumerate(self._jobs, start=1):
                try:
                    suggestion = suggest_label(job)
                    current = current_by_job.get(job.job_id, "")
                    if suggestion and suggestion != current:
                        proposals.append((job, current, suggestion))
                except Exception as exc:
                    failures.append(f"{job.job_id}: {exc}")
                try:
                    self.after(
                        0,
                        lambda i=index, j=job: (
                            self._suggest_label_button.configure(text=f"Foreslår {i}/{len(self._jobs)}..."),
                            self._summary.configure(text=f"Foreslår LABEL: {i} av {len(self._jobs)} · {j.job_id}"),
                        ),
                    )
                except Exception:
                    pass

            def finish() -> None:
                self._scan_running = False
                self._suggest_label_button.configure(text="Foreslå LABEL", state="normal")
                if not proposals:
                    detail = "Ingen nye LABEL-forslag kunne lages. Eksisterende verdier er ikke endret."
                    if failures:
                        detail += "\n\nFeil:\n" + "\n".join(failures[:8])
                    self._summary.configure(text=f"LABEL-forslag ferdig: 0 endringer · {len(failures)} feil")
                    messagebox.showinfo(APP_NAME, detail, parent=self)
                    return

                lines = []
                for job, old, new in proposals:
                    before = old or "(tom)"
                    lines.append(f"{job.job_id}: {before}  →  {new}")
                if len(lines) > 10:
                    lines = lines[:10] + [f"... og {len(proposals) - 10} til"]
                concrete = sum(1 for _job, _old, new in proposals if "YYYY" not in new)
                placeholder = len(proposals) - concrete
                question = (
                    f"LABEL-forslag er ferdig.\n\n"
                    f"Forslag/endringer: {len(proposals)}\n"
                    f"Med konkret periode: {concrete}\n"
                    f"Fortsatt uavklart periode: {placeholder}\n"
                    f"Feil: {len(failures)}\n\n"
                    + "\n".join(lines)
                    + "\n\nJa = bruk forslagene og lagre dem.\n"
                      "Nei = bruk forslagene i feltene uten å lagre ennå.\n"
                      "Avbryt = forkast forslagene."
                )
                decision = messagebox.askyesnocancel(APP_NAME, question, parent=self)
                if decision is None:
                    self._summary.configure(text=f"LABEL-forslag forkastet: {len(proposals)}")
                    return
                for job, _old, new in proposals:
                    var = self._vars.get(job.job_id)
                    if var is not None:
                        var.set(new)
                if decision is True:
                    if self._save_field(quiet=True):
                        self._summary.configure(text=f"LABEL-forslag brukt og lagret: {len(proposals)}")
                        messagebox.showinfo(APP_NAME, f"{len(proposals)} LABEL-forslag er brukt og lagret.", parent=self)
                else:
                    self._summary.configure(text=f"LABEL-forslag lagt i feltene, ikke lagret: {len(proposals)}")

            try:
                self.after(0, finish)
            except Exception:
                pass

        threading.Thread(
            target=worker,
            name="depot-label-suggestion",
            daemon=True,
        ).start()

    def _use_label_suggestion(self, job_id: str, value: str) -> None:
        var = self._vars.get(job_id)
        if var is not None:
            var.set(value)

    def _collect_current_field(self) -> list[tuple[Job, str]]:
        values: list[tuple[Job, str]] = []
        for job in self._jobs:
            widget = self._edit_widgets.get(job.job_id)
            if self._field_key == "delivery_information" and widget is not None:
                value = widget.get("1.0", "end").strip()
            else:
                value = self._vars[job.job_id].get().strip()
            values.append((job, value))
        return values

    def _save_field(self, *, quiet: bool = False) -> bool:
        try:
            values = self._collect_current_field()
            for job, value in values:
                update_current_metadata(job, {self._field_key: value})
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Kunne ikke lagre depotmetadata:\n{exc}", parent=self)
            return False
        self._on_saved()
        self._refresh_status()
        if not quiet:
            messagebox.showinfo(APP_NAME, "Feltet er lagret for valgte jobber.", parent=self)
        return True

    def _scan_all(self) -> None:
        if self._scan_running:
            self._scan_cancel_requested = True
            self._scan_button.configure(text="Avbryter...", state="disabled")
            return
        if not self._save_field(quiet=True):
            return

        self._scan_running = True
        self._scan_cancel_requested = False
        self._scan_button.configure(text="Avbryt søk", state="normal")
        self._summary.configure(
            text=f"Søker metadata: 0 av {len(self._jobs)} jobber ..."
        )

        def worker() -> None:
            results = []
            failure = None
            try:
                for index, job in enumerate(self._jobs, start=1):
                    if self._scan_cancel_requested:
                        break
                    self.after(
                        0,
                        lambda i=index, j=job: self._summary.configure(
                            text=(
                                f"Søker metadata: {i} av {len(self._jobs)} · "
                                f"{j.job_id} {j.name or j.job_id}"
                            )
                        ),
                    )
                    results.append(scan_and_import_info_xml_for_jobs((job,))[0])
            except Exception as exc:
                failure = exc

            def finish() -> None:
                self._scan_running = False
                cancelled = self._scan_cancel_requested
                self._scan_cancel_requested = False
                self._scan_button.configure(text="Finn metadata...", state="normal")
                self._on_saved()
                self._refresh_all()
                if failure is not None:
                    messagebox.showerror(
                        APP_NAME, f"Søk etter metadata feilet:\n{failure}", parent=self
                    )
                    return
                if cancelled:
                    self._summary.configure(
                        text=f"Metadata-søk avbrutt etter {len(results)} jobb(er)."
                    )
                    return
                found = sum(int(item["candidate_count"]) for item in results)
                imported = sum(int(item["imported_new"]) for item in results)
                errors = sum(len(item["errors"]) for item in results)
                review = sum(1 for item in results if item["review_required"])
                messagebox.showinfo(
                    APP_NAME,
                    (
                        f"Metadata-søk ferdig for {len(results)} jobb(er).\n\n"
                        f"Funn: {found}\nNye kildeversjoner lagret: {imported}\n"
                        f"Må avklares: {review}\nFeil: {errors}\n\n"
                        "Nye kildeverdier overskriver aldri eksisterende depotverdier automatisk. "
                        "Ved avvik går du gjennom feltene og velger hvilken verdi som skal gjelde."
                    ),
                    parent=self,
                )

            try:
                self.after(0, finish)
            except Exception:
                pass

        threading.Thread(
            target=worker,
            name="depot-metadata-discovery",
            daemon=True,
        ).start()

    def _acknowledge(self, job: Job) -> None:
        if not self._save_field(quiet=True):
            return
        state = metadata_review_state(job)
        reasons = "\n- ".join(state["reasons"])
        if not messagebox.askyesno(
            APP_NAME,
            (
                f"Marker depotmetadata som avklart for {job.job_id}?\n\n"
                f"Gjeldende avklaringspunkter:\n- {reasons or 'Ingen'}\n\n"
                "Importhistorikken beholdes uendret."
            ),
            parent=self,
        ):
            return
        try:
            acknowledge_metadata(job)
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Kunne ikke markere metadata som avklart:\n{exc}", parent=self)
            return
        self._on_saved()
        self._refresh_all()

    def _choose_field(self, label: str) -> None:
        key = self._label_to_key.get(label)
        if key is None or key == self._field_key:
            return
        if not self._save_field(quiet=True):
            self._field_choice.set(self._field_labels[self._field_key])
            return
        self._field_index = self._field_keys.index(key)
        self._render_field()

    def _previous_field(self) -> None:
        if self._field_index <= 0 or not self._save_field(quiet=True):
            return
        self._field_index -= 1
        self._render_field()

    def _next_field(self) -> None:
        if self._field_index >= len(self._field_keys) - 1 or not self._save_field(quiet=True):
            return
        self._field_index += 1
        self._render_field()
