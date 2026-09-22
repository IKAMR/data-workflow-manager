from __future__ import annotations
from tkinter import messagebox
import customtkinter as ctk
from noark5_workflow.external_evidence.arkade5 import infer_work_operations_from_depot_report, list_arkade5_imports, load_arkade5_import
from noark5_workflow.external_evidence.arkade5_analysis import build_arkade5_analysis
from noark5_workflow.external_evidence.arkade5_report import write_arkade5_analysis_reports
from version import APP_NAME
from . import theme
from .arkade5_analysis_dialog_a15 import Arkade5AnalysisDialogA15, choose_report_output_dir
from .depot_result_views_a14 import Arkade5AnalysisSelectionDialog, DepotResultViewsDialogA14

class DepotResultViewsDialogA15(DepotResultViewsDialogA14):
    def _build_external_evidence_tab(self,tab)->None:
        super()._build_external_evidence_tab(tab)
        reports=ctk.CTkFrame(tab,fg_color="transparent")
        reports.grid(row=6,column=0,sticky="ew",padx=8,pady=(0,8))
        reports.grid_columnconfigure(0,weight=1)
        ctk.CTkLabel(
            reports,
            text=("Generer lesbare Arkade 5-analyser til valgt output-mappe. "
                  "Alle importerte Arkade-kjøringer kan tas ut i én operasjon."),
            anchor="w",justify="left",wraplength=720,
            text_color=theme.TEXT_MUTED,font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0,column=0,sticky="ew",padx=(0,8))
        ctk.CTkButton(
            reports,text="Generer alle rapporter...",width=165,
            state="normal" if self.report_path else "disabled",
            command=self._generate_all_arkade_reports,
            fg_color=theme.BUTTON_BG,hover_color=theme.BUTTON_HOVER,
        ).grid(row=0,column=1)

    def _open_arkade5_analysis_for_import(self,work,selected)->None:
        try:
            loaded=load_arkade5_import(work,str(selected.get("import_id")))
            analysis=build_arkade5_analysis(loaded["normalized"],loaded.get("reconciliation"))
        except Exception as exc:
            messagebox.showerror(APP_NAME,str(exc),parent=self)
            return
        summary=selected.get("source_summary") or {}
        import_id=str(selected.get("import_id") or "")
        label=(f"Arkade 5  |  Testdato: {summary.get('date_of_testing') or '–'}  |  "
               f"Import-ID: {import_id or '–'}")
        Arkade5AnalysisDialogA15(self,analysis=analysis,source_label=label,import_id=import_id)

    def _generate_all_arkade_reports(self)->None:
        if self.report_path is None:
            return
        output_dir=choose_report_output_dir(self)
        if output_dir is None:
            return
        try:
            work=infer_work_operations_from_depot_report(self.report_path)
            imports=list_arkade5_imports(work)
        except Exception as exc:
            messagebox.showerror(APP_NAME,str(exc),parent=self)
            return
        if not imports:
            messagebox.showinfo(APP_NAME,"Ingen importerte Arkade 5-rapporter er tilgjengelige.",parent=self)
            return
        written=[]
        failed=[]
        for selected in imports:
            import_id=str(selected.get("import_id") or "")
            try:
                loaded=load_arkade5_import(work,import_id)
                analysis=build_arkade5_analysis(loaded["normalized"],loaded.get("reconciliation"))
                written.extend(write_arkade5_analysis_reports(
                    analysis,import_id=import_id,output_dir=output_dir,
                    html_output=True,json_output=True,
                ))
            except Exception as exc:
                failed.append(f"{import_id or 'ukjent import'}: {exc}")
        message=(f"Genererte {len(written)} fil(er) fra {len(imports)} "
                 f"Arkade 5-kjøring(er) til:\n{output_dir}")
        if failed:
            message+="\n\nFeil:\n"+"\n".join(failed)
            messagebox.showwarning(APP_NAME,message,parent=self)
        else:
            messagebox.showinfo(APP_NAME,message,parent=self)
