from __future__ import annotations

from pathlib import Path
import json
from tkinter import filedialog, messagebox
import threading

from noark5_workflow.reporting.metadata_templates import load_templates, save_template

import customtkinter as ctk

from noark5_workflow.core.job import Job
from noark5_workflow.reporting.depot_metadata import (
    acknowledge_metadata, export_info_xml, import_selected_info_xml,
    load_depot_metadata, metadata_review_state, scan_and_import_info_xml,
    update_current_metadata, job_display_name, source_values,
)
from noark5_workflow.operations.dias_mets import LEGACY_TO_CANONICAL, read_meta_from_mets
from version import APP_NAME, VERSION
from . import theme
from .work_window_state_v017_a1 import install_work_window_state, job_window_state_key

_FIELDS = (
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
)
# Still persisted in depot_metadata.json for future separate forms; not DIAS metadata fields.
# Keep the canonical labels available for future forms and backwards compatibility.
_DEPOT_ADDITIONAL_FIELDS = (
    ("owner_municipalities", "Eierkommune(r)", "Depotmetadata / tillegg"),
    ("archive_creators", "Arkivskapere / historiske kommuner", "Depotmetadata / tillegg"),
    ("system_region", "IT-/systemregion", "Depotmetadata / tillegg"),
    ("delivery_information", "Informasjon om innleveringen / fritekst", "Depotmetadata / tillegg"),
)
def _system_type_choices() -> list[str]:
    """Suggestions, not an enum: preserve arbitrary imported legacy values."""
    path = Path(__file__).resolve().parents[1] / 'config' / 'noark5' / 'metadata' / 'system_type_values.json'
    try:
        values = json.loads(path.read_text(encoding='utf-8')).get('system_types', [])
        if isinstance(values, list) and all(isinstance(x, str) for x in values) and values:
            return values
    except (OSError, ValueError, TypeError):
        pass
    return ['Noark3', 'Noark4', 'Noark5', 'SpecializedSystem', 'Siard']


_READ_ONLY_CURRENT = {"mets_creator_software": APP_NAME, "mets_creator_software_version": VERSION}


def _source_field(source: dict, key: str) -> str:
    fields = source.get("fields", {})
    if not isinstance(fields, dict):
        return ""
    value = fields.get(key, "")
    if not value:
        for old, new in LEGACY_TO_CANONICAL.items():
            if new == key and fields.get(old):
                value = fields[old]
                break
    return str(value or "").strip()


def _source_choices(imports: list[dict]) -> list[str]:
    choices = []
    for index, item in enumerate(imports):
        path = str(item.get("path", "") or "")
        when = str(item.get("imported_at", "") or "")
        digest = str(item.get("sha256", "") or "")[:10]
        choices.append((f"{index + 1}: Mal: {item.get('name', 'Uten navn')}" if item.get("kind") == "template" else f"{index + 1}: Gjenbruk: {Path(path).name}" if item.get("kind") == "reuse" else f"{index + 1}: Kilde: {Path(path).name or 'Ukjent fil'} | {when} | {digest}"))
    return choices


