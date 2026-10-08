from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox
import threading

import customtkinter as ctk

from noark5_workflow.core.job import Job
from noark5_workflow.reporting.depot_metadata import (
    acknowledge_metadata,
    export_info_xml,
    import_selected_info_xml,
    load_depot_metadata,
    metadata_review_state,
    scan_and_import_info_xml,
    source_values,
    update_current_metadata,
    job_display_name,
)
from version import APP_NAME, VERSION
from . import theme
from .work_window_state_v017_a1 import install_work_window_state, job_window_state_key


_FIELDS = (
    # Rows 1-47 follow 0000-metadata-arkade.xlsx / Arkade 5 GUI order.
    ("archive_description", "Arkivbeskrivelse", "Arkiv / pakke"),
    ("submission_agreement", "Avtalenr", "Arkiv / pakke"),
    ("record_status", "Oppføringstype", "Arkiv / pakke"),
    ("delivery_type", "Arkivsystemtype", "Arkiv / pakke"),
    ("project_name", "Prosjektnavn", "Arkiv / pakke"),
    ("package_number", "Pakkenummer", "Arkiv / pakke"),
    ("reference_code", "Referansekode", "Arkiv / pakke"),

    ("archivist_org", "Arkivskaper", "Arkivskaper"),
    ("archivist_person", "Kontaktperson", "Arkivskaper"),
    ("archivist_address", "Adresse", "Arkivskaper"),
    ("archivist_phone", "Telefon", "Arkivskaper"),
    ("archivist_email", "Epost", "Arkivskaper"),

    ("submitter_org", "Overfører", "Overfører"),
    ("submitter_person", "Kontaktperson", "Overfører"),
    ("submitter_address", "Adresse", "Overfører"),
    ("submitter_phone", "Telefon", "Overfører"),
    ("submitter_email", "Epost", "Overfører"),

    ("producer_org", "Produsent", "Produsent"),
    ("producer_person", "Kontaktperson", "Produsent"),
    ("producer_address", "Adresse", "Produsent"),
    ("producer_phone", "Telefon", "Produsent"),
    ("producer_email", "Epost", "Produsent"),

    ("owner_org", "Eier", "Eier"),
    ("owner_person", "Kontaktperson", "Eier"),
    ("owner_address", "Adresse", "Eier"),
    ("owner_phone", "Telefon", "Eier"),
    ("owner_email", "Epost", "Eier"),

    ("creator_org", "Skaper info.xml", "Skaper info.xml"),
    ("creator_person", "Kontaktperson", "Skaper info.xml"),
    ("creator_address", "Adresse", "Skaper info.xml"),
    ("creator_phone", "Telefon", "Skaper info.xml"),
    ("creator_email", "Epost", "Skaper info.xml"),

    ("mets_creator_software", "METS program", "METS program"),
    ("mets_creator_software_version", "METS program versjon", "METS program"),
    ("recipient", "Mottaker", "Mottaker"),

    ("system", "Systemnavn", "System"),
    ("system_version", "Versjon", "System"),
    ("system_type", "Type", "System"),
    ("system_type_version", "Typeversjon", "System"),

    ("extraction_system", "Uttrekkssystem", "Uttrekkssystem"),
    ("extraction_system_version", "Versjon", "Uttrekkssystem"),
    ("extraction_system_type", "Type", "Uttrekkssystem"),
    ("extraction_system_type_version", "Typeversjon", "Uttrekkssystem"),

    ("period_start", "Startdato", "Periode / uttrekk"),
    ("period_end", "Sluttdato", "Periode / uttrekk"),
    ("extraction_date", "Uttrekksdato", "Periode / uttrekk"),
    ("label", "Merkelapp", "Merkelapp"),

    # Depot/portal values are deliberately separate from DIAS/METS.
    ("owner_municipalities", "Eierkommune(r)", "Depotmetadata / tillegg"),
    ("archive_creators", "Arkivskapere / historiske kommuner", "Depotmetadata / tillegg"),
    ("system_region", "IT-/systemregion", "Depotmetadata / tillegg"),
    ("delivery_information", "Informasjon om innleveringen / fritekst", "Depotmetadata / tillegg"),
)

_READ_ONLY_CURRENT = {
    "mets_creator_software": APP_NAME,
    "mets_creator_software_version": VERSION,
}



