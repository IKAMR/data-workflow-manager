from __future__ import annotations

from typing import Callable
import customtkinter as ctk

from app.operation_metadata import maturity_short_label
from noark5_workflow.core.registry import OperationRegistry
from noark5_workflow.core.workflow import Workflow
from . import theme


class _Tooltip:
    """Small hover tooltip that can never remain as a stale top-level overlay."""

    AUTO_HIDE_MS = 1800

    def __init__(self, widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.window = None
        self._after_id = None

        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
        widget.bind("<ButtonRelease>", self._hide, add="+")
        widget.bind("<Destroy>", self._hide, add="+")

    def _cancel_auto_hide(self) -> None:
        if self._after_id is None:
            return
        try:
            self.widget.after_cancel(self._after_id)
        except Exception:
            pass
        self._after_id = None

    def _show(self, _event=None) -> None:
        if self.window is not None or not self.text:
            return
        try:
            if not self.widget.winfo_exists():
                return
            x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        except Exception:
            return

        self.window = tip = ctk.CTkToplevel(self.widget)
        tip.withdraw()
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        ctk.CTkLabel(
            tip,
            text=self.text,
            fg_color=theme.CARD_BG,
            text_color=theme.TEXT_MAIN,
            corner_radius=5,
            font=theme.font(theme.SMALL_SIZE),
        ).pack(padx=1, pady=1)
        tip.update_idletasks()
        tip.geometry(f"+{x-tip.winfo_width()//2}+{y}")
        tip.deiconify()

        # A tooltip is transient UI. Auto-hide is a final safety net for cases
        # where the hovered workflow button is moved/rebuilt under the pointer.
        self._cancel_auto_hide()
        try:
            self._after_id = self.widget.after(self.AUTO_HIDE_MS, self._hide)
        except Exception:
            self._after_id = None

    def _hide(self, _event=None) -> None:
        self._cancel_auto_hide()
        if self.window is not None:
            try:
                self.window.destroy()
            except Exception:
                pass
            self.window = None


class WorkflowPanel(ctk.CTkFrame):
    def __init__(self,master,registry:OperationRegistry,workflow:Workflow,on_run:Callable[[],None],
                 on_edit:Callable[[str],None]|None=None,
                 on_checkpoint_toggle:Callable[[str],None]|None=None,
                 checkpoint_ids_provider:Callable[[],set[str]]|None=None):
        super().__init__(master,fg_color=theme.APP_BG,corner_radius=0)
        self.registry=registry; self.workflow=workflow; self.on_run=on_run
        self.on_edit=on_edit; self.on_checkpoint_toggle=on_checkpoint_toggle
        self.checkpoint_ids_provider=checkpoint_ids_provider
        self.on_reorder: Callable[[str],None] | None = None
        self._tooltips=[]
        self.grid_columnconfigure(0,weight=1); self.grid_rowconfigure(1,weight=1)
        ctk.CTkLabel(self,text="WORKFLOW",font=theme.font(theme.SMALL_SIZE),
                     text_color=theme.TEXT_MUTED).grid(row=0,column=0,padx=8,pady=(4,8),sticky="w")
        self.items=ctk.CTkScrollableFrame(self,fg_color=theme.PANEL_BG_DARK,corner_radius=8)
        self.items.grid(row=1,column=0,padx=4,pady=0,sticky="nsew"); self.items.grid_columnconfigure(0,weight=1)
        run_row=ctk.CTkFrame(self,fg_color="transparent"); run_row.grid(row=2,column=0,padx=4,pady=(10,6),sticky="ew")
        run_row.grid_columnconfigure(0,weight=1)
        self.run_button=ctk.CTkButton(run_row,text="Kjør workflow",command=self.on_run,height=34,
                                      font=theme.font(theme.NORMAL_SIZE))
        self.run_button.grid(row=0,column=0,sticky="ew")
        self.reset_project_button=ctk.CTkButton(run_row,text="↻",fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,width=38,height=34,state="disabled",font=theme.font(theme.NORMAL_SIZE))
        self.reset_project_button.grid(row=0,column=1,padx=(6,0))
        buttons=ctk.CTkFrame(self,fg_color="transparent"); buttons.grid(row=3,column=0,padx=4,pady=(0,4),sticky="ew")
        buttons.grid_columnconfigure((0,1),weight=1)
        ctk.CTkButton(buttons,text="Tøm",fg_color=theme.BUTTON_BG,hover_color=theme.BUTTON_HOVER,
                      command=self.clear,height=28,font=theme.font(theme.SMALL_SIZE)).grid(row=0,column=0,padx=(0,3),sticky="ew")
        self.save_profile_button=ctk.CTkButton(buttons,text="Lagre profil...",fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,state="disabled",height=28,font=theme.font(theme.SMALL_SIZE))
        self.save_profile_button.grid(row=0,column=1,padx=(3,0),sticky="ew")
        project_buttons=ctk.CTkFrame(self,fg_color="transparent"); project_buttons.grid(row=4,column=0,padx=4,pady=(0,4),sticky="ew")
        project_buttons.grid_columnconfigure((0,1),weight=1)
        self.open_project_button=ctk.CTkButton(project_buttons,text="📂 Åpne prosjekt",fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,state="disabled",height=28,font=theme.font(theme.SMALL_SIZE))
        self.open_project_button.grid(row=0,column=0,padx=(0,3),sticky="ew")
        self.save_project_button=ctk.CTkButton(project_buttons,text="💾 Lagre prosjekt",fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,state="disabled",height=28,font=theme.font(theme.SMALL_SIZE))
        self.save_project_button.grid(row=0,column=1,padx=(3,0),sticky="ew")
        self.refresh()

    def add(self,operation_id:str)->bool:
        added=self.workflow.add(operation_id); self.refresh(); return added
    def remove(self,operation_id:str)->None:
        self.workflow.remove(operation_id); self.refresh()
    def clear(self)->None:
        self.workflow.clear(); self.refresh()
    def move_up(self,operation_id:str)->None:
        if self.workflow.move_up(operation_id):
            if self.on_reorder: self.on_reorder(operation_id)
            self.refresh()
    def move_down(self,operation_id:str)->None:
        if self.workflow.move_down(operation_id):
            if self.on_reorder: self.on_reorder(operation_id)
            self.refresh()
    def set_run_text(self,text:str)->None: self.run_button.configure(text=text)
    def _add_tooltip(self,widget,text:str)->None: self._tooltips.append(_Tooltip(widget,text))

    def refresh(self)->None:
        for tooltip in self._tooltips: tooltip._hide()
        self._tooltips.clear()
        for child in self.items.winfo_children(): child.destroy()
        ids=self.workflow.operation_ids()
        checkpoints=set(self.checkpoint_ids_provider()) if self.checkpoint_ids_provider else set()
        if not ids:
            ctk.CTkLabel(self.items,text="Legg til operasjoner\nfra paletten til høyre",
                         font=theme.font(theme.SMALL_SIZE),text_color=theme.TEXT_MUTED,
                         justify="center").grid(row=0,column=0,padx=8,pady=36)
            return
        for row,op_id in enumerate(ids):
            operation=self.registry.get(op_id)
            item=ctk.CTkFrame(self.items,fg_color=theme.CARD_BG,corner_radius=6)
            item.grid(row=row,column=0,padx=5,pady=4,sticky="ew"); item.grid_columnconfigure(0,weight=1)
            label = f"{row + 1}. ({maturity_short_label(op_id)}) {operation.definition.name}"
            ctk.CTkLabel(item,text=label,font=theme.font(theme.SMALL_SIZE),anchor="w").grid(row=0,column=0,padx=8,pady=7,sticky="ew")
            col=1
            up=ctk.CTkButton(item,text="↑",width=28,height=26,state="disabled" if row==0 else "normal",
                             fg_color=theme.BUTTON_BG,hover_color=theme.BUTTON_HOVER,
                             command=lambda oid=op_id:self.move_up(oid))
            up.grid(row=0,column=col,padx=2,pady=5); self._add_tooltip(up,"Flytt operasjonen opp"); col+=1
            down=ctk.CTkButton(item,text="↓",width=28,height=26,state="disabled" if row==len(ids)-1 else "normal",
                               fg_color=theme.BUTTON_BG,hover_color=theme.BUTTON_HOVER,
                               command=lambda oid=op_id:self.move_down(oid))
            down.grid(row=0,column=col,padx=2,pady=5); self._add_tooltip(down,"Flytt operasjonen ned"); col+=1
            configure=getattr(operation,"configure",None)
            if self.on_edit is not None and callable(configure):
                btn=ctk.CTkButton(item,text="✎",width=30,height=26,font=theme.font(theme.NORMAL_SIZE),
                    fg_color=theme.BUTTON_BG,hover_color=theme.BUTTON_HOVER,command=lambda oid=op_id:self.on_edit(oid))
                btn.grid(row=0,column=col,padx=2,pady=5); self._add_tooltip(btn,"Rediger operasjonen"); col+=1
            if self.on_checkpoint_toggle is not None and row<len(ids)-1:
                active_checkpoint = op_id in checkpoints
                btn=ctk.CTkButton(item,text="■" if active_checkpoint else "",width=30,height=26,
                    font=theme.font(theme.NORMAL_SIZE),fg_color=theme.BUTTON_BG,hover_color=theme.BUTTON_HOVER,
                    command=lambda oid=op_id:self.on_checkpoint_toggle(oid))
                btn.grid(row=0,column=col,padx=2,pady=5)
                self._add_tooltip(btn,"Fjern kontrollpunkt" if active_checkpoint else "Sett kontrollpunkt etter operasjonen"); col+=1
            btn=ctk.CTkButton(item,text="×",width=28,height=26,font=("Consolas",14,"bold"),
                              command=lambda oid=op_id:self.remove(oid))
            btn.grid(row=0,column=col,padx=5,pady=5); self._add_tooltip(btn,"Fjern operasjonen fra workflow")