class DepotMetadataEditor(ctk.CTkToplevel):
    """One-job editor. Source evidence is never changed by field transfers."""

    def __init__(self, master, job: Job, *, on_saved=None) -> None:
        super().__init__(master)
        self.job = job
        self._on_saved = on_saved or (lambda: None)
        self._vars: dict[str, ctk.StringVar] = {}
        self._widgets: dict[str, object] = {}
        self._source_labels: dict[str, ctk.CTkLabel] = {}
        self._source_buttons: dict[str, ctk.CTkButton] = {}
        self._conflicting_source_fields: set[str] = set()
        self._imports: list[dict] = []
        self._selected_source = 0
        self._reuse_source: dict | None = None  # session only; never persisted as evidence
        self._source_menu = None
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
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)
        ctk.CTkLabel(self, text="REDIGER METADATA - ETT UTREKK", font=theme.font(theme.TITLE_SIZE, "bold"),
                     text_color=theme.BLUE, anchor="w").grid(row=0, column=0, padx=22, pady=(18, 3), sticky="ew")
        self._identity = ctk.CTkLabel(self, text="", font=theme.font(theme.SMALL_SIZE),
                                      text_color=theme.TEXT_MUTED, anchor="w", justify="left")
        self._identity.grid(row=1, column=0, padx=22, pady=(0, 9), sticky="ew")
        tools = ctk.CTkFrame(self, fg_color="transparent")
        tools.grid(row=2, column=0, padx=22, pady=(0, 9), sticky="ew")
        tools.grid_columnconfigure(5, weight=1)
        self._scan_button = ctk.CTkButton(tools, text="Finn/importer metadata...", width=190,
                                          command=self._scan, fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER)
        self._scan_button.grid(row=0, column=0, padx=(0, 8), sticky="w")
        self._file_button = ctk.CTkButton(tools, text="Velg info.xml...", width=150,
                                          command=self._choose_info_xml, fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER)
        self._file_button.grid(row=0, column=1, padx=(0, 8), sticky="w")
        self._export_button = ctk.CTkButton(tools, text="Eksporter info.xml...", width=165,
                                            command=self._export_info_xml, fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER)
        self._export_button.grid(row=0, column=2, padx=(0, 8), sticky="w")
        self._review_label = ctk.CTkLabel(tools, text="", font=theme.font(theme.SMALL_SIZE, "bold"), anchor="w")
        self._review_label.grid(row=0, column=3, padx=(0, 14), sticky="w")
        self._sources_label = ctk.CTkLabel(tools, text="", font=theme.font(theme.SMALL_SIZE),
                                            text_color=theme.TEXT_MUTED, anchor="w")
        self._sources_label.grid(row=0, column=4, sticky="w")

        source_tools = ctk.CTkFrame(self, fg_color="transparent")
        source_tools.grid(row=3, column=0, padx=22, pady=(0, 8), sticky="ew")
        ctk.CTkLabel(source_tools, text="Kilde / mal:", font=theme.font(theme.SMALL_SIZE)).pack(side="left", padx=(0, 8))
        self._source_menu = ctk.CTkOptionMenu(source_tools, values=["Ingen importerte kilder"],
                                               width=370, command=self._select_source)
        self._source_menu.pack(side="left", padx=(0, 10))
        self._missing_button = ctk.CTkButton(source_tools, text="Hent manglende verdier", width=175,
                                              command=self._fill_missing, fg_color=theme.BUTTON_BG,
                                              hover_color=theme.BUTTON_HOVER)
        self._missing_button.pack(side="left", padx=(0, 8))
        self._all_button = ctk.CTkButton(source_tools, text="Hent alle verdier", width=145,
                                          command=self._fill_all, fg_color=theme.BUTTON_BG,
                                          hover_color=theme.BUTTON_HOVER)
        self._all_button.pack(side="left", padx=(0, 8))
        self._template_button = ctk.CTkButton(source_tools, text="Lagre som mal...", width=125,
              command=self._save_template, fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER)
        self._template_button.pack(side="left")

        self._body = ctk.CTkScrollableFrame(self, fg_color=theme.SURFACE_BG)
        self._body.grid(row=4, column=0, padx=22, pady=(0, 10), sticky="nsew")
        self._body.grid_columnconfigure(1, weight=2)
        self._body.grid_columnconfigure(3, weight=2)
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=5, column=0, padx=22, pady=(0, 18), sticky="e")
        ctk.CTkButton(footer, text="Lukk", width=100, command=self.destroy,
                      fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER).pack(side="left", padx=(0, 8))
        ctk.CTkButton(footer, text="Lagre", width=110, command=self._save,
                      fg_color=theme.BLUE_DIM, hover_color=theme.BLUE).pack(side="left", padx=(0, 8))
        ctk.CTkButton(footer, text="Lagre og marker avklart", width=190, command=self._save_and_acknowledge,
                      fg_color=theme.BLUE, hover_color=theme.BLUE_DIM).pack(side="left")
        self._render()
        install_work_window_state(self, job_window_state_key("metadata", self._v017_display_name),
                                  max_width_fraction=0.95, max_height_fraction=0.94)

    def _source(self) -> dict | None:
        if 0 <= self._selected_source < len(self._imports):
            return self._imports[self._selected_source]
        return None

    def _select_source(self, choice: str) -> None:
        choices = _source_choices(self._imports)
        if choice not in choices:
            return
        self._selected_source = choices.index(choice)
        self._refresh_source_values()

    def _refresh_source_values(self) -> None:
        source = self._source()
        for key, label in self._source_labels.items():
            value = _source_field(source, key) if source else ""
            note = "\n⚠ Ulike verdier i flere kilder" if key in self._conflicting_source_fields else ""
            label.configure(text=(value or "-") + note)
            self._source_buttons[key].configure(state="normal" if value and key not in _READ_ONLY_CURRENT else "disabled")
        state = "normal" if source else "disabled"
        self._missing_button.configure(state=state)
        self._all_button.configure(state=state)

    def _field_value(self, key: str) -> str:
        widget = self._widgets.get(key)
        return self._vars[key].get().strip()

    def _set_field(self, key: str, value: str) -> None:
        if key in _READ_ONLY_CURRENT:
            return
        self._vars[key].set(value)

    def _copy_field(self, key: str) -> None:
        source = self._source()
        if source is not None:
            value = _source_field(source, key)
            if value and key not in _READ_ONLY_CURRENT:
                self._set_field(key, value)

    def _save_template(self) -> None:
        name = ctk.CTkInputDialog(text="Navn på ny metadatamal:", title="Lagre metadatamal").get_input()
        if not name or not name.strip():
            return
        try:
            save_template(name.strip(), self._values())
        except (ValueError, OSError) as exc:
            messagebox.showerror(APP_NAME, f"Kunne ikke lagre mal:\n{exc}", parent=self)
            return
        self._render()
        messagebox.showinfo(APP_NAME, "Malen er lagret lokalt og er ikke kildeevidens.", parent=self)

    def _review_replacements(self, conflicts: dict[str, tuple[str, str]]) -> set[str] | None:
        """One scrollable, bounded dialog for all differing fields."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Velg metadata som skal erstattes")
        dialog.geometry("980x650")
        dialog.minsize(680, 420)
        dialog.transient(self)
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(dialog, text=f"{len(conflicts)} ulike verdier – velg hvilke som skal erstattes",
                     font=theme.font(theme.SECTION_SIZE, "bold"), anchor="w").grid(
                         row=0, column=0, padx=16, pady=12, sticky="ew")
        scroll = ctk.CTkScrollableFrame(dialog)
        scroll.grid(row=1, column=0, padx=16, pady=5, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        selections = {}
        names = {key: f"{group} / {label}" for key, label, group in _FIELDS}
        for row, (key, (old, new)) in enumerate(conflicts.items()):
            frame = ctk.CTkFrame(scroll)
            frame.grid(row=row, column=0, padx=4, pady=5, sticky="ew")
            frame.grid_columnconfigure(0, weight=1)
            selected = ctk.BooleanVar(value=True)
            selections[key] = selected
            ctk.CTkCheckBox(frame, text=names.get(key, key), variable=selected).grid(
                row=0, column=0, padx=12, pady=(9, 2), sticky="w")
            ctk.CTkLabel(frame, text=f"Gammel: {old}", anchor="w", justify="left",
                wraplength=850).grid(row=1, column=0, padx=12, sticky="w")
            ctk.CTkLabel(frame, text=f"Ny: {new}", anchor="w", justify="left",
                wraplength=850).grid(row=2, column=0, padx=12, pady=(0, 9), sticky="w")
        choice = {"approved": False}
        def approve():
            choice["approved"] = True
            dialog.destroy()
        actions = ctk.CTkFrame(dialog, fg_color="transparent")
        actions.grid(row=2, column=0, padx=16, pady=12, sticky="e")
        ctk.CTkButton(actions, text="Avbryt", command=dialog.destroy).pack(side="left", padx=6)
        ctk.CTkButton(actions, text="Overfør valgte", command=approve).pack(side="left", padx=6)
        dialog.wait_window()
        return {key for key, selected in selections.items() if selected.get()} if choice["approved"] else None

    def _transfer(self, *, overwrite: bool) -> None:
        source = self._source()
        if source is None:
            return
        candidates = {key: value for key, _, _ in _FIELDS if key not in _READ_ONLY_CURRENT
                      if (value := _source_field(source, key)) and (overwrite or not self._field_value(key))}
        if not candidates:
            messagebox.showinfo(APP_NAME, "Ingen verdier å overføre fra valgt kilde/mal.", parent=self)
            return
        conflicts = {key: (self._field_value(key), value) for key, value in candidates.items()
                     if self._field_value(key) and self._field_value(key) != value}
        if conflicts:
            approved = self._review_replacements(conflicts)
            if approved is None:
                return
            candidates = {key: value for key, value in candidates.items() if key not in conflicts or key in approved}
        for key, value in candidates.items():
            self._set_field(key, value)

    def _fill_missing(self) -> None:
        self._transfer(overwrite=False)

    def _fill_all(self) -> None:
        self._transfer(overwrite=True)

    def _render(self) -> None:
        for child in self._body.winfo_children():
            child.destroy()
        self._vars.clear()
        self._widgets.clear()
        self._source_labels.clear()
        self._source_buttons.clear()
        payload = load_depot_metadata(self.job)
        current = payload["current"]
        self._conflicting_source_fields = {
            key for key, _, _ in _FIELDS if len(source_values(payload, key)) > 1
        }
        self._imports = [item for item in payload.get("source_imports", []) if isinstance(item, dict)]
        self._imports.extend(load_templates())
        if self._reuse_source is not None:
            self._imports.append(self._reuse_source)
        choices = _source_choices(self._imports)
        self._selected_source = min(self._selected_source, max(0, len(choices) - 1))
        self._source_menu.configure(values=choices or ["Ingen importerte kilder"])
        self._source_menu.set(choices[self._selected_source] if choices else "Ingen importerte kilder")
        state = metadata_review_state(self.job)
        self._identity.configure(text=(
            f"{self.job.job_id} | teknisk navn: {self.job.name or self.job.job_id}\n"
            "Felt 1-47 følger Arkade 5 / DIAS METS. Samme metadata brukes til ytre "
            "submission description (info.xml) og indre dias-mets.xml. Importerte "
            "kilder bevares separat som historisk evidens."
        ))
        self._review_label.configure(text="⚠ Må avklares" if state["required"] else "✓ Avklart",
                                     text_color=theme.DANGER_TEXT if state["required"] else theme.TEXT_SUB)
        self._sources_label.configure(text=f"Importerte kilder: {state['source_count']}")
        for column, title in ((0, "Felt"), (1, "Gjeldende depotverdi"), (3, "Valgt kilde / mal")):
            ctk.CTkLabel(self._body, text=title, anchor="w", font=theme.font(theme.SMALL_SIZE, "bold"),
                         text_color=theme.TEXT_SUB).grid(row=0, column=column, padx=10, pady=(8, 5), sticky="ew")
        row = 1
        group = None
        for key, label, field_group in _FIELDS:
            if field_group != group:
                group = field_group
                ctk.CTkLabel(self._body, text=group, anchor="w", font=theme.font(theme.SECTION_SIZE, "bold"),
                             text_color=theme.BLUE).grid(row=row, column=0, columnspan=4, padx=10, pady=(14, 4), sticky="ew")
                row += 1
            ctk.CTkLabel(self._body, text=label, anchor="w", justify="left", wraplength=230,
                         font=theme.font(theme.SMALL_SIZE), text_color=theme.TEXT_MAIN).grid(
                             row=row, column=0, padx=10, pady=6, sticky="nw")
            value = str(_READ_ONLY_CURRENT.get(key, current.get(key, "")) or "")
            var = ctk.StringVar(value=value)
            self._vars[key] = var
            widget = (ctk.CTkComboBox(self._body, variable=var, values=_system_type_choices(),
                                          state='normal', font=theme.font(theme.SMALL_SIZE))
                          if key in ('system_type', 'extraction_system_type')
                          else ctk.CTkEntry(self._body, textvariable=var,
                                            font=theme.font(theme.SMALL_SIZE)))
            if key in _READ_ONLY_CURRENT:
                widget.configure(state="disabled")
            widget.grid(row=row, column=1, padx=10, pady=6, sticky="ew")
            self._widgets[key] = widget
            transfer = ctk.CTkButton(self._body, text="←", width=34,
                                      command=lambda name=key: self._copy_field(name),
                                      fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER)
            transfer.grid(row=row, column=2, padx=(0, 2), pady=6, sticky="nw")
            self._source_buttons[key] = transfer
            source_label = ctk.CTkLabel(self._body, text="-", anchor="w", justify="left", wraplength=340,
                                         font=theme.font(theme.SMALL_SIZE), text_color=theme.TEXT_MUTED)
            source_label.grid(row=row, column=3, padx=10, pady=6, sticky="nw")
            self._source_labels[key] = source_label
            row += 1
        if payload.get("source_imports"):
            ctk.CTkLabel(self._body, text="Importerte kildeversjoner", anchor="w",
                         font=theme.font(theme.SECTION_SIZE, "bold"), text_color=theme.BLUE).grid(
                             row=row, column=0, columnspan=4, padx=10, pady=(18, 5), sticky="ew")
            row += 1
            for item in reversed(payload.get("source_imports", [])):
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
                ctk.CTkLabel(self._body, text=text, anchor="w", justify="left", wraplength=850,
                             font=theme.font(theme.SMALL_SIZE), text_color=theme.TEXT_MUTED).grid(
                                 row=row, column=0, columnspan=4, padx=10, pady=4, sticky="ew")
                row += 1
        self._refresh_source_values()

    def _values(self) -> dict[str, str]:
        return {key: self._field_value(key) for key, _, _ in _FIELDS}

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
        kwargs = {"parent": self, "title": "Eksporter DIAS info.xml (submission description)",
                  "initialfile": f"{stem}_info.xml", "defaultextension": ".xml",
                  "filetypes": [("XML-filer", "*.xml"), ("Alle filer", "*.*")]}
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
        messagebox.showinfo(APP_NAME,
                            "Metadata er eksportert som DIAS package-level METS (info.xml).\n\n"
                            "Feltmappingen følger Arkade 5 og submissionDescription.xsd. Denne "
                            "metadataeksporten har ikke filinventar/TAR-sjekksum; det legges til "
                            "når den endelige DIAS SIP/AIP-pakken bygges.\n\n"
                            f"Lagret: {path}", parent=self)

    def _choose_import_mode(self) -> str | None:
        """Explicit mode selection prevents accidental evidence registration."""
        choice: dict[str, str | None] = {"value": None}
        dialog = ctk.CTkToplevel(self)
        dialog.title("Hvordan skal metadata brukes?")
        dialog.geometry("570x220")
        dialog.minsize(540, 210)
        dialog.transient(self)
        dialog.grab_set()
        ctk.CTkLabel(
            dialog, text="Velg hvordan info.xml skal importeres:",
            font=theme.font(theme.SECTION_SIZE, "bold"), anchor="w",
        ).pack(fill="x", padx=20, pady=(19, 9))
        ctk.CTkLabel(
            dialog,
            text="Evidens: Bevarer filen og registrerer den på denne jobben.\n"
                 "Gjenbruk: Leser kun feltverdier, uten evidens eller kildehistorikk.",
            justify="left", anchor="w", wraplength=510,
        ).pack(fill="x", padx=20, pady=(0, 15))
        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(fill="x", padx=20, pady=(0, 15))
        def select(mode: str | None) -> None:
            choice["value"] = mode
            dialog.destroy()
        ctk.CTkButton(buttons, text="Importer som evidens", width=165,
                      command=lambda: select("evidence")).pack(side="left", padx=(0, 7))
        ctk.CTkButton(buttons, text="Importer for gjenbruk", width=165,
                      command=lambda: select("reuse")).pack(side="left", padx=(0, 7))
        ctk.CTkButton(buttons, text="Avbryt", width=90,
                      command=lambda: select(None)).pack(side="right")
        dialog.protocol("WM_DELETE_WINDOW", lambda: select(None))
        dialog.wait_window()
        return choice["value"]

    def _choose_info_xml(self) -> None:
        if self._scan_running:
            return
        mode = self._choose_import_mode()
        if mode is None:
            return
        kwargs = {"parent": self, "title": "Velg DIAS info.xml / submission description",
                  "filetypes": [("XML-filer", "*.xml"), ("Alle filer", "*.*")]}
        initial = self._manual_import_initial_dir()
        if initial:
            kwargs["initialdir"] = initial
        filename = filedialog.askopenfilename(**kwargs)
        if not filename:
            return
        if mode == "reuse":
            try:
                fields = read_meta_from_mets(Path(filename))
                if not fields or not any(str(value or "").strip() for value in fields.values()):
                    raise ValueError("Ingen lesbare DIAS/METS-metadatafelt i filen.")
            except Exception as exc:
                messagebox.showerror(APP_NAME, f"Kunne ikke lese metadata for gjenbruk:\n{exc}", parent=self)
                return
            # Never call import_info_xml/import_selected_info_xml here: they write evidence.
            self._reuse_source = {"kind": "reuse", "path": str(Path(filename)), "fields": fields}
            self._render()
            self._selected_source = len(self._imports) - 1
            self._source_menu.set(_source_choices(self._imports)[self._selected_source])
            self._refresh_source_values()
            messagebox.showinfo(APP_NAME,
                "Metadata er lest for gjenbruk, uten å registrere evidens.\n\n"
                "Bruk pilene eller 'Hent manglende verdier' / 'Hent alle verdier'. "
                "Overførte depotverdier lagres først med Lagre.\n\n"
                "Du kan også velge Lagre som mal for senere bruk.", parent=self)
            return
        try:
            import_selected_info_xml(self.job, Path(filename))
        except Exception as exc:
            messagebox.showerror(APP_NAME,
                                 "Filen kunne ikke importeres som info.xml / DIAS-METS metadata:\n"
                                 f"{exc}", parent=self)
            return
        self._render()
        self._on_saved()
        state = metadata_review_state(self.job)
        messagebox.showinfo(APP_NAME,
                            "Metadatafil importert.\n\n"
                            "Kildeverdiene er bevart som historikk. Eksisterende depotverdier "
                            "er ikke overskrevet; tomme depotfelt er fylt fra den valgte kilden.\n\n"
                            f"Importerte kilder: {state['source_count']}\n"
                            f"Må avklares: {'ja' if state['required'] else 'nei'}", parent=self)

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
        messagebox.showinfo(APP_NAME,
                            "Metadata-søk ferdig.\n\n"
                            f"Funn: {result.get('candidate_count', 0)}\n"
                            f"Nye kildeversjoner: {result.get('imported_new', 0)}\n"
                            f"Må avklares: {'ja' if result.get('review_required') else 'nei'}", parent=self)
