"""Shared UI theme tokens and stylesheet helpers for the kiosk screens.

Centralizes the color palette, font, and animation timings so individual
screens stay free of magic values (per the project coding rules).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

# ---- 컬러 팔레트 -------------------------------------------------------
ORANGE = "#F4A261"
PINK = "#E85D75"
DARK = "#264653"
GREEN = "#2A9D8F"
SOFT = "#FFF8F3"
WHITE = "#FFFFFF"
GRAY = "#CCCCCC"
GRAY_BTN = "#8D99AE"

# ---- 폰트 --------------------------------------------------------------
FONT_FAMILY = "맑은 고딕"

# ---- 애니메이션 타이밍 (ms) --------------------------------------------
COUNTDOWN_START = 3
COUNTDOWN_INTERVAL_MS = 1000
FLASH_MS = 500
PROGRESS_TICK_MS = 30           # 진행바 1틱 간격
PROGRESS_STEPS = 100            # 0~100 -> 총 3초 (30ms * 100)
THANK_YOU_RETURN_MS = 5000      # "감사합니다!" 후 대기화면 복귀까지


def apply_background(widget: QWidget, color: str) -> None:
    """Paint a solid background scoped to this widget only (not children)."""
    name = widget.__class__.__name__
    widget.setObjectName(name)
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    widget.setStyleSheet(f"#{name} {{ background-color: {color}; }}")


def label_style(size_px: int, color: str, bold: bool = True) -> str:
    """QSS for a transparent text label."""
    weight = "bold" if bold else "normal"
    return (
        f"font-family:'{FONT_FAMILY}'; font-size:{size_px}px; "
        f"color:{color}; font-weight:{weight}; background:transparent;"
    )


def button_style(
    bg: str,
    fg: str = WHITE,
    size_px: int = 28,
    radius: int = 20,
    padding: str = "18px 44px",
) -> str:
    """QSS for a rounded push button."""
    return (
        "QPushButton {"
        f"background-color:{bg}; color:{fg};"
        f"font-family:'{FONT_FAMILY}'; font-size:{size_px}px; font-weight:bold;"
        f"border:none; border-radius:{radius}px; padding:{padding};"
        "}"
        f"QPushButton:hover {{ background-color:{bg}; border:3px solid {WHITE}; }}"
    )


def progressbar_style(chunk_color: str) -> str:
    """QSS for a rounded progress bar with a colored chunk."""
    return (
        "QProgressBar {"
        f"background-color:{WHITE}; border:2px solid {GRAY}; border-radius:16px;"
        "height:32px; text-align:center;"
        f"font-family:'{FONT_FAMILY}'; font-size:16px; color:{DARK};"
        "}"
        f"QProgressBar::chunk {{ background-color:{chunk_color}; border-radius:14px; }}"
    )
