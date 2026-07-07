"""Capture screen - dummy preview with a 3-2-1 countdown then a flash."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QGridLayout, QLabel, QWidget

from src.ui import theme


class CaptureScreen(QWidget):
    """Runs a countdown on entry, then emits ``analysis_needed``."""

    analysis_needed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        theme.apply_background(self, theme.DARK)
        self._count = theme.COUNTDOWN_START
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._build()

    def _build(self) -> None:
        # 프리뷰 자리와 큰 숫자를 같은 셀에 겹쳐 배치
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)

        self.preview = QLabel()
        self.preview.setFixedSize(800, 600)
        self.preview.setStyleSheet("background:#3A5563; border-radius:16px;")
        grid.addWidget(self.preview, 0, 0, Qt.AlignmentFlag.AlignCenter)

        self.number = QLabel(str(self._count))
        self.number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number.setStyleSheet(theme.label_style(300, theme.WHITE))
        grid.addWidget(self.number, 0, 0, Qt.AlignmentFlag.AlignCenter)

    def start(self) -> None:
        """Reset and begin the countdown (called on screen entry)."""
        self._count = theme.COUNTDOWN_START
        self.number.setStyleSheet(theme.label_style(300, theme.WHITE))
        self.number.setText(str(self._count))
        self._timer.start(theme.COUNTDOWN_INTERVAL_MS)

    def _tick(self) -> None:
        self._count -= 1
        if self._count > 0:
            self.number.setText(str(self._count))
        else:
            self._timer.stop()
            # "찰칵!"을 잠깐 보여준 뒤 분석 화면으로
            self.number.setStyleSheet(theme.label_style(180, theme.WHITE))
            self.number.setText("찰칵!")
            QTimer.singleShot(theme.FLASH_MS, self.analysis_needed.emit)


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    screen = CaptureScreen()
    screen.analysis_needed.connect(lambda: print("[signal] analysis_needed"))
    screen.resize(1280, 720)
    screen.show()
    screen.start()
    sys.exit(app.exec())
