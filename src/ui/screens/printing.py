"""Printing screen - prints the preview images, shows progress, then returns.

Falls back to a friendly message if printing is disabled or no images are set.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

from src.print.print_thread import PrintThread
from src.ui import theme
from src.utils.config import get_config
from src.utils.logger import get_logger

log = get_logger(__name__)

_DONE_RETURN_MS = 5000   # 완료/에러 후 대기 화면 복귀까지


class PrintingScreen(QWidget):
    """Prints images off-thread and emits ``return_to_attract`` when done."""

    return_to_attract = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        theme.apply_background(self, theme.DARK)
        self._images: list = []
        self._thread: PrintThread | None = None
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
        self.bar.setTextVisible(False)
        self.bar.setStyleSheet(theme.progressbar_style(theme.GREEN))
        layout.addWidget(self.bar)

        layout.addSpacing(24)

        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet(theme.label_style(28, theme.WHITE, bold=False))
        layout.addWidget(self.status)

        layout.addStretch(3)

    def set_images(self, images: list) -> None:
        """Store the images to print (called before the screen is shown)."""
        self._images = images or []

    def start(self) -> None:
        """Begin printing (called on screen entry)."""
        cfg = get_config()
        enabled = bool(cfg.get("print.enabled", True))

        # 인쇄 비활성 또는 이미지 없음 -> 안내 후 복귀
        if not enabled or not self._images:
            self.title.setText("인쇄 기능이 꺼져 있어요" if not enabled else "인쇄할 사진이 없어요")
            self.bar.hide()
            self.status.setText("잠시 후 처음 화면으로 돌아갑니다.")
            QTimer.singleShot(_DONE_RETURN_MS, self.return_to_attract.emit)
            return

        total = len(self._images)
        self.title.setText("인쇄 중입니다...")
        self.bar.show()
        self.bar.setRange(0, total)
        self.bar.setValue(0)
        self.status.setText(f"{total}장 준비 중...")

        self._thread = PrintThread(self._images)
        self._thread.progress.connect(self._on_progress)
        self._thread.finished_all.connect(self._on_done)
        self._thread.error.connect(self._on_error)
        self._thread.start()

    def _on_progress(self, current: int, total: int) -> None:
        self.bar.setValue(current)
        self.status.setText(f"{total}장 중 {current}장 인쇄 중...")

    def _on_done(self) -> None:
        self.title.setStyleSheet(theme.label_style(72, theme.WHITE))
        self.title.setText("인쇄 완료!")
        self.bar.hide()
        self.status.setText("사진을 가져가세요. 감사합니다!")
        QTimer.singleShot(_DONE_RETURN_MS, self.return_to_attract.emit)

    def _on_error(self, message: str) -> None:
        log.warning("인쇄 에러 표시: %s", message)
        self.title.setText(message)
        self.bar.hide()
        self.status.setText("잠시 후 처음 화면으로 돌아갑니다.")
        QTimer.singleShot(_DONE_RETURN_MS, self.return_to_attract.emit)


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    screen = PrintingScreen()
    screen.return_to_attract.connect(lambda: print("[signal] return_to_attract"))
    screen.resize(1280, 720)
    screen.show()
    screen.start()  # 이미지 없음 -> 안내 흐름
    sys.exit(app.exec())
