from __future__ import annotations

import weakref

import customtkinter as ctk

CATEGORIES = [
    "Pipeline", "Integritet", "Sikkerhet", "Innhold", "Systemspesifikt",
    "Kompatibilitet", "Rapport", "Metadata", "SIP/AIC-Pakking",
]

CATEGORY_COLORS = {
    "Pipeline": "#4f8ef7", "Integritet": "#4f8ef7", "Sikkerhet": "#e05252",
    "Innhold": "#f0c040", "Systemspesifikt": "#4f8ef7", "Kompatibilitet": "#4f8ef7",
    "Rapport": "#f97316", "Metadata": "#a78bfa", "SIP/AIC-Pakking": "#4f8ef7",
}

APP_BG = "#0d0f14"
SURFACE_BG = "#13161e"
PANEL_BG = "#191d28"
PANEL_BG_DARK = "#0d1017"
DROPZONE_BG = "#1a2640"
CARD_BG = "#191d28"
CARD_BORDER = "#252b3a"
TEXT = "#d4daf0"
TEXT_MAIN = TEXT
TEXT_SUB = "#b7bcc8"
TEXT_MUTED = "#8a95b0"
BLUE = "#4f8ef7"
BLUE_DIM = "#3a70d4"
BUTTON_BG = "#1e2333"
BUTTON_HOVER = "#252b3a"
DANGER_BG = "#2a1515"
DANGER_TEXT = "#e05252"

TOOLTIP_DARK_BG = "#2a3142"
TOOLTIP_DARK_TEXT = "#f4f7ff"
TOOLTIP_DARK_BORDER = "#526079"
TOOLTIP_LIGHT_BG = "#d9dee8"
TOOLTIP_LIGHT_TEXT = "#172033"
TOOLTIP_LIGHT_BORDER = "#8b96a8"

FONT_FAMILY = "Courier New"
TITLE_SIZE = 13
SECTION_SIZE = 10
NORMAL_SIZE = 10
SMALL_SIZE = 9

# Semantic aliases used by newer dialogs. Keep the established base sizes
# authoritative while allowing dialogs to describe font roles explicitly.
HEADER_SIZE = TITLE_SIZE
BODY_SIZE = NORMAL_SIZE

TOOLTIP_SIZE = 10
FONT_MIN_SIZE = 10

HEADER_HEIGHT = 48
LEFT_WIDTH = 390
OPERATIONS_HEIGHT = 142
STATUS_HEIGHT = 24


class FontRegistry:
    """SIARD-lik fontskalering for alle registrerte CTkFont-objekter."""

    _fonts: list[tuple[weakref.ReferenceType, int]] = []
    _offset: int = 0

    @classmethod
    def _apply(cls) -> None:
        dead: list[int] = []
        for index, (font_ref, base_size) in enumerate(cls._fonts):
            font_obj = font_ref()
            if font_obj is None:
                dead.append(index)
                continue
            try:
                font_obj.configure(size=cls.effective_size(base_size))
            except Exception:
                pass
        for index in reversed(dead):
            del cls._fonts[index]

    @classmethod
    def effective_size(cls, base_size: int) -> int:
        return max(FONT_MIN_SIZE, int(base_size) + cls._offset)

    @classmethod
    def scale(cls, delta: int) -> None:
        cls._offset = max(-3, min(8, cls._offset + int(delta)))
        cls._apply()

    @classmethod
    def current_offset(cls) -> int:
        return cls._offset

    @classmethod
    def set_offset(cls, offset: int) -> None:
        cls._offset = max(-3, min(8, int(offset)))
        cls._apply()


def font(size: int, weight: str = "normal", family: str | None = None) -> ctk.CTkFont:
    """Lag en font som automatisk følger global A-/A+ skalering."""
    obj = ctk.CTkFont(
        family=family or FONT_FAMILY,
        size=FontRegistry.effective_size(size),
        weight=weight,
    )
    FontRegistry._fonts.append((weakref.ref(obj), int(size)))
    return obj


def tooltip_colors() -> tuple[str, str, str]:
    """Return background, text and border for the current appearance mode."""
    try:
        light = ctk.get_appearance_mode().lower() == "light"
    except Exception:
        light = False
    if light:
        return TOOLTIP_LIGHT_BG, TOOLTIP_LIGHT_TEXT, TOOLTIP_LIGHT_BORDER
    return TOOLTIP_DARK_BG, TOOLTIP_DARK_TEXT, TOOLTIP_DARK_BORDER


def apply_theme() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