class DepotMetadataEditor(ctk.CTkToplevel):
    """Edit the current depot metadata for exactly one extraction/job.

    Imported METS/info.xml values remain immutable source evidence in the
    metadata sidecar. Editing changes only the current depot value set.
    """

    def __init__(self, master, job: Job, *, on_saved=None) -> None:
        super().__init__(master)
        self.job = job
        self._on_saved = on_saved or (lambda: None)
        self._vars: dict[str, ctk.StringVar] = {}
        self._widgets: dict[str, object] = {}
        self._scan_running = False

        display_name = str(job_display_name(job) or "").strip()
        if display_name in {str(job.name or "").strip(), str(job.job_id or "").strip()} and job.source_root:
            display_name = Path(job.source_root).name.strip() or display_name
        display_name = display_name or str(job.name or job.job_id)
        self._v017_display_name = display_name
        self.title(f"Rediger metadata – {display_name}")
        self.geometry("1120x820")
        self.minsize(860, 620)
        self.resizable(True, True)
        self.configure(fg_color=theme.APP_BG)
        # This is a major work window, not a modal child dialog. Keeping it
        # non-transient gives Windows normal minimize/maximize/close controls.

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self._title = ctk.CTkLabel(
            self,
            text="REDIGER METADATA - ETT UTREKK",
            font=theme.font(theme.TITLE_SIZE, "bold"),
            text_color=theme.BLUE,
            anchor="w",
        )
        self._title.grid(row=0, column=0, padx=22, pady=(18, 3), sticky="ew")

        self._identity = ctk.CTkLabel(
            self,
            text="",
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
            anchor="w",
            justify="left",
        )
        self._identity.grid(row=1, column=0, padx=22, pady=(0, 9), sticky="ew")

        tools = ctk.CTkFrame(self, fg_color="transparent")
        tools.grid(row=2, column=0, padx=22, pady=(0, 9), sticky="ew")
        tools.grid_columnconfigure(5, weight=1)
        self._scan_button = ctk.CTkButton(
            tools,
            text="Finn/importer metadata...",
            width=190,
            command=self._scan,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        )
        self._scan_button.grid(row=0, column=0, padx=(0, 8), sticky="w")
        self._file_button = ctk.CTkButton(
            tools,
            text="Velg info.xml...",
            width=150,
            command=self._choose_info_xml,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        )
        self._file_button.grid(row=0, column=1, padx=(0, 8), sticky="w")
        self._export_button = ctk.CTkButton(
            tools,
            text="Eksporter info.xml...",
            width=165,
            command=self._export_info_xml,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        )
        self._export_button.grid(row=0, column=2, padx=(0, 8), sticky="w")
        self._review_label = ctk.CTkLabel(
            tools,
            text="",
            font=theme.font(theme.SMALL_SIZE, "bold"),
            anchor="w",
        )
        self._review_label.grid(row=0, column=3, padx=(0, 14), sticky="w")
        self._sources_label = ctk.CTkLabel(
            tools,
            text="",
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        self._sources_label.grid(row=0, column=4, sticky="w")

        self._body = ctk.CTkScrollableFrame(self, fg_color=theme.SURFACE_BG)
        self._body.grid(row=3, column=0, padx=22, pady=(0, 10), sticky="nsew")
        self._body.grid_columnconfigure(1, weight=2)
        self._body.grid_columnconfigure(2, weight=2)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=4, column=0, padx=22, pady=(0, 18), sticky="e")
        ctk.CTkButton(
            footer, text="Lukk", width=100, command=self.destroy,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            footer, text="Lagre", width=110, command=self._save,
            fg_color=theme.BLUE_DIM, hover_color=theme.BLUE,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            footer, text="Lagre og marker avklart", width=190,
            command=self._save_and_acknowledge,
            fg_color=theme.BLUE, hover_color=theme.BLUE_DIM,
        ).pack(side="left")

        self._render()
        install_work_window_state(
            self,
            job_window_state_key("metadata", self._v017_display_name),
            max_width_fraction=0.95,
            max_height_fraction=0.94,
        )

    def _render(self) -> None:
        for child in self._body.winfo_children():
            child.destroy()
        self._vars.clear()
        self._widgets.clear()

        payload = load_depot_metadata(self.job)
        current = payload["current"]
        state = metadata_review_state(self.job)
        self._identity.configure(
            text=(
                f"{self.job.job_id} | teknisk navn: {self.job.name or self.job.job_id}\n"
                "Felt 1-47 følger Arkade 5 / DIAS METS. Samme metadata brukes til ytre "
                "submission description (info.xml) og indre dias-mets.xml. Importerte "
                "kilder bevares separat som historisk evidens."
            )
        )
        self._review_label.configure(
            text="⚠ Må avklares" if state["required"] else "✓ Avklart",
            text_color=theme.DANGER_TEXT if state["required"] else theme.TEXT_SUB,
        )
        self._sources_label.configure(text=f"Importerte kilder: {state['source_count']}")

        ctk.CTkLabel(
            self._body, text="Felt", anchor="w",
            font=theme.font(theme.SMALL_SIZE, "bold"), text_color=theme.TEXT_SUB,
        ).grid(row=0, column=0, padx=10, pady=(8, 5), sticky="ew")
        ctk.CTkLabel(
            self._body, text="Gjeldende depotverdi", anchor="w",
            font=theme.font(theme.SMALL_SIZE, "bold"), text_color=theme.TEXT_SUB,
        ).grid(row=0, column=1, padx=10, pady=(8, 5), sticky="ew")
        ctk.CTkLabel(
            self._body, text="Importert kilde / historikk", anchor="w",
            font=theme.font(theme.SMALL_SIZE, "bold"), text_color=theme.TEXT_SUB,
        ).grid(row=0, column=2, padx=10, pady=(8, 5), sticky="ew")

        row = 1
        group = None
        for key, label, field_group in _FIELDS:
            if field_group != group:
                group = field_group
                ctk.CTkLabel(
                    self._body,
                    text=group,
                    anchor="w",
                    font=theme.font(theme.SECTION_SIZE, "bold"),
                    text_color=theme.BLUE,
                ).grid(row=row, column=0, columnspan=3, padx=10, pady=(14, 4), sticky="ew")
                row += 1

            ctk.CTkLabel(
                self._body,
                text=label,
                anchor="w",
                justify="left",
                wraplength=230,
                font=theme.font(theme.SMALL_SIZE),
                text_color=theme.TEXT_MAIN,
            ).grid(row=row, column=0, padx=10, pady=6, sticky="nw")

            value = str(_READ_ONLY_CURRENT.get(key, current.get(key, "")) or "")
            var = ctk.StringVar(value=value)
            self._vars[key] = var
            if key == "delivery_information":
                widget = ctk.CTkTextbox(self._body, height=92, wrap="word", font=theme.font(theme.SMALL_SIZE))
                widget.insert("1.0", value)
            else:
                widget = ctk.CTkEntry(self._body, textvariable=var, font=theme.font(theme.SMALL_SIZE))
                if key in _READ_ONLY_CURRENT:
                    widget.configure(state="disabled")
            widget.grid(row=row, column=1, padx=10, pady=6, sticky="ew")
            self._widgets[key] = widget

            imported = source_values(payload, key)
            source_text = "\n".join(imported) if imported else "-"
            ctk.CTkLabel(
                self._body,
                text=source_text,
                anchor="w",
                justify="left",
                wraplength=360,
                font=theme.font(theme.SMALL_SIZE),
                text_color=theme.TEXT_MUTED,
            ).grid(row=row, column=2, padx=10, pady=6, sticky="nw")
            row += 1

        imports = [item for item in payload.get("source_imports", []) if isinstance(item, dict)]
        if imports:
            ctk.CTkLabel(
                self._body,
                text="Importerte kildeversjoner",
                anchor="w",
                font=theme.font(theme.SECTION_SIZE, "bold"),
                text_color=theme.BLUE,
            ).grid(row=row, column=0, columnspan=3, padx=10, pady=(18, 5), sticky="ew")
            row += 1
            for item in reversed(imports):
                path = str(item.get("path", "") or "")
                stamp = str(item.get("imported_at", "") or "")
                sha = str(item.get("sha256", "") or "")
                evidence_status = str(item.get("evidence_status", "") or "")
                preserved = str(item.get("preserved_file", "") or "")
                manifest = str(item.get("evidence_manifest", "") or "")
                text = f"{stamp} | {path}"
                if sha:
                    text += f"\nSHA-256: {sha}"
                if evidence_status:
                    text += f"\nEvidensstatus: {evidence_status}"
                if preserved:
                    text += f"\nBevart original: {preserved}"
                if manifest:
                    text += f"\nEvidensmanifest: {manifest}"
                ctk.CTkLabel(
                    self._body, text=text, anchor="w", justify="left",
                    wraplength=850, font=theme.font(theme.SMALL_SIZE),
                    text_color=theme.TEXT_MUTED,
                ).grid(row=row, column=0, columnspan=3, padx=10, pady=4, sticky="ew")
                row += 1

    def _values(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for key, _label, _group in _FIELDS:
            widget = self._widgets.get(key)
            if key == "delivery_information" and widget is not None:
                result[key] = widget.get("1.0", "end-1c").strip()
            else:
                result[key] = self._vars[key].get().strip()
        return result

    def _save(self, *, show_message: bool = True) -> bool:
        try:
            update_current_metadata(self.job, self._values())
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Kunne ikke lagre metadata:\n{exc}", parent=self)
            return False
        self._render()
        self._on_saved()
        if show_message:
            messagebox.showinfo(APP_NAME, "Depotmetadata er lagret.", parent=self)
        return True

    def _save_and_acknowledge(self) -> None:
        if not self._save(show_message=False):
            return
        try:
            acknowledge_metadata(self.job)
        except Exception as exc:
            messagebox.showwarning(APP_NAME, str(exc), parent=self)
            self._render()
            return
        self._render()
        self._on_saved()
        messagebox.showinfo(APP_NAME, "Depotmetadata er lagret og markert avklart.", parent=self)


    def _manual_import_initial_dir(self) -> str | None:
        payload = load_depot_metadata(self.job)
        imports = [item for item in payload.get("source_imports", []) if isinstance(item, dict)]
        for item in reversed(imports):
            value = str(item.get("path", "") or "").strip()
            if value:
                parent = Path(value).expanduser().parent
                if parent.is_dir():
                    return str(parent)
        for value in (self.job.source_root, self.job.work_root, self.job.source_extraction):
            if value is None:
                continue
            path = Path(value)
            if path.is_dir():
                return str(path)
            if path.parent.is_dir():
                return str(path.parent)
        return None


    def _export_info_xml(self) -> None:
        if self._scan_running:
            return
        current_label = self._values().get("label", "").strip()
        stem = self.job.job_id
        if current_label:
            safe = "_".join(part for part in current_label.replace("/", " ").replace("\\", " ").split() if part)
            safe = "".join(ch if ch.isalnum() or ch in "-_.()" else "_" for ch in safe).strip("._")
            if safe:
                stem = safe[:120]
        kwargs = {
            "parent": self,
            "title": "Eksporter DIAS info.xml (submission description)",
            "initialfile": f"{stem}_info.xml",
            "defaultextension": ".xml",
            "filetypes": [("XML-filer", "*.xml"), ("Alle filer", "*.*")],
        }
        initial = self._manual_import_initial_dir()
        if initial:
            kwargs["initialdir"] = initial
        filename = filedialog.asksaveasfilename(**kwargs)
        if not filename:
            return
        try:
            path = export_info_xml(self.job, Path(filename), values=self._values())
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Kunne ikke eksportere info.xml:\n{exc}", parent=self)
            return
        messagebox.showinfo(
            APP_NAME,
            "Metadata er eksportert som DIAS package-level METS (info.xml).\n\n"
            "Feltmappingen følger Arkade 5 og submissionDescription.xsd. Denne "
            "metadataeksporten har ikke filinventar/TAR-sjekksum; det legges til "
            "når den endelige DIAS SIP/AIP-pakken bygges.\n\n"
            f"Lagret: {path}",
            parent=self,
        )

    def _choose_info_xml(self) -> None:
        if self._scan_running:
            return
        kwargs = {
            "parent": self,
            "title": "Velg DIAS info.xml / submission description",
            "filetypes": [("XML-filer", "*.xml"), ("Alle filer", "*.*")],
        }
        initial = self._manual_import_initial_dir()
        if initial:
            kwargs["initialdir"] = initial
        filename = filedialog.askopenfilename(**kwargs)
        if not filename:
            return
        try:
            import_selected_info_xml(self.job, Path(filename))
        except Exception as exc:
            messagebox.showerror(
                APP_NAME,
                "Filen kunne ikke importeres som info.xml / DIAS-METS metadata:\n"
                f"{exc}",
                parent=self,
            )
            return
        self._render()
        self._on_saved()
        state = metadata_review_state(self.job)
        messagebox.showinfo(
            APP_NAME,
            "Metadatafil importert.\n\n"
            "Kildeverdiene er bevart som historikk. Eksisterende depotverdier "
            "er ikke overskrevet; tomme depotfelt er fylt fra den valgte kilden.\n\n"
            f"Importerte kilder: {state['source_count']}\n"
            f"Må avklares: {'ja' if state['required'] else 'nei'}",
            parent=self,
        )

    def _scan(self) -> None:
        if self._scan_running:
            return
        self._scan_running = True
        self._scan_button.configure(text="Søker...", state="disabled")
        self._file_button.configure(state="disabled")
        self._export_button.configure(state="disabled")
        self._identity.configure(text=f"{self.job.job_id} | søker etter DIAS/METS metadata i Source/Work ...")

        def worker() -> None:
            result = None
            error = None
            try:
                result = scan_and_import_info_xml(self.job)
            except Exception as exc:
                error = exc
            self.after(0, lambda: self._scan_done(result, error))

        threading.Thread(target=worker, name="dwm-metadata-single", daemon=True).start()

    def _scan_done(self, result, error) -> None:
        self._scan_running = False
        self._scan_button.configure(text="Finn/importer metadata...", state="normal")
        self._file_button.configure(state="normal")
        self._export_button.configure(state="normal")
        self._render()
        self._on_saved()
        if error is not None:
            messagebox.showerror(APP_NAME, f"Metadata-søket feilet:\n{error}", parent=self)
            return
        result = result or {}
        messagebox.showinfo(
            APP_NAME,
            "Metadata-søk ferdig.\n\n"
            f"Funn: {result.get('candidate_count', 0)}\n"
            f"Nye kildeversjoner: {result.get('imported_new', 0)}\n"
            f"Må avklares: {'ja' if result.get('review_required') else 'nei'}",
            parent=self,
        )
