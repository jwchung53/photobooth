"""Printing screen - placeholder until Phase 5 adds real printing.

Shows a "coming soon" message and auto-returns to the attract screen so the
kiosk flow stays intact.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from src.ui import theme

_RETURN_MS = 5000  # 안내 후 대기 화면 복귀까지


class PrintingScreen(QWidget):
    """Dummy print screen. Emits ``return_to_attract`` after a short message."""

    return_to_attract = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        theme.apply_background(self, theme.DARK)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.return_to_attract.emit)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.addStretch(1)

        title = QLabel("인쇄 기능은 준비 중입니다")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(theme.label_style(60, theme.WHITE))
        layout.addWidget(title)

        layout.addSpacing(24)

        sub = QLabel("다음 업데이트에서 제공돼요. 잠시 후 처음 화면으로 돌아갑니다.")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(theme.label_style(28, theme.WHITE, bold=False))
        layout.addWidget(sub)

        layout.addStretch(1)

    def start(self) -> None:
        """Begin the auto-return countdown (called on screen entry)."""
        self._timer.start(_RETURN_MS)


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    screen = PrintingScreen()
    screen.return_to_attract.connect(lambda: print("[signal] return_to_attract"))
    screen.resize(1280, 720)
    screen.show()
    screen.start()
    sys.exit(app.exec())
