from __future__ import annotations

import customtkinter as ctk

from app.storage_layouts import storage_layout_labels
from app.workflow_sequences import noark5_workflow_labels
from . import theme
from .settings_dialog import SettingsDialog as BaseSettingsDialog


def _find_scrollable_frame(widget):
    if isinstance(widget, ctk.CTkScrollableFrame):
        return widget
    for child in widget.winfo_children():
        found = _find_scrollable_frame(child)
        if found is not None:
            return found
    return None


def _next_free_row(frame) -> int:
    max_row = -1
    for child in frame.winfo_children():
        info = child.grid_info()
        if not info:
            continue
        try:
            row = int(info.get("row", -1))
        except (TypeError, ValueError):
            continue
        max_row = max(max_row, row)
    return max_row + 1


class SettingsDialog(BaseSettingsDialog):
    """Window, storage-layout and Noark 5 discovery workflow settings."""

    def __init__(self, master, settings: dict, on_save):
        super().__init__(master, settings, on_save)

        self.restore_position_var = ctk.BooleanVar(
            value=bool(self.settings.get("restore_main_window_position", True))
        )
        self.restore_size_var = ctk.BooleanVar(
            value=bool(self.settings.get("restore_main_window_size", True))
        )
        self.restore_maximized_var = ctk.BooleanVar(
            value=bool(self.settings.get("restore_main_window_maximized", True))
        )

        layout_labels = storage_layout_labels()
        self._layout_labels = layout_labels
        self._layout_ids_by_label = {label: key for key, label in layout_labels.items()}
        current_layout = str(
            self.settings.get("storage_layout_profile", "ikamr_standard")
        )
        self.storage_layout_var = ctk.StringVar(
            value=layout_labels.get(
                current_layout,
                layout_labels.get("none", "Ingen automatisk utfylling"),
            )
        )

        workflow_labels = noark5_workflow_labels()
        self._workflow_labels = workflow_labels
        self._workflow_ids_by_label = {
            label: key for key, label in workflow_labels.items()
        }
        current_workflow = str(
            self.settings.get("noark5_discovery_workflow", "noark5_standard")
        )
        self.noark5_workflow_var = ctk.StringVar(
            value=workflow_labels.get(
                current_workflow,
                workflow_labels.get("none", "Ingen automatisk workflow"),
            )
        )

        body = _find_scrollable_frame(self)
        if body is None:
            return

        row = _next_free_row(body)

        ctk.CTkLabel(
            body,
            text="Automatisk jobboppsett",
            font=theme.font(theme.SECTION_SIZE, "bold"),
            text_color=theme.BLUE,
        ).grid(row=row, column=0, columnspan=2, padx=12, pady=(20, 8), sticky="w")
        row += 1

        ctk.CTkLabel(
            body,
            text="Mappeprofil",
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=row, column=0, padx=12, pady=8, sticky="w")
        ctk.CTkOptionMenu(
            body,
            variable=self.storage_layout_var,
            values=list(self._layout_ids_by_label),
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=row, column=1, padx=12, pady=8, sticky="ew")
        row += 1

        ctk.CTkLabel(
            body,
            text="Noark 5 workflow",
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=row, column=0, padx=12, pady=8, sticky="w")
        ctk.CTkOptionMenu(
            body,
            variable=self.noark5_workflow_var,
            values=list(self._workflow_ids_by_label),
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=row, column=1, padx=12, pady=8, sticky="ew")
        row += 1

        ctk.CTkLabel(
            body,
            text=(
                "Brukes ved «Finn jobber…». Standardvalget fyller kjente "
                "Source/Work/Storage-roller og legger til den kanoniske "
                "Noark 5-standardløypen fra config/workflow_sequences.json. "
                "U1/U2/regresjonskjøring inngår ikke i standardløypen."
            ),
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
            wraplength=610,
            justify="left",
        ).grid(row=row, column=0, columnspan=2, padx=12, pady=(0, 16), sticky="w")
        row += 1

        ctk.CTkLabel(
            body,
            text="Vindu",
            font=theme.font(theme.SECTION_SIZE, "bold"),
            text_color=theme.BLUE,
        ).grid(row=row, column=0, columnspan=2, padx=12, pady=(20, 8), sticky="w")
        row += 1

        ctk.CTkCheckBox(
            body,
            text="Start med samme vindusposisjon",
            variable=self.restore_position_var,
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=row, column=0, columnspan=2, padx=12, pady=4, sticky="w")
        row += 1

        ctk.CTkCheckBox(
            body,
            text="Start med samme vindusstørrelse",
            variable=self.restore_size_var,
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=row, column=0, columnspan=2, padx=12, pady=4, sticky="w")
        row += 1

        ctk.CTkCheckBox(
            body,
            text="Start maksimert hvis vinduet ble avsluttet maksimert",
            variable=self.restore_maximized_var,
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=row, column=0, columnspan=2, padx=12, pady=4, sticky="w")
        row += 1

        ctk.CTkLabel(
            body,
            text=(
                "Lagret posisjon brukes bare når vinduet fortsatt er synlig på dagens "
                "skjermoppsett. Maksimert tilstand tilpasses automatisk skjermen som "
                "er tilgjengelig ved oppstart."
            ),
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
            wraplength=610,
            justify="left",
        ).grid(row=row, column=0, columnspan=2, padx=12, pady=(2, 16), sticky="w")

    def _load_vars(self, settings: dict) -> None:
        super()._load_vars(settings)
        if hasattr(self, "restore_position_var"):
            self.restore_position_var.set(
                bool(settings.get("restore_main_window_position", True))
            )
            self.restore_size_var.set(
                bool(settings.get("restore_main_window_size", True))
            )
            self.restore_maximized_var.set(
                bool(settings.get("restore_main_window_maximized", True))
            )
        if hasattr(self, "storage_layout_var"):
            layout_id = str(settings.get("storage_layout_profile", "ikamr_standard"))
            self.storage_layout_var.set(
                self._layout_labels.get(
                    layout_id,
                    self._layout_labels.get("none", "Ingen automatisk utfylling"),
                )
            )
        if hasattr(self, "noark5_workflow_var"):
            workflow_id = str(
                settings.get("noark5_discovery_workflow", "noark5_standard")
            )
            self.noark5_workflow_var.set(
                self._workflow_labels.get(
                    workflow_id,
                    self._workflow_labels.get("none", "Ingen automatisk workflow"),
                )
            )

    def _collect(self) -> dict:
        updated = super()._collect()
        updated["restore_main_window_position"] = bool(
            self.restore_position_var.get()
        )
        updated["restore_main_window_size"] = bool(
            self.restore_size_var.get()
        )
        updated["restore_main_window_maximized"] = bool(
            self.restore_maximized_var.get()
        )
        updated["storage_layout_profile"] = self._layout_ids_by_label.get(
            self.storage_layout_var.get(), "none"
        )
        updated["noark5_discovery_workflow"] = self._workflow_ids_by_label.get(
            self.noark5_workflow_var.get(), "none"
        )
        return updated
