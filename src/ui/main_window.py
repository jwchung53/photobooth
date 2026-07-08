"""Main kiosk window - hosts the 5 screens in a QStackedWidget and wires
their signals into the attract -> capture -> analysis -> preview -> printing
flow. Frameless full-screen; ESC quits.

The camera lives inside the capture screen (started/stopped via its show/hide
events); here we just relay the captured photo forward.
"""

from __future__ import annotations

import numpy as np

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QMainWindow, QStackedWidget, QWidget

from src.ui.screens.analysis import AnalysisScreen
from src.ui.screens.attract import AttractScreen
from src.ui.screens.capture import CaptureScreen
from src.ui.screens.preview import PreviewScreen
from src.ui.screens.printing import PrintingScreen
from src.utils.logger import get_logger

log = get_logger(__name__)


class MainWindow(QMainWindow):
    """Kiosk shell managing screen transitions via signals."""

    # 백그라운드 워밍업 완료 알림 (워커 스레드 -> UI 스레드, 큐 연결)
    warmup_ready = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("감정 포토부스")
        self.captured_photo: np.ndarray | None = None  # 다음 Phase(분석)에서 사용

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # 5개 화면 생성 및 등록
        self.attract = AttractScreen()
        self.capture = CaptureScreen()
        self.analysis = AnalysisScreen()
        self.preview = PreviewScreen()
        self.printing = PrintingScreen()
        for screen in (
            self.attract,
            self.capture,
            self.analysis,
            self.preview,
            self.printing,
        ):
            self.stack.addWidget(screen)

        self._wire_signals()

        # 프레임리스 (풀스크린은 showFullScreen 호출 시 적용)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)

        # ESC 종료
        self._esc = QShortcut(QKeySequence("Esc"), self)
        self._esc.activated.connect(self.close)

        # 워밍업 완료 전까지 촬영 버튼 비활성화
        self.attract.set_ready(False)
        self.warmup_ready.connect(lambda: self.attract.set_ready(True))

        self.stack.setCurrentWidget(self.attract)

    def _wire_signals(self) -> None:
        """Connect each screen's signal to the next screen transition."""
        self.attract.start_capture.connect(lambda: self._go(self.capture))
        self.capture.photo_captured.connect(self.on_photo_captured)
        self.analysis.analysis_complete.connect(self.on_analysis_complete)
        self.analysis.analysis_failed.connect(lambda: self._go(self.attract))
        self.preview.print_start.connect(lambda: self._go(self.printing))
        self.preview.restart.connect(lambda: self._go(self.attract))
        self.printing.return_to_attract.connect(lambda: self._go(self.attract))

    def on_photo_captured(self, frame: np.ndarray) -> None:
        """Store the captured photo and move on to the analysis screen."""
        self.captured_photo = frame
        self.analysis.set_photo(frame)
        log.info("사진 수신 (shape=%s) -> 분석 화면", frame.shape)
        self._go(self.analysis)

    def on_analysis_complete(self, photo: np.ndarray, results: list) -> None:
        """Pass analysis results to the preview screen and show it."""
        log.info("분석 완료 수신 (%d명) -> 미리보기", len(results))
        self.preview.set_results(photo, results)
        self._go(self.preview)

    def _go(self, screen: QWidget) -> None:
        """Switch to a screen and kick off its animation, if any."""
        self.stack.setCurrentWidget(screen)
        log.info("화면 전환: %s", screen.__class__.__name__)
        start = getattr(screen, "start", None)
        if callable(start):
            start()

    def closeEvent(self, event) -> None:
        """Ensure the camera thread is stopped on shutdown."""
        self.capture.camera.stop()
        super().closeEvent(event)


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = MainWindow()
    window.showFullScreen()
    sys.exit(app.exec())
