"""Two separate IKAMR ingest actions; all site-specific paths from JSON setup."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.grouped_ingest import (
    RECEIPT, create_grouped_ingest, grouped_profiles, plan_extraction,
    plan_receipt, suggest_receipt_number,
)
from app.receiving_folders import read_info_xml
from app.ingest_saved_profiles import load_ingest_profile, save_ingest_profile
from app.identity_provider import LocalUserProfileIdentityProvider
from settings import load_config, save_config
from . import theme

DEFAULT_SETUP = Path(__file__).resolve().parents[1] / 'config' / 'receiving_folder_profiles.json'


class GroupedIngestDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title('Mottak / Ingest – mottak og uttrekk')
        self.geometry('1030x855')
        self.minsize(800, 650)
        self.transient(parent)
        self.grab_set()
        cfg = load_config()
        self._profiles = {}
        self._metadata = {}
        self._plan = None
        self._saved_profile_path = None
        self._last_user_profile = str(cfg.get('last_ingest_user_profile_file', '') or '')
        self.mode = ctk.StringVar(value='Mottak')
        self.setup_var = ctk.StringVar(value=str(cfg.get('receiving_setup_file') or DEFAULT_SETUP))
        self.profile_var = ctk.StringVar(value='')
        self.xml_var = ctk.StringVar(value='')
        self.label_var = ctk.StringVar(value='')
        self.owner_var = ctk.StringVar(value='')
        self.receipt_var = ctk.StringVar(value='')
        self.disk_var = ctk.StringVar(value=str(cfg.get('last_ingest_disk', '') or ''))
        self.group_var = ctk.StringVar(value=str(cfg.get('last_ingest_group', '') or ''))
        self.extraction_var = ctk.StringVar(value='')
        self.date_var = ctk.StringVar(value=date.today().isoformat())
        for v in (self.mode, self.setup_var, self.profile_var, self.xml_var, self.label_var,
                  self.owner_var, self.receipt_var, self.disk_var, self.group_var,
                  self.extraction_var, self.date_var):
            v.trace_add('write', lambda *_: self._invalidate())

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(self, text='MOTTAK / INGEST', font=theme.font(theme.TITLE_SIZE, 'bold')).grid(
            row=0, column=0, padx=20, pady=(15, 5), sticky='w')
        main = ctk.CTkScrollableFrame(self)
        main.grid(row=1, column=0, padx=14, pady=6, sticky='nsew')
        main.grid_columnconfigure(0, weight=1)
        row = 0

        def entry(name, variable, buttons=()):
            nonlocal row
            ctk.CTkLabel(main, text=name, anchor='w').grid(row=row, column=0, padx=10,
                                                              pady=(8, 2), sticky='w')
            row += 1
            line = ctk.CTkFrame(main, fg_color='transparent')
            line.grid(row=row, column=0, sticky='ew', padx=10)
            line.grid_columnconfigure(0, weight=1)
            ctk.CTkEntry(line, textvariable=variable).grid(row=0, column=0, sticky='ew')
            for i, (text, command) in enumerate(buttons, 1):
                ctk.CTkButton(line, text=text, command=command, width=100).grid(
                    row=0, column=i, padx=(7, 0))
            row += 1

        ctk.CTkLabel(main, text='Handling').grid(row=row, column=0, padx=10, sticky='w')
        row += 1
        ctk.CTkSegmentedButton(main, variable=self.mode,
             values=['Mottak', 'Uttrekk'], command=lambda _: self._mode_changed(),
             width=480).grid(row=row, column=0, padx=10, sticky='w')
        row += 1
        self.mode_hint = ctk.CTkLabel(main, text='', text_color=theme.TEXT_MUTED,
                                      anchor='w', wraplength=920)
        self.mode_hint.grid(row=row, column=0, padx=10, sticky='ew')
        row += 1
        entry('1. info.xml (valgfritt)', self.xml_var,
              [('Velg ...', self._pick_xml), ('Tøm', self._clear_xml)])
        entry('2. LABEL (påkrevd; beholdes uendret som metadata)', self.label_var,
              [('Fra info.xml', self._apply_xml_label)])
        entry('3. Eierkommune – FFKK (gjeldende eier, ikke historisk arkivskaper)', self.owner_var)
        entry('4. Mottaksnummer E-FFKK-YYYY-nnnn (påkrevd, kan redigeres)', self.receipt_var,
              [('Neste forslag', self._suggest_number), ('Velg mottak', self._pick_receipt)])
        entry('5. Disk / volum', self.disk_var, [('Velg disk', self._pick_disk)])
        entry('6. Gruppemappe arkiv-karantene-nn (eksisterende)', self.group_var,
              [('Velg gruppe', self._pick_group)])
        entry('7. Uttrekks-ID FFKK_nnn (kun ved Uttrekk)', self.extraction_var,
              [('Fra LABEL', self._apply_label_id)])
        entry('8. Dato for uttrekksmappe YYYY-MM-DD (kun ved Uttrekk)', self.date_var)
        entry('Ekstern depot-setup (JSON)', self.setup_var,
              [('Velg setup', self._pick_setup), ('Last inn', self._load_setup)])
        ctk.CTkLabel(main, text='Mappeprofil').grid(row=row, column=0, padx=10, pady=(8, 2), sticky='w')
        row += 1
        self.profiles_menu = ctk.CTkOptionMenu(main, variable=self.profile_var, values=['Les setup'])
        self.profiles_menu.grid(row=row, column=0, padx=10, sticky='ew')
        row += 1
        # A saved user preset contains disk/group/owner/setup/profile choices.
        # It never stores a receipt number or a previously delivered LABEL.
        saved_buttons = ctk.CTkFrame(main, fg_color='transparent')
        saved_buttons.grid(row=row, column=0, padx=10, pady=(10, 2), sticky='w')
        for caption, command in (
            ('Åpne profil', self._open_saved_profile),
            ('Lagre profil', self._save_saved_profile),
            ('Lagre som ny profil', self._save_as_new_profile),
        ):
            ctk.CTkButton(saved_buttons, text=caption, command=command, width=150).pack(
                side='left', padx=(0, 8))
        row += 1
        self.profile_status = ctk.CTkLabel(main, text='Brukerprofil: Ingen lagret profil åpnet',
                                            anchor='w', text_color=theme.TEXT_MUTED)
        self.profile_status.grid(row=row, column=0, padx=10, sticky='ew')
        row += 1
        ctk.CTkLabel(main, text='Forhåndsvisning – ingen mapper opprettes før bekreftelse').grid(
            row=row, column=0, padx=10, pady=(10, 2), sticky='w')
        row += 1
        self.preview = ctk.CTkTextbox(main, height=180, font=('Consolas', 12), wrap='none')
        self.preview.grid(row=row, column=0, padx=10, sticky='ew', pady=(0, 7))
        self.preview.configure(state='disabled')
        row += 1
        self.message = ctk.CTkLabel(main, text='', anchor='w', text_color=theme.TEXT_MUTED,
                                     wraplength=920)
        self.message.grid(row=row, column=0, padx=10, sticky='ew', pady=5)

        bottom = ctk.CTkFrame(self, fg_color='transparent')
        bottom.grid(row=2, column=0, padx=20, pady=(9, 14), sticky='ew')
        ctk.CTkButton(bottom, text='Vis mappestruktur', width=170,
                      command=self._preview).pack(side='left')
        self.create_button = ctk.CTkButton(bottom, text='Opprett mottaksmappe', width=210,
                                          command=self._create)
        self.create_button.pack(side='left', padx=8)
        ctk.CTkButton(bottom, text='Lukk', command=self.destroy,
                      fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER).pack(side='right')
        self.owner_var.trace_add('write', lambda *_: self._auto_number_if_blank())
        self.disk_var.trace_add('write', lambda *_: self._auto_number_if_blank())
        self._load_setup()
        self._mode_changed()
        self._auto_number_if_blank()
        if self._last_user_profile and Path(self._last_user_profile).is_file():
            try:
                self._apply_saved_profile(self._last_user_profile)
            except (OSError, ValueError):
                # Do not prevent ingest when a previously used preset is missing.
                self.profile_status.configure(text='Tidligere profil kan ikke lastes. Velg Åpne profil.')

    def _put_preview(self, s):
        self.preview.configure(state='normal')
        self.preview.delete('1.0', 'end')
        self.preview.insert('1.0', s)
        self.preview.configure(state='disabled')

    def _invalidate(self):
        self._plan = None
        if hasattr(self, 'preview'):
            self._put_preview('Trykk «Vis mappestruktur» for oppdatert kontroll.')

    def _mode_changed(self):
        self.create_button.configure(text='Opprett mottaksmappe' if self.mode.get() == 'Mottak'
                                     else 'Opprett uttrekksmappe')
        self.mode_hint.configure(text=(
            'Mottaksmappe: Én E-FFKK-YYYY-nnnn-mappe for kryptert(e) leveranse(r). '
            'LABEL brukes til registrering, ikke som mappenavn.' if self.mode.get() == 'Mottak' else
            'Uttrekksmappe: opprettes ved siden av mottaksmappen i samme karantenegruppe. '
            'Flere uttrekk kan bruke samme mottaksnummer.'))
        self._invalidate()

    def _pick_xml(self):
        p = filedialog.askopenfilename(parent=self, title='Velg info.xml',
                                       filetypes=[('XML', '*.xml'), ('Alle filer', '*.*')])
        if p:
            self.xml_var.set(p)
            try:
                self._metadata = read_info_xml(p)
                self._apply_xml_label(quiet=True)
                self._apply_label_id(quiet=True)
            except (OSError, ValueError) as exc:
                self.message.configure(text=f'info.xml kunne ikke leses: {exc}')

    def _clear_xml(self):
        self.xml_var.set('')
        self._metadata = {}

    def _apply_xml_label(self, quiet=False):
        value = self._metadata.get('label', '').strip()
        if value:
            self.label_var.set(value)
        elif not quiet:
            self.message.configure(text='Ingen LABEL funnet i info.xml. Skriv den manuelt.')

    def _apply_label_id(self, quiet=False):
        match = re.match(r'^(\d{4}_\d{3,})\b', self.label_var.get().strip())
        if match:
            self.extraction_var.set(match.group(1))
        elif not quiet:
            self.message.configure(text='Fant ikke FFKK_nnn i LABEL. Oppgi uttrekks-ID manuelt.')

    def _pick_disk(self):
        p = filedialog.askdirectory(parent=self, title='Velg karantenedisk', mustexist=True)
        if p:
            self.disk_var.set(p)

    def _pick_group(self):
        p = filedialog.askdirectory(parent=self, title='Velg arkiv-karantene-nn', mustexist=True)
        if p:
            path = Path(p)
            self.disk_var.set(str(path.parent))
            self.group_var.set(path.name)

    def _pick_receipt(self):
        p = filedialog.askdirectory(parent=self, title='Velg eksisterende E-FFKK-YYYY-nnnn-mappe',
                                    mustexist=True)
        if p:
            path = Path(p)
            m = RECEIPT.fullmatch(path.name.upper())
            if m is None:
                self.message.configure(text='Velg mottaksmappe E-FFKK-YYYY-nnnn.')
                return
            self.disk_var.set(str(path.parent.parent))
            self.group_var.set(path.parent.name)
            self.receipt_var.set(path.name)
            self.owner_var.set(m.group(1))
            self.mode.set('Uttrekk')
            self._mode_changed()

    def _auto_number_if_blank(self):
        if self.receipt_var.get().strip() or not re.fullmatch(r'\d{4}', self.owner_var.get().strip()):
            return
        try:
            disk = Path(self.disk_var.get().strip())
            if disk.is_dir() and self.profile_var.get() in self._profiles:
                self.receipt_var.set(suggest_receipt_number(disk, self._profiles[self.profile_var.get()],
                                                            self.owner_var.get().strip()))
        except (OSError, ValueError):
            return

    def _suggest_number(self):
        try:
            profile = self._profiles[self.profile_var.get()]
            nr = suggest_receipt_number(self.disk_var.get().strip(), profile, self.owner_var.get().strip())
            self.receipt_var.set(nr)
            self.message.configure(text='Forslag beregnet fra synlige gruppemapper på valgt disk. '
                                        'Kontroller annet depotregister/disk før nummeret tas i bruk.')
        except (KeyError, OSError, ValueError) as exc:
            self.message.configure(text=f'Kan ikke foreslå mottaksnummer: {exc}')

    def _pick_setup(self):
        p = filedialog.askopenfilename(parent=self, title='Velg mottaks-setup',
                                      filetypes=[('JSON', '*.json'), ('Alle filer', '*.*')])
        if p:
            self.setup_var.set(p)
            self._load_setup()

    def _load_setup(self):
        try:
            profiles = grouped_profiles(self.setup_var.get().strip())
            if not profiles:
                raise ValueError('Setup inneholder ingen profiler for grupperte mottak')
            self._profiles = {p.name:p for p in profiles}
            self.profiles_menu.configure(values=list(self._profiles))
            if self.profile_var.get() not in self._profiles:
                self.profile_var.set(profiles[0].name)
        except (OSError, ValueError, KeyError) as exc:
            self._profiles = {}
            self.profiles_menu.configure(values=['Ugyldig setup'])
            self.profile_var.set('Ugyldig setup')
            self.message.configure(text=f'Kunne ikke lese setup: {exc}')

    def _profile_settings(self) -> dict[str, str]:
        active = self._profiles.get(self.profile_var.get())
        if active is None:
            raise ValueError('Velg en gyldig mappeprofil før lagring')
        return {
            'setup_file': self.setup_var.get().strip(),
            'folder_profile_id': active.profile_id,
            'disk': self.disk_var.get().strip(),
            'group': self.group_var.get().strip(),
            'owner_code': self.owner_var.get().strip(),
            'default_mode': self.mode.get(),
        }

    def _apply_saved_profile(self, path: str | Path) -> None:
        values = load_ingest_profile(path)
        self.setup_var.set(values['setup_file'])
        self._load_setup()
        found = next((profile.name for profile in self._profiles.values()
                      if profile.profile_id == values['folder_profile_id']), None)
        if found is None:
            raise ValueError('Mappeprofilen finnes ikke i angitt depot-setup')
        self.profile_var.set(found)
        # These are always a new operation, never a previously issued receipt.
        self.receipt_var.set('')
        self.xml_var.set('')
        self._metadata = {}
        self.label_var.set('')
        self.extraction_var.set('')
        self.date_var.set(date.today().isoformat())
        self.disk_var.set(values['disk'])
        self.group_var.set(values['group'])
        self.owner_var.set(values['owner_code'])
        self.mode.set(values['default_mode'])
        self._mode_changed()
        self._auto_number_if_blank()
        self._saved_profile_path = Path(path)
        self.profile_status.configure(text=f'Brukerprofil: {self._saved_profile_path.name}')
        self.message.configure(text='Profil åpnet. LABEL/info.xml og mottaksnummer må kontrolleres for ny levering.')
        save_config({'last_ingest_user_profile_file': str(self._saved_profile_path)})

    def _open_saved_profile(self):
        path = filedialog.askopenfilename(parent=self, title='Åpne lagret mottaksprofil',
                filetypes=[('Mottaksprofil (JSON)', '*.json')])
        if not path:
            return
        try:
            self._apply_saved_profile(path)
        except (OSError, ValueError) as exc:
            messagebox.showerror('Mottaksprofil', str(exc), parent=self)

    def _write_saved_profile(self, path: str | Path, *, replace: bool):
        saved = save_ingest_profile(path, self._profile_settings(), replace=replace)
        self._saved_profile_path = saved
        self.profile_status.configure(text=f'Brukerprofil: {saved.name}')
        save_config({'last_ingest_user_profile_file': str(saved)})
        self.message.configure(text=f'Mottaksprofil lagret: {saved}. Mottaksnummer/LABEL er ikke lagret.')

    def _save_as_new_profile(self):
        path = filedialog.asksaveasfilename(parent=self, title='Lagre ny mottaksprofil',
                  defaultextension='.json', initialfile='mottaksprofil.json',
                  filetypes=[('Mottaksprofil (JSON)', '*.json')])
        if not path:
            return
        try:
            self._write_saved_profile(path, replace=False)
        except (OSError, ValueError) as exc:
            messagebox.showerror('Mottaksprofil', str(exc), parent=self)

    def _save_saved_profile(self):
        if self._saved_profile_path is None:
            self._save_as_new_profile()
            return
        try:
            self._write_saved_profile(self._saved_profile_path, replace=True)
        except (OSError, ValueError) as exc:
            messagebox.showerror('Mottaksprofil', str(exc), parent=self)

    def _preview(self):
        try:
            profile = self._profiles[self.profile_var.get()]
            if self.xml_var.get().strip():
                self._metadata = read_info_xml(self.xml_var.get().strip())
            params = (self.disk_var.get().strip(), self.group_var.get().strip(), profile,
                      self.owner_var.get().strip(), self.receipt_var.get().strip(),
                      self.label_var.get().strip())
            if self.mode.get() == 'Mottak':
                plan = plan_receipt(*params, info_xml=self.xml_var.get().strip() or None)
            else:
                plan = plan_extraction(*params, self.extraction_var.get().strip(),
                                      self.date_var.get().strip(),
                                      info_xml=self.xml_var.get().strip() or None)
            self._plan = plan
            lines = [f'Handling: {"Mottak" if plan.mode == "receipt" else "Uttrekk"}',
                     f'Eierkommune: {plan.owner_code}', f'Mottaksnummer: {plan.receipt_number}',
                     f'LABEL: {plan.label}', f'Mottaksmappe: {plan.receipt_root}',
                     f'Ny mappe: {plan.root}', '']
            if plan.mode == 'extraction':
                lines += [f'Uttrekks-ID (arkivskaper): {plan.extraction_id}',
                          f'Dato: {plan.ingest_date}', '']
            lines.extend(str(p.relative_to(plan.group)) + '/' for p in plan.paths)
            lines += ['', f'Kanonisk mottakslogg (JSONL): {plan.audit_path}',
                      f'Lesbar mottakslogg: {plan.receipt_root / "depot-log.txt"}']
            if plan.mode == 'receipt':
                lines += ['Mottaket er bare en flat mappe. Ingen arkivfiler er lastet ned.',
                          'Neste steg: Last ned kryptert(e) leveranse(r) manuelt hit.']
            if plan.mode == 'extraction':
                lines += [f'Uttrekkslogg: {plan.root / plan.profile.operations_folder / "depot-log.txt"}',
                          f'Portabel hendelseslogg: {plan.root / plan.profile.operations_folder / "ingest.events.jsonl"}']
            self._put_preview('\n'.join(lines))
            self.message.configure(text=f'{len(plan.paths)} mapper planlagt. '
                                        'Ingen filer lastes ned eller kopieres. '
                                        'Passord registreres ikke i DWM-loggen.')
            return plan
        except (KeyError, OSError, ValueError) as exc:
            self._plan = None
            self._put_preview(f'Kan ikke opprette plan: {exc}')
            return None

    def _create(self):
        plan = self._preview()
        if plan is None:
            return
        if not messagebox.askyesno('Bekreft Mottak / Ingest',
            f'Opprett {len(plan.paths)} mapper?\n\n{plan.root}\n\n'
            f'Mottaksnummer: {plan.receipt_number}\nLABEL: {plan.label}\n\n'
            'Ingen innleverte filer kopieres, flyttes eller endres.\n'
            'Bekreft at mottaksnummeret er kontrollert mot depotregisteret og andre disker.',
            parent=self):
            return
        try:
            actor = LocalUserProfileIdentityProvider().current_identity()
            create_grouped_ingest(plan, actor=actor)
        except Exception as exc:
            messagebox.showerror('Mottak / Ingest', str(exc), parent=self)
            return
        try:
            save_config({'last_ingest_disk': str(plan.disk),
                         'last_ingest_group': plan.group.name,
                         'receiving_setup_file': self.setup_var.get().strip()})
        except OSError:
            pass
        self._plan = None
        self.message.configure(text=f'Opprettet og loggført: {plan.root}')
        readable_log = (plan.receipt_root if plan.mode == 'receipt'
                        else plan.root / plan.profile.operations_folder) / 'depot-log.txt'
        next_step = ('\n\nNeste steg: Last ned leveransen manuelt til mottaksmappen.'
                     if plan.mode == 'receipt' else '')
        messagebox.showinfo('Mottak / Ingest',
            f'Opprettet: {plan.root}\n\nMottakslogg: {plan.audit_path}\n'
            f'Depotlogg: {readable_log}{next_step}', parent=self)
