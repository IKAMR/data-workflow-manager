from __future__ import annotations
from pathlib import Path
from tkinter import filedialog, messagebox
from noark5_workflow.external_evidence.arkade5_report import write_arkade5_analysis_reports
from settings import load_config, save_config
from version import APP_NAME
from .arkade5_analysis_dialog_a14 import Arkade5AnalysisDialog

def choose_report_output_dir(parent) -> Path | None:
    settings=load_config()
    remembered=str(settings.get("last_report_output_dir","") or "").strip()
    kwargs={"title":"Velg output-mappe for rapporter"}
    if remembered and Path(remembered).is_dir():
        kwargs["initialdir"]=remembered
    selected=filedialog.askdirectory(parent=parent,**kwargs)
    if not selected:
        return None
    output=Path(selected)
    save_config({"last_report_output_dir":str(output)})
    return output

class Arkade5AnalysisDialogA15(Arkade5AnalysisDialog):
    def __init__(self,master,*,analysis:dict,source_label:str,import_id:str)->None:
        self.import_id=import_id
        super().__init__(master,analysis=analysis,source_label=source_label)
        bottom_widgets=self.grid_slaves(row=4,column=0)
        if not bottom_widgets:
            return
        bottom=bottom_widgets[0]
        try:
            bottom.grid_columnconfigure(0,weight=1)
            close=bottom.grid_slaves(row=0,column=1)
            if close:
                close[0].grid_configure(column=2)
        except Exception:
            return
        import customtkinter as ctk
        from . import theme
        ctk.CTkButton(
            bottom,text="Generer rapport...",width=145,command=self._generate_report,
            fg_color=theme.BUTTON_BG,hover_color=theme.BUTTON_HOVER,
        ).grid(row=0,column=1,padx=(0,8))

    def _generate_report(self)->None:
        output_dir=choose_report_output_dir(self)
        if output_dir is None:
            return
        try:
            written=write_arkade5_analysis_reports(
                self.analysis,import_id=self.import_id,output_dir=output_dir,
                html_output=True,json_output=True,
            )
        except Exception as exc:
            messagebox.showerror(APP_NAME,str(exc),parent=self)
            return
        messagebox.showinfo(
            APP_NAME,"Rapport generert:\n\n"+"\n".join(str(path) for path in written),parent=self
        )
