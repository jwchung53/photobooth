"""Printing screen - dummy print progress, thank-you, then auto return."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

from src.ui import theme


class PrintingScreen(QWidget):
    """Fakes printing, shows a thank-you, then emits ``return_to_attract``."""

    return_to_attract = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        theme.apply_background(self, theme.DARK)
        self._progress = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(120, 0, 120, 0)
        layout.addStretch(2)

        self.title = QLabel("인쇄 중입니다...")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet(theme.label_style(60, theme.WHITE))
        layout.addWidget(self.title)

        layout.addSpacing(40)

        self.bar = QProgressBar()
        self.bar.setRange(0, theme.PROGRESS_STEPS)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setStyleSheet(theme.progressbar_style(theme.GREEN))
        layout.addWidget(self.bar)

        layout.addSpacing(24)

        self.status = QLabel(f"1/{theme.PRINT_COUNT} 인쇄 중...")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet(theme.label_style(28, theme.WHITE, bold=False))
        layout.addWidget(self.status)

        layout.addStretch(3)

    def start(self) -> None:
        """Reset and begin the printing animation (called on entry)."""
        self._progress = 0
        self.title.setStyleSheet(theme.label_style(60, theme.WHITE))
        self.title.setText("인쇄 중입니다...")
        self.bar.setValue(0)
        self.bar.show()
        self.status.setText(f"1/{theme.PRINT_COUNT} 인쇄 중...")
        self.status.show()
        self._timer.start(theme.PROGRESS_TICK_MS)

    def _tick(self) -> None:
        self._progress += 1
        self.bar.setValue(self._progress)

        # 진행률 -> 현재 인쇄 매수 (1..PRINT_COUNT)
        step = theme.PROGRESS_STEPS // theme.PRINT_COUNT
        photo = min(theme.PRINT_COUNT, self._progress // step + 1)
        self.status.setText(f"{photo}/{theme.PRINT_COUNT} 인쇄 중...")

        if self._progress >= theme.PROGRESS_STEPS:
            self._timer.stop()
            self._show_thanks()

    def _show_thanks(self) -> None:
        self.title.setStyleSheet(theme.label_style(80, theme.WHITE))
        self.title.setText("감사합니다!")
        self.bar.hide()
        self.status.hide()
        QTimer.singleShot(theme.THANK_YOU_RETURN_MS, self.return_to_attract.emit)


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
