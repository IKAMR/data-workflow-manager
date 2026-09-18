from __future__ import annotations

from typing import Callable
import tkinter as tk
import customtkinter as ctk

from app.operation_metadata import maturity_short_label
from noark5_workflow.core.registry import OperationRegistry
from noark5_workflow.core.workflow import Workflow
from . import theme
from .workflow_status import status_spec


class _Tooltip:
    """One shared tooltip window for the whole workflow panel.

    The previous per-widget Toplevel model could leave several independent
    overlays visible after rapid pointer movement.  This manager owns exactly
    one Toplevel and reuses it for every workflow control.  The tooltip is
    positioned beside the mouse pointer, remains visible while the pointer
    stays on the owning widget, and is hidden immediately on leave/click.

    ``widget`` and ``window`` intentionally remain public attributes because
    the established runtime tooltip watchdog uses them as a final safety net.
    """

    OFFSET_X = 22
    OFFSET_Y = 24

    def __init__(self, owner) -> None:
        self.owner = owner
        self.widget = None
        self.window = None
        self.label = None
        self._text = ""

    def bind(self, widget, text: str) -> None:
        widget.bind(
            "<Enter>",
            lambda event, w=widget, t=text: self._show(event, w, t),
            add="+",
        )
        widget.bind(
            "<Motion>",
            lambda event, w=widget: self._move(event, w),
            add="+",
        )
        widget.bind(
            "<Leave>",
            lambda _event, w=widget: self._hide_if_owner(w),
            add="+",
        )
        widget.bind(
            "<ButtonPress>",
            lambda _event, w=widget: self._hide_if_owner(w),
            add="+",
        )
        widget.bind(
            "<ButtonRelease>",
            lambda _event, w=widget: self._hide_if_owner(w),
            add="+",
        )
        widget.bind(
            "<Destroy>",
            lambda _event, w=widget: self._hide_if_owner(w),
            add="+",
        )

    def _ensure_window(self, parent) -> bool:
        try:
            if self.window is not None and self.window.winfo_exists():
                return True
        except Exception:
            self.window = None
            self.label = None

        try:
            tip = tk.Toplevel(self.owner)
            tip.withdraw()
            tip.overrideredirect(True)
            try:
                tip.transient(parent)
            except Exception:
                pass
            label = tk.Label(
                tip,
                text="",
                relief="solid",
                borderwidth=1,
                padx=9,
                pady=6,
                justify="left",
            )
            label.pack()
            self.window = tip
            self.label = label
            return True
        except Exception:
            self.window = None
            self.label = None
            return False

    def _configure_label(self, text: str) -> None:
        if self.label is None:
            return
        bg, fg, border = theme.tooltip_colors()
        tooltip_font = (
            theme.FONT_FAMILY,
            theme.FontRegistry.effective_size(theme.TOOLTIP_SIZE),
        )
        self.label.configure(
            text=text,
            bg=bg,
            fg=fg,
            font=tooltip_font,
            highlightthickness=1,
            highlightbackground=border,
            highlightcolor=border,
        )

    def _position(self, event=None) -> None:
        if self.window is None or self.label is None:
            return
        try:
            parent = self.owner.winfo_toplevel()
            parent.update_idletasks()

            pointer_x = (
                int(event.x_root)
                if event is not None and hasattr(event, "x_root")
                else int(self.owner.winfo_pointerx())
            )
            pointer_y = (
                int(event.y_root)
                if event is not None and hasattr(event, "y_root")
                else int(self.owner.winfo_pointery())
            )

            left = int(parent.winfo_rootx())
            top = int(parent.winfo_rooty())
            right = left + max(1, int(parent.winfo_width()))
            bottom = top + max(1, int(parent.winfo_height()))
            margin = 10

            # A tooltip must fit as a complete readable box.  Native Tk gives
            # reliable requested pixel sizes here; CTkToplevel could report a
            # scaled size before mapping and caused text to be clipped at both ends.
            available_width = max(120, right - left - (margin * 2))
            self.label.configure(wraplength=max(120, available_width - 24))
            self.window.update_idletasks()
            width = max(1, int(self.label.winfo_reqwidth()) + 2)
            height = max(1, int(self.label.winfo_reqheight()) + 2)
            width = min(width, available_width)

            x = pointer_x + self.OFFSET_X
            y = pointer_y + self.OFFSET_Y

            if x + width + margin > right:
                x = pointer_x - width - self.OFFSET_X
            if y + height + margin > bottom:
                y = pointer_y - height - self.OFFSET_Y

            x = max(left + margin, min(x, right - width - margin))
            y = max(top + margin, min(y, bottom - height - margin))

            # Set explicit size as well as position.  This avoids a second geometry
            # negotiation shrinking the borderless tooltip after it has been placed.
            self.window.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            pass

    def _show(self, event, widget, text: str) -> None:
        if not text:
            self._hide()
            return
        try:
            if not widget.winfo_exists():
                return
            parent = widget.winfo_toplevel()
        except Exception:
            return

        # A new hover always replaces the previous one.  There can never be
        # several independently mapped tooltip windows.
        self.widget = widget
        self._text = text
        if not self._ensure_window(parent):
            return
        self._configure_label(text)
        self._position(event)
        try:
            self.window.deiconify()
            tip = self.window
            tip.lift(parent)
        except Exception:
            pass

    def _move(self, event, widget) -> None:
        if widget is not self.widget or self.window is None:
            return
        try:
            if not self.window.winfo_viewable():
                return
        except Exception:
            return
        self._position(event)

    def _hide_if_owner(self, widget) -> None:
        # Ignore delayed Leave/Destroy events from a previously hovered widget.
        # Only the widget that currently owns the shared tooltip may hide it.
        if widget is self.widget:
            self._hide()

    def _hide(self, _event=None) -> None:
        self.widget = None
        self._text = ""
        if self.window is not None:
            try:
                self.window.withdraw()
            except Exception:
                try:
                    self.window.destroy()
                except Exception:
                    pass
                self.window = None
                self.label = None


