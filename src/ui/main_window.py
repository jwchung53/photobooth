"""Main kiosk window - hosts the 5 screens and enforces kiosk behavior.

Screen flow: attract -> capture -> analysis -> preview -> printing. On top of
that this window adds kiosk-mode safety: frameless full-screen (stay-on-top),
admin-only exit (Ctrl+Shift+Q with confirm; ESC/Alt+F4 ignored), idle
auto-reset to the attract screen, and error auto-recovery.
"""

from __future__ import annotations

import numpy as np

from PyQt6.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QWidget,
)

from src.ui.screens.analysis import AnalysisScreen
from src.ui.screens.attract import AttractScreen
from src.ui.screens.capture import CaptureScreen
from src.ui.screens.preview import PreviewScreen
from src.ui.screens.printing import PrintingScreen
from src.utils import kiosk_utils
from src.utils.config import get_config
from src.utils.idle_timer import IdleTimer
from src.utils.logger import get_logger

log = get_logger(__name__)


class MainWindow(QMainWindow):
    """Kiosk shell: screen transitions + kiosk safety behaviors."""

    # 백그라운드 워밍업 완료 알림 (워커 스레드 -> UI 스레드, 큐 연결)
    warmup_ready = pyqtSignal()

    # 무입력 판별용 사용자 입력 이벤트
    _INPUT_EVENTS = frozenset({
        QEvent.Type.MouseMove,
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseButtonDblClick,
        QEvent.Type.KeyPress,
        QEvent.Type.Wheel,
        QEvent.Type.TouchBegin,
    })

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("감정 포토부스")
        self.captured_photo: np.ndarray | None = None

        cfg = get_config()
        self._hide_cursor = bool(cfg.get("kiosk.hide_cursor", True))
        self._auto_reset_on_error = bool(cfg.get("kiosk.auto_reset_on_error", True))
        self._error_ms = int(cfg.get("kiosk.error_display_seconds", 3)) * 1000
        self._allow_close = False

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # 5개 화면 생성 및 등록
        self.attract = AttractScreen()
        self.capture = CaptureScreen()
        self.analysis = AnalysisScreen()
        self.preview = PreviewScreen()
        self.printing = PrintingScreen()
        for screen in (
            self.attract, self.capture, self.analysis, self.preview, self.printing,
        ):
            self.stack.addWidget(screen)

        # 카메라 프레임 -> 촬영 화면
        self.camera = self.capture.camera
        self._wire_signals()

        # ---- 키오스크 모드 ----
        flags = Qt.WindowType.FramelessWindowHint
        if bool(cfg.get("kiosk.stay_on_top", True)):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)

        # 무입력 자동 복귀 타이머 + 앱 전체 입력 감지
        self.idle = IdleTimer(int(cfg.get("kiosk.idle_timeout_ms", 60000)), self)
        self.idle.idle_timeout.connect(self._on_idle)
        self.idle.start()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        # 워밍업 완료 전까지 촬영 버튼 비활성화
        self.attract.set_ready(False)
        self.warmup_ready.connect(lambda: self.attract.set_ready(True))

        self.stack.setCurrentWidget(self.attract)

    # ---- 시그널 배선 ---------------------------------------------------
    def _wire_signals(self) -> None:
        self.attract.start_capture.connect(lambda: self._go(self.capture))
        self.capture.photo_captured.connect(self.on_photo_captured)
        self.capture.camera_failed.connect(lambda: self._go(self.attract))
        self.analysis.analysis_complete.connect(self.on_analysis_complete)
        self.analysis.analysis_failed.connect(lambda: self._go(self.attract))
        self.analysis.retake.connect(lambda: self._go(self.capture))
        self.preview.print_start.connect(lambda: self._go(self.printing))
        self.preview.restart.connect(lambda: self._go(self.attract))
        self.printing.return_to_attract.connect(lambda: self._go(self.attract))

    # ---- 화면 전환 (에러 복구 래퍼) ------------------------------------
    def _go(self, screen: QWidget) -> None:
        try:
            self.stack.setCurrentWidget(screen)
            log.info("화면 전환: %s", screen.__class__.__name__)
            start = getattr(screen, "start", None)
            if callable(start):
                start()
        except Exception:  # noqa: BLE001 - 절대 크래시 금지
            log.exception("화면 전환/시작 오류")
            if screen is not self.attract:
                self._recover_to_attract()

    def on_photo_captured(self, frame: np.ndarray) -> None:
        try:
            self.captured_photo = frame
            # 감정 안정화용 버스트 프레임을 함께 전달
            self.analysis.set_photo(frame, self.capture.captured_burst)
            log.info("사진 수신 (shape=%s) -> 분석 화면", frame.shape)
            self._go(self.analysis)
        except Exception:  # noqa: BLE001
            log.exception("촬영 처리 오류")
            self._recover_to_attract()

    def on_analysis_complete(self, photo: np.ndarray, results: list) -> None:
        try:
            log.info("분석 완료 수신 (%d명) -> 미리보기", len(results))
            self.preview.set_results(photo, results)
            self._go(self.preview)
        except Exception:  # noqa: BLE001
            log.exception("결과 표시 오류")
            self._recover_to_attract()

    def _recover_to_attract(self) -> None:
        """Log-and-recover: return to the attract screen after a short delay."""
        if not self._auto_reset_on_error:
            return
        log.info("에러 복구 -> %d초 후 대기 화면", self._error_ms // 1000)
        QTimer.singleShot(self._error_ms, lambda: self.stack.setCurrentWidget(self.attract))

    # ---- 무입력 자동 복귀 ----------------------------------------------
    def eventFilter(self, obj, event) -> bool:
        et = event.type()
        if et in self._INPUT_EVENTS:
            self.idle.reset()
            if et == QEvent.Type.KeyPress and self._is_admin_quit(event):
                self._confirm_and_quit()
                return True
        return super().eventFilter(obj, event)

    def _on_idle(self) -> None:
        if self.stack.currentWidget() is not self.attract:
            log.info("무입력 %d초 -> 대기 화면 복귀", self.idle.timeout_ms // 1000)
            self._go(self.attract)

    # ---- 관리자 종료 ---------------------------------------------------
    @staticmethod
    def _is_admin_quit(event) -> bool:
        mods = event.modifiers()
        return (
            event.key() == Qt.Key.Key_Q
            and bool(mods & Qt.KeyboardModifier.ControlModifier)
            and bool(mods & Qt.KeyboardModifier.ShiftModifier)
        )

    def _confirm_and_quit(self) -> None:
        # 대화상자 동안 커서를 잠깐 복원
        kiosk_utils.show_cursor()
        reply = QMessageBox.question(
            self,
            "종료 확인",
            "정말 종료하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            log.info("관리자 종료 승인")
            self._allow_close = True
            self.close()
        elif self._hide_cursor:
            kiosk_utils.hide_cursor()

    def closeEvent(self, event) -> None:
        # 관리자 승인(_allow_close) 없이는 종료 차단 (Alt+F4 등 무시)
        if not self._allow_close:
            log.info("종료 시도 차단 (Ctrl+Shift+Q로만 종료)")
            event.ignore()
            return
        log.info("앱 종료 - 리소스 정리")
        try:
            self.idle.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.capture.camera.stop()
        except Exception:  # noqa: BLE001
            pass
        super().closeEvent(event)


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    window = MainWindow()
    window.showFullScreen()
    sys.exit(app.exec())
