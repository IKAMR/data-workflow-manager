"""Standalone depot Mottak / Ingest dialog, independent of an active DWM job."""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.receiving_folders import (
    ReceiveProfile, adjusted_label_folder, create_receiving_folders, load_profiles,
    plan_receiving_folders, read_info_xml, resolve_receiving_base,
    safe_suggestion, suggested_folder_name, suggested_receipt_number,
)
from app.identity_provider import LocalUserProfileIdentityProvider
from settings import load_config, save_config
from . import theme

_DEFAULT_SETUP = Path(__file__).resolve().parents[1] / 'config' / 'receiving_folder_profiles.json'


class ReceivingFolderDialog(ctk.CTkToplevel):
    """Shows full target before any disk modifications; no job needed."""

    def __init__(self, parent):
        super().__init__(parent)
        cfg = load_config()
        self.title('Mottak / Ingest')
        self.geometry('1000x810')
        self.minsize(780, 600)
        self.transient(parent)
        self.grab_set()
        self._profiles: dict[str, ReceiveProfile] = {}
        self._metadata: dict[str, str] = {}
        self._plan = None

        remembered = Path(str(cfg.get('last_receiving_root', '') or ''))
        valid_root = remembered if str(remembered) != '.' and remembered.is_dir() else None
        disk = str(Path(valid_root.anchor)) if valid_root else ''
        relative = str(valid_root.relative_to(Path(valid_root.anchor))) if valid_root else ''
        if relative == '.':
            relative = ''

        self.disk_var = ctk.StringVar(value=disk)
        self.root_rel_var = ctk.StringVar(value=relative)
        self.setup_var = ctk.StringVar(value=cfg.get('receiving_setup_file', '') or str(_DEFAULT_SETUP))
        self.xml_var = ctk.StringVar(value='')  # A new receipt never reuses the prior source silently.
        self.label_var = ctk.StringVar(value='')
        self.folder_var = ctk.StringVar(value='')
        self.receipt_var = ctk.StringVar(value='')
        self.profile_var = ctk.StringVar(value='')
        for var in (self.disk_var, self.root_rel_var, self.setup_var, self.xml_var,
                    self.receipt_var, self.profile_var):
            var.trace_add('write', lambda *_: self._invalidate_preview())
        self.label_var.trace_add('write', self._label_changed)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(self, text='MOTTAK / INGEST',
                     font=theme.font(theme.TITLE_SIZE, 'bold')).grid(
            row=0, column=0, padx=20, pady=(16, 6), sticky='w')
        body = ctk.CTkScrollableFrame(self)
        body.grid(row=1, column=0, padx=14, pady=7, sticky='nsew')
        body.grid_columnconfigure(0, weight=1)
        row = 0

        def entry_with_actions(label, variable, actions=()):
            nonlocal row
            ctk.CTkLabel(body, text=label, anchor='w').grid(
                row=row, column=0, sticky='ew', padx=10, pady=(10, 2))
            row += 1
            frame = ctk.CTkFrame(body, fg_color='transparent')
            frame.grid(row=row, column=0, sticky='ew', padx=10)
            frame.grid_columnconfigure(0, weight=1)
            entry = ctk.CTkEntry(frame, textvariable=variable)
            entry.grid(row=0, column=0, sticky='ew')
            for i, (title, cmd) in enumerate(actions, start=1):
                ctk.CTkButton(frame, text=title, width=90, command=cmd).grid(
                    row=0, column=i, padx=(8, 0))
            row += 1
            return entry

        # User-requested order 1-5: metadata, LABEL, receipt number, disk, root.
        entry_with_actions('1. info.xml (valgfritt)', self.xml_var,
                           (('Velg ...', self._pick_xml), ('Tøm', self._clear_xml)))
        self.source_label = ctk.CTkLabel(body, text='Ingen info.xml er valgt.',
                                         anchor='w', justify='left', wraplength=850,
                                         text_color=theme.TEXT_MUTED)
        self.source_label.grid(row=row, column=0, sticky='ew', padx=10, pady=(3, 4))
        row += 1
        entry_with_actions('2. LABEL (må ha verdi)', self.label_var,
                           (('Fra info.xml', self._suggest_label),))
        ctk.CTkLabel(body, text='LABEL beholdes som metadata. Mappenavnet justeres kun for Windows.',
                     anchor='w', text_color=theme.TEXT_MUTED).grid(
            row=row, column=0, padx=10, pady=(2, 4), sticky='w')
        row += 1
        entry_with_actions('3. Mottaksnr (foreslås automatisk, kan endres)', self.receipt_var,
                           (('Nytt forslag', self._suggest_number),))
        entry_with_actions('4. Disk / volum', self.disk_var,
                           (('Velg disk', self._pick_disk),))
        entry_with_actions('5. Mottaksrot på valgt disk (eksisterende mappe, kan være tom)',
                           self.root_rel_var, (('Velg rot', self._pick_root),))
        folder_entry = entry_with_actions('Mappenavn fra justert LABEL (kun visning)', self.folder_var)
        folder_entry.configure(state='disabled')

        entry_with_actions('Ekstern depot-setup (JSON)', self.setup_var,
                           (('Velg setup', self._pick_setup), ('Les setup', self._load_profiles)))
        ctk.CTkLabel(body, text='Mappeprofil', anchor='w').grid(
            row=row, column=0, sticky='w', padx=10, pady=(10, 2))
        row += 1
        self.profile_menu = ctk.CTkOptionMenu(body, variable=self.profile_var,
                                               values=['Les setup for profiler'],
                                               command=lambda _: self._profile_changed())
        self.profile_menu.grid(row=row, column=0, sticky='ew', padx=10)
        row += 1
        ctk.CTkLabel(body, text='6. Forhåndsvisning av standardstruktur', anchor='w').grid(
            row=row, column=0, sticky='w', padx=10, pady=(12, 2))
        row += 1
        self.preview = ctk.CTkTextbox(body, height=220, font=('Consolas', 12), wrap='none')
        self.preview.grid(row=row, column=0, sticky='nsew', padx=10, pady=(0, 9))
        self.preview.configure(state='disabled')
        row += 1
        self.message_label = ctk.CTkLabel(body,
            text='Mottak opprettes bare etter bekreftelse. Eksisterende mapper røres ikke.',
            anchor='w', text_color=theme.TEXT_MUTED)
        self.message_label.grid(row=row, column=0, sticky='ew', padx=10)

        footer = ctk.CTkFrame(self, fg_color='transparent')
        footer.grid(row=2, column=0, sticky='ew', padx=20, pady=(9, 16))
        ctk.CTkButton(footer, text='Vis mappestruktur', command=self._preview,
                      width=160).pack(side='left')
        ctk.CTkButton(footer, text='Opprett standardstruktur', command=self._create,
                      width=210).pack(side='left', padx=10)
        ctk.CTkButton(footer, text='Lukk', command=self.destroy,
                      fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER).pack(side='right')
        self._load_profiles()

    def _set_preview(self, value):
        self.preview.configure(state='normal')
        self.preview.delete('1.0', 'end')
        self.preview.insert('1.0', value)
        self.preview.configure(state='disabled')

    def _invalidate_preview(self):
        self._plan = None
        if hasattr(self, 'preview'):
            self._set_preview('Trykk «Vis mappestruktur» for oppdatert forhåndsvisning.')

    def _label_changed(self, *_):
        self.folder_var.set(safe_suggestion(self.label_var.get()))
        self._invalidate_preview()

    def _pick_disk(self):
        selected = filedialog.askdirectory(parent=self, title='Velg disk eller mappe på mottaksdisken', mustexist=True)
        if selected:
            path = Path(selected)
            self.disk_var.set(path.anchor)
            relative = path.relative_to(Path(path.anchor))
            self.root_rel_var.set('' if str(relative) == '.' else str(relative))

    def _pick_root(self):
        selected = filedialog.askdirectory(parent=self, title='Velg eksisterende mottaksrot', mustexist=True)
        if selected:
            path = Path(selected)
            self.disk_var.set(path.anchor)
            relative = path.relative_to(Path(path.anchor))
            self.root_rel_var.set('' if str(relative) == '.' else str(relative))

    def _pick_setup(self):
        selected = filedialog.askopenfilename(parent=self, title='Velg depotets mottaks-setup',
            filetypes=[('JSON setup', '*.json'), ('Alle filer', '*.*')])
        if selected:
            self.setup_var.set(selected)
            self._load_profiles()

    def _pick_xml(self):
        selected = filedialog.askopenfilename(parent=self, title='Velg info.xml',
            filetypes=[('METS XML', '*.xml'), ('Alle filer', '*.*')])
        if selected:
            self.xml_var.set(selected)
            self._load_info(show_error=True)

    def _clear_xml(self):
        self.xml_var.set('')
        self._metadata = {}
        self.source_label.configure(text='Ingen info.xml er valgt.')

    def _load_profiles(self):
        try:
            profiles = load_profiles(self.setup_var.get().strip())
            self._profiles = {profile.name: profile for profile in profiles}
            old = self.profile_var.get()
            self.profile_menu.configure(values=list(self._profiles))
            self.profile_var.set(old if old in self._profiles else profiles[0].name)
            self._profile_changed()
            save_config({'receiving_setup_file': self.setup_var.get().strip()})
        except (OSError, ValueError) as exc:
            self._profiles = {}
            self.profile_menu.configure(values=['Ugyldig setup'])
            self.profile_var.set('Ugyldig setup')
            self.message_label.configure(text=str(exc))

    def _selected_profile(self):
        value = self._profiles.get(self.profile_var.get())
        if value is None:
            raise ValueError('Velg gyldig mappeprofil')
        return value

    def _profile_changed(self):
        if not self.receipt_var.get().strip():
            self._suggest_number()
        self._invalidate_preview()

    def _suggest_number(self):
        try:
            self.receipt_var.set(suggested_receipt_number(self._selected_profile()))
        except ValueError as exc:
            self.message_label.configure(text=str(exc))

    def _load_info(self, *, show_error):
        try:
            data = read_info_xml(self.xml_var.get().strip())
            self._metadata = data
            values = [f'{key}: {data[key]}' for key in
                      ('label', 'system', 'reference_code', 'period_start', 'period_end') if data.get(key)]
            self.source_label.configure(text=' | '.join(values) or 'Fant ikke LABEL i info.xml.')
            if not self.label_var.get().strip():
                self._suggest_label()
            return True
        except (OSError, ValueError) as exc:
            self._metadata = {}
            self.source_label.configure(text=f'Kunne ikke lese info.xml: {exc}')
            if show_error:
                messagebox.showerror('info.xml', str(exc), parent=self)
            return False

    def _suggest_label(self):
        label = self._metadata.get('label', '').strip()
        if not label:
            self.message_label.configure(text='Ingen LABEL i valgt info.xml. Skriv LABEL manuelt.')
        else:
            self.label_var.set(label)

    def _preview(self):
        try:
            profile = self._selected_profile()
            if self.xml_var.get().strip() and not self._load_info(show_error=False):
                raise ValueError('info.xml kunne ikke leses; velg en gyldig fil eller tøm feltet')
            label = self.label_var.get().strip()
            adjusted_label_folder(label)  # mandatory, even if profile uses another template
            base = resolve_receiving_base(self.disk_var.get().strip(), self.root_rel_var.get().strip())
            metadata = dict(self._metadata)
            metadata['label'] = label
            name = suggested_folder_name(profile, metadata)
            self._plan = plan_receiving_folders(
                base, name, profile, metadata,
                label=label, receipt_number=self.receipt_var.get().strip(),
                info_xml=self.xml_var.get().strip() or None,
            )
            if not self._plan.receipt_number:
                raise ValueError('Mottaksnr må ha en verdi')
            listing = [f'Mottaksnr: {self._plan.receipt_number}',
                       f'LABEL: {label}', f'Mottaksmappe: {self._plan.root}', '']
            for folder in self._plan.paths:
                rel = folder.relative_to(self._plan.root)
                listing.append('  ' * len(rel.parts) + (rel.name + '/' if rel.parts else './'))
            listing += ['', f'Hendelseslogg: {self._plan.audit_path.relative_to(self._plan.root)}']
            self._set_preview('\n'.join(listing))
            self.message_label.configure(text=f'{len(self._plan.paths)} mapper planlagt. Ingen er opprettet.')
            return self._plan
        except (OSError, ValueError) as exc:
            self._plan = None
            self._set_preview(f'Kan ikke vise mappestruktur: {exc}')
            return None

    def _create(self):
        plan = self._preview()
        if plan is None:
            return
        if not messagebox.askyesno('Bekreft mottak / Ingest',
            f'Mottaksnr: {plan.receipt_number}\nLABEL: {plan.label}\n\n'
            f'Opprett {len(plan.paths)} mapper under:\n{plan.root}\n\n'
            'Ingen eksisterende mapper endres. Ingen filer kopieres eller flyttes.', parent=self):
            return
        try:
            identity = LocalUserProfileIdentityProvider().current_identity()
            created = create_receiving_folders(plan, actor=identity)
        except Exception as exc:
            messagebox.showerror('Mottak / Ingest', str(exc), parent=self)
            return
        try:
            save_config({'last_receiving_root': str(plan.base),
                         'receiving_setup_file': self.setup_var.get().strip()})
        except OSError:
            # The ingest and its audit record already succeeded; never report it as undone.
            pass
        self._plan = None
        self.message_label.configure(text=f'Mottak opprettet og hendelse logget: {plan.root}')
        messagebox.showinfo('Mottak opprettet',
            f'{len(created)} mapper opprettet.\n\n{plan.root}\n\nHendelseslogg:\n{plan.audit_path}', parent=self)


def open_receiving_folder_dialog(parent):
    return ReceivingFolderDialog(parent)

# a19-fix2: grouped IKAMR receiving is the primary Ingest dialog.
# The a19 folder-only dialog remains for backwards compatibility and tests.
def open_receiving_folder_dialog(parent):
    # Preserve use of third-party/legacy receiving profiles without grouped_ingest.
    from app.grouped_ingest import grouped_profiles
    from .grouped_ingest_dialog import GroupedIngestDialog
    cfg = load_config()
    setup_path = cfg.get('receiving_setup_file', '') or str(_DEFAULT_SETUP)
    try:
        if not grouped_profiles(setup_path):
            return ReceivingFolderDialog(parent)
    except (OSError, ValueError):
        # The grouped dialog shows configuration errors and lets the operator
        # select a valid setup rather than falling back to an unsafe default.
        pass
    return GroupedIngestDialog(parent)