class WorkflowPanel(ctk.CTkFrame):
    def __init__(
        self,
        master,
        registry: OperationRegistry,
        workflow: Workflow,
        on_run: Callable[[], None],
        on_edit: Callable[[str], None] | None = None,
        on_checkpoint_toggle: Callable[[str], None] | None = None,
        checkpoint_ids_provider: Callable[[], set[str]] | None = None,
    ):
        super().__init__(master, fg_color=theme.APP_BG, corner_radius=0)
        self.registry = registry
        self.workflow = workflow
        self.on_run = on_run
        self.on_edit = on_edit
        self.on_checkpoint_toggle = on_checkpoint_toggle
        self.checkpoint_ids_provider = checkpoint_ids_provider
        self.on_reorder: Callable[[str], None] | None = None
        self.on_rerun: Callable[[str], None] | None = None
        self.on_regenerate_stale: Callable[[], None] | None = None
        self.stale_ids_provider: Callable[[], set[str]] | None = None
        self.status_provider: Callable[[str], str] | None = None
        self.on_status_click: Callable[[str], None] | None = None
        self._tooltip = _Tooltip(self)
        # Compatibility boundary for the established a11/a26 watchdog/tests:
        # one shared manager replaces the previous list of per-widget windows.
        self._tooltips = [self._tooltip]
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            self, text="WORKFLOW", font=theme.font(theme.SMALL_SIZE), text_color=theme.TEXT_MUTED
        ).grid(row=0, column=0, padx=8, pady=(4, 8), sticky="w")
        self.items = ctk.CTkScrollableFrame(self, fg_color=theme.PANEL_BG_DARK, corner_radius=8)
        self.items.grid(row=1, column=0, padx=4, pady=0, sticky="nsew")
        self.items.grid_columnconfigure(0, weight=1)
        run_row = ctk.CTkFrame(self, fg_color="transparent")
        run_row.grid(row=2, column=0, padx=4, pady=(10, 6), sticky="ew")
        run_row.grid_columnconfigure(0, weight=1)
        self.run_button = ctk.CTkButton(
            run_row,
            text="Kjør workflow",
            command=self.on_run,
            height=34,
            font=theme.font(theme.NORMAL_SIZE),
        )
        self.run_button.grid(row=0, column=0, sticky="ew")
        self.reset_project_button = ctk.CTkButton(
            run_row,
            text="↻",
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            width=38,
            height=34,
            state="disabled",
            font=theme.font(theme.NORMAL_SIZE),
        )
        self.reset_project_button.grid(row=0, column=1, padx=(6, 0))
        self.regenerate_stale_button = ctk.CTkButton(
            self,
            text="Regenerer foreldede",
            command=lambda: self.on_regenerate_stale() if self.on_regenerate_stale else None,
            height=30,
            state="disabled",
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            font=theme.font(theme.SMALL_SIZE),
        )
        self.regenerate_stale_button.grid(row=3, column=0, padx=4, pady=(0, 6), sticky="ew")
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=4, column=0, padx=4, pady=(0, 4), sticky="ew")
        buttons.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            buttons,
            text="Tøm",
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self.clear,
            height=28,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0, column=0, padx=(0, 3), sticky="ew")
        self.save_profile_button = ctk.CTkButton(
            buttons,
            text="Lagre profil...",
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            state="disabled",
            height=28,
            font=theme.font(theme.SMALL_SIZE),
        )
        self.save_profile_button.grid(row=0, column=1, padx=(3, 0), sticky="ew")
        project_buttons = ctk.CTkFrame(self, fg_color="transparent")
        project_buttons.grid(row=5, column=0, padx=4, pady=(0, 4), sticky="ew")
        project_buttons.grid_columnconfigure((0, 1), weight=1)
        self.open_project_button = ctk.CTkButton(
            project_buttons,
            text="📂 Åpne prosjekt",
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            state="disabled",
            height=28,
            font=theme.font(theme.SMALL_SIZE),
        )
        self.open_project_button.grid(row=0, column=0, padx=(0, 3), sticky="ew")
        self.save_project_button = ctk.CTkButton(
            project_buttons,
            text="💾 Lagre prosjekt",
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            state="disabled",
            height=28,
            font=theme.font(theme.SMALL_SIZE),
        )
        self.save_project_button.grid(row=0, column=1, padx=(3, 0), sticky="ew")
        self.refresh()

    def add(self, operation_id: str) -> bool:
        added = self.workflow.add(operation_id)
        self.refresh()
        return added

    def remove(self, operation_id: str) -> None:
        self.workflow.remove(operation_id)
        self.refresh()

    def clear(self) -> None:
        self.workflow.clear()
        self.refresh()

    def move_up(self, operation_id: str) -> None:
        if self.workflow.move_up(operation_id):
            if self.on_reorder:
                self.on_reorder(operation_id)
            self.refresh()

    def move_down(self, operation_id: str) -> None:
        if self.workflow.move_down(operation_id):
            if self.on_reorder:
                self.on_reorder(operation_id)
            self.refresh()

    def set_run_text(self, text: str) -> None:
        self.run_button.configure(text=text)

    def _add_tooltip(self, widget, text: str) -> None:
        self._tooltip.bind(widget, text)

    def refresh(self) -> None:
        for tooltip in self._tooltips: tooltip._hide()
        self._tooltips.clear()
        for child in self.items.winfo_children():
            child.destroy()
        ids = self.workflow.operation_ids()
        checkpoints = set(self.checkpoint_ids_provider()) if self.checkpoint_ids_provider else set()
        stale_ids = set(self.stale_ids_provider()) if self.stale_ids_provider else set()
        self.regenerate_stale_button.configure(
            state="normal" if stale_ids and self.on_regenerate_stale is not None else "disabled"
        )
        if not ids:
            ctk.CTkLabel(
                self.items,
                text="Legg til operasjoner\nfra paletten til høyre",
                font=theme.font(theme.SMALL_SIZE),
                text_color=theme.TEXT_MUTED,
                justify="center",
            ).grid(row=0, column=0, padx=8, pady=36)
            return

        for row, op_id in enumerate(ids):
            operation = self.registry.get(op_id)
            item = ctk.CTkFrame(self.items, fg_color=theme.CARD_BG, corner_radius=6)
            item.grid(row=row, column=0, padx=5, pady=3, sticky="ew")
            item.grid_columnconfigure(1, weight=1)

            status_key = self.status_provider(op_id) if self.status_provider else (
                "stale" if op_id in stale_ids else "not_run"
            )
            spec = status_spec(status_key)
            status_icon = ctk.CTkLabel(
                item,
                text=spec.symbol,
                width=24,
                height=24,
                corner_radius=12,
                fg_color=spec.color,
                text_color="#ffffff",
                font=theme.font(theme.NORMAL_SIZE, "bold"),
            )
            status_icon.grid(row=0, column=0, padx=(7, 5), pady=5)
            self._add_tooltip(status_icon,
                f"{spec.label}: {spec.tooltip}"
                + (" Klikk for resultatversjoner." if self.on_status_click is not None else ""),
            )
            if self.on_status_click is not None:
                status_icon.configure(cursor="hand2")
                status_icon.bind(
                    "<Button-1>",
                    lambda _event, oid=op_id: self.on_status_click(oid),
                    add="+",
                )

            label = f"{row + 1}. ({maturity_short_label(op_id)}) {operation.definition.name}"
            ctk.CTkLabel(
                item, text=label, font=theme.font(theme.SMALL_SIZE), anchor="w"
            ).grid(row=0, column=1, padx=(0, 4), pady=5, sticky="ew")

            col = 2
            up = ctk.CTkButton(
                item, text="↑", width=26, height=24,
                state="disabled" if row == 0 else "normal",
                fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
                command=lambda oid=op_id: self.move_up(oid),
            )
            up.grid(row=0, column=col, padx=1, pady=5)
            self._add_tooltip(up, "Flytt operasjonen opp")
            col += 1

            down = ctk.CTkButton(
                item, text="↓", width=26, height=24,
                state="disabled" if row == len(ids) - 1 else "normal",
                fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
                command=lambda oid=op_id: self.move_down(oid),
            )
            down.grid(row=0, column=col, padx=1, pady=5)
            self._add_tooltip(down, "Flytt operasjonen ned")
            col += 1

            if self.on_rerun is not None:
                rerun = ctk.CTkButton(
                    item, text="↻", width=28, height=24,
                    font=theme.font(theme.NORMAL_SIZE),
                    fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
                    command=lambda oid=op_id: self.on_rerun(oid),
                )
                rerun.grid(row=0, column=col, padx=1, pady=5)
                self._add_tooltip(rerun, "Kjør bare denne operasjonen på nytt")
                col += 1

            configure = getattr(operation, "configure", None)
            if self.on_edit is not None and callable(configure):
                btn = ctk.CTkButton(
                    item, text="✎", width=28, height=24,
                    font=theme.font(theme.NORMAL_SIZE),
                    fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
                    command=lambda oid=op_id: self.on_edit(oid),
                )
                btn.grid(row=0, column=col, padx=1, pady=5)
                self._add_tooltip(btn, "Rediger operasjonen")
                col += 1

            if self.on_checkpoint_toggle is not None and row < len(ids) - 1:
                active_checkpoint = op_id in checkpoints
                btn = ctk.CTkButton(
                    item, text="■" if active_checkpoint else "", width=28, height=24,
                    font=theme.font(theme.NORMAL_SIZE),
                    fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
                    command=lambda oid=op_id: self.on_checkpoint_toggle(oid),
                )
                btn.grid(row=0, column=col, padx=1, pady=5)
                self._add_tooltip(
                    btn,
                    "Fjern kontrollpunkt" if active_checkpoint else "Sett kontrollpunkt etter operasjonen",
                )
                col += 1

            remove = ctk.CTkButton(
                item, text="×", width=28, height=24,
                font=("Consolas", 14, "bold"),
                command=lambda oid=op_id: self.remove(oid),
            )
            remove.grid(row=0, column=col, padx=(1, 5), pady=5)
            self._add_tooltip(remove, "Fjern operasjonen fra workflow")
