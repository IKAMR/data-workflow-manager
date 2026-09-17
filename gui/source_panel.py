from __future__ import annotations
from pathlib import Path
from typing import Callable
import customtkinter as ctk
from noark5_workflow.sources.noark5_extraction import Noark5Extraction
from settings import load_config, save_config
from . import theme
from .source_location_dialog import SourceLocationDialog

class SourcePanel(ctk.CTkFrame):
    def __init__(self, master, on_source_changed: Callable[[Noark5Extraction | None], None]):
        super().__init__(master,fg_color=theme.PANEL_BG,corner_radius=8)
        self.on_source_changed=on_source_changed
        self.on_browse_complete=None
        self.extraction=None
        self.profile_id=None
        self.path_var=ctk.StringVar()
        self.settings=load_config()
        self._location_dialog=None
        self._location_dialog_open=False
        self.grid_columnconfigure(0,weight=1); self.grid_rowconfigure(3,weight=1)
        self.title_label=ctk.CTkLabel(self,text="SOURCE",font=theme.font(theme.SECTION_SIZE,"bold"),
                                      text_color=theme.TEXT_MUTED)
        self.title_label.grid(row=0,column=0,padx=10,pady=(10,5),sticky="w")
        self.path_entry=ctk.CTkEntry(self,textvariable=self.path_var,font=theme.font(theme.SMALL_SIZE))
        self.path_entry.grid(row=1,column=0,padx=10,pady=4,sticky="ew")
        self.browse_button=ctk.CTkButton(self,text="Bla gjennom...",command=self._browse,height=30,
                                         font=theme.font(theme.SMALL_SIZE))
        self.browse_button.grid(row=2,column=0,padx=10,pady=(4,8),sticky="ew")
        self.info=ctk.CTkTextbox(self,height=180,wrap="word",font=theme.font(theme.SMALL_SIZE))
        self.info.grid(row=3,column=0,padx=10,pady=(0,10),sticky="nsew")
        self._set_text("Velg Source – uttrekksmappe. Velg profil for formatspesifikk gjenkjenning.")

    def set_profile(self, profile_id: str | None) -> None:
        self.profile_id=profile_id or None
        self.title_label.configure(text="NOARK 5" if self.profile_id=="noark5" else
                                        "SIARD" if self.profile_id=="siard" else "SOURCE")
        self.detect()

    def _recent_dirs(self)->list[Path]:
        raw=self.settings.get("recent_source_extraction_dirs",[])
        if not isinstance(raw,list): raw=[]
        result=[]
        for value in raw:
            p=Path(str(value))
            if p.is_dir() and p not in result: result.append(p)
        legacy=str(self.settings.get("last_noark_source_dir","")).strip()
        if legacy:
            p=Path(legacy)
            if p.is_dir() and p not in result: result.append(p)
        return result[:10]

    def _remember(self,path:Path)->None:
        raw=self.settings.get("recent_source_extraction_dirs",[])
        recent=[str(v) for v in raw] if isinstance(raw,list) else []
        value=str(path); recent=[v for v in recent if v!=value]; recent.insert(0,value); recent=recent[:10]
        self.settings["last_source_extraction_dir"]=value
        self.settings["recent_source_extraction_dirs"]=recent
        changes={"last_source_extraction_dir":value,"recent_source_extraction_dirs":recent}
        if self.profile_id=="noark5":
            self.settings["last_noark_source_dir"]=value; changes["last_noark_source_dir"]=value
        save_config(changes)

    def _forget(self,path:Path)->None:
        value=str(path)
        raw=self.settings.get("recent_source_extraction_dirs",[])
        recent=[str(v) for v in raw] if isinstance(raw,list) else []
        recent=[v for v in recent if v!=value]
        self.settings["recent_source_extraction_dirs"]=recent
        save_config({"recent_source_extraction_dirs":recent})
        self._browse()

    def _browse(self)->None:
        # Single-instance guard is set before the dialog is constructed.
        # This closes the small rapid-click race where two CTkToplevels could
        # be created before the first one was fully mapped.
        if self._location_dialog_open:
            dialog=self._location_dialog
            if dialog is not None:
                try:
                    if dialog.winfo_exists():
                        dialog.focus(); dialog.lift()
                except Exception:
                    pass
            return

        self._location_dialog_open=True
        self.browse_button.configure(state="disabled")
        initial=str(self.settings.get("last_source_extraction_dir","")).strip()
        initial_path=Path(initial) if initial else None
        try:
            dialog=SourceLocationDialog(
                self,
                recent_dirs=self._recent_dirs(),
                initial_dir=initial_path,
                on_choose=self._browse_chosen,
                on_remove=self._forget,
            )
            self._location_dialog=dialog
            dialog.bind(
                "<Destroy>",
                lambda event,d=dialog:self._location_closed(d,event),
                add="+",
            )
        except Exception:
            self._location_dialog=None
            self._location_dialog_open=False
            self.browse_button.configure(state="normal")
            raise

    def _location_closed(self,dialog,event=None)->None:
        # Ignore Destroy events from children. Only the actual Toplevel closes
        # the single-instance guard.
        if event is not None and getattr(event,"widget",None) is not dialog:
            return
        if self._location_dialog is dialog:
            self._location_dialog=None
        self._location_dialog_open=False
        try:
            self.browse_button.configure(state="normal")
        except Exception:
            pass

    def _browse_chosen(self,path:Path)->None:
        self.set_path(str(path))
        if callable(self.on_browse_complete): self.on_browse_complete(path)

    def set_path(self,folder:str)->None:
        self.path_var.set(folder)
        if folder: self._remember(Path(folder))
        self.detect()

    def detect(self)->None:
        root=self.path_var.get().strip()
        if not root:
            self.extraction=None; self.on_source_changed(None)
            self._set_text("Velg Source – uttrekksmappe. Velg profil for formatspesifikk gjenkjenning.")
            return
        if self.profile_id!="noark5":
            self.extraction=None; self.on_source_changed(None)
            if self.profile_id=="siard":
                self._set_text("SIARD-profil valgt.\n\nSIARD-spesifikk kildegjenkjenning er ikke implementert i denne appen ennå.")
            else:
                self._set_text(f"Source valgt:\n{root}\n\nIngen profil valgt – formatspesifikk gjenkjenning kjøres ikke.")
            return

        root_path=Path(root)
        if not root_path.is_dir():
            self.extraction=None
            self._set_text(
                "Uttrekksmappen er ikke tilgjengelig:\n"
                f"{root}\n\n"
                "Kontroller at ekstern disk, nettverksstasjon eller annen lagring er tilkoblet."
            )
            self.on_source_changed(None)
            return

        try:
            self.extraction=Noark5Extraction.detect(root_path); self._render_inventory(self.extraction)
        except Exception as exc:
            self.extraction=None; self._set_text(f"FEIL: {exc}")
        self.on_source_changed(self.extraction)

    def _render_inventory(self,extraction:Noark5Extraction)->None:
        lines=["Noark 5-uttrekk" if extraction.is_noark5_candidate else "Ikke gjenkjent som Noark 5-uttrekk",""]
        labels={"arkivstruktur":"arkivstruktur.xml","arkivuttrekk":"arkivuttrekk.xml",
                "loepende_journal":"loependeJournal.xml","offentlig_journal":"offentligJournal.xml",
                "endringslogg":"endringslogg.xml"}
        for key,label in labels.items(): lines.append(f"[OK] {label}" if extraction.metadata_files.get(key) else f"[--] {label}")
        n=len(extraction.xsd_files); lines.append(f"[OK] XSD-filer: {n}" if n else "[--] XSD-filer: 0")
        lines.append(f"[OK] {extraction.documents_dir.name}/" if extraction.documents_dir else "[--] dokument/dokumenter/")
        if extraction.business_metadata_files: lines.append(f"[OK] Virksomhetsspesifikke metadata: {len(extraction.business_metadata_files)}")
        self._set_text("\n".join(lines))

    def _set_text(self,text:str)->None:
        self.info.configure(state="normal"); self.info.delete("1.0","end"); self.info.insert("1.0",text); self.info.configure(state="disabled")
