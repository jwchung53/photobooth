"""Analysis screen - runs real emotion analysis on the captured photo.

Shows the photo, overlays a face box per detection and an emotion emoji per
classification (with a fade-in), and drives a real progress bar from the
AnalysisThread. Emits ``analysis_complete(photo, results)`` when done, or
``analysis_failed`` after showing a friendly error.
"""

from __future__ import annotations

import cv2
import numpy as np

from PyQt6.QtCore import Qt, QPropertyAnimation, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QGraphicsOpacityEffect,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.analysis.analysis_thread import AnalysisThread
from src.analysis.emotion import EMOTION_EMOJI
from src.ui import theme
from src.utils.logger import get_logger

log = get_logger(__name__)

_DISP_W = 960
_DISP_H = 540
_ERROR_RETURN_MS = 5000  # 에러 후 자동 대기 화면 복귀까지


class AnalysisScreen(QWidget):
    """Live analysis view. Emits ``analysis_complete`` / ``analysis_failed``."""

    analysis_complete = pyqtSignal(np.ndarray, list)
    analysis_failed = pyqtSignal()   # 자동 대기 화면 복귀
    retake = pyqtSignal()            # [다시 찍기] -> 촬영 화면

    def __init__(self) -> None:
        super().__init__()
        theme.apply_background(self, theme.SOFT)
        self._photo: np.ndarray | None = None
        self._frames: list = []
        self.analysis_results: list[dict] = []
        self._thread: AnalysisThread | None = None
        # 에러 시 자동 복귀 타이머
        self._error_timer = QTimer(self)
        self._error_timer.setSingleShot(True)
        self._error_timer.timeout.connect(self.analysis_failed.emit)

        # 오버레이 상태
        self._scale = 1.0
        self._offx = 0
        self._offy = 0
        self._base_pix: QPixmap | None = None
        self._work_pix: QPixmap | None = None
        self._boxes: dict[int, tuple] = {}
        self._emoji_labels: list[QLabel] = []
        self._anims: list[QPropertyAnimation] = []

        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 30, 60, 30)
        layout.addStretch(1)

        self.title = QLabel("감정을 분석하고 있어요...")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet(theme.label_style(48, theme.DARK))
        layout.addWidget(self.title)

        layout.addSpacing(20)

        # 사진 + 오버레이 호스트
        self.photo_host = QWidget()
        self.photo_host.setFixedSize(_DISP_W, _DISP_H)
        self.photo_label = QLabel(self.photo_host)
        self.photo_label.setGeometry(0, 0, _DISP_W, _DISP_H)
        self.photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo_label.setStyleSheet("background:#EADFD5; border-radius:12px;")
        layout.addWidget(self.photo_host, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addSpacing(24)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setStyleSheet(theme.progressbar_style(theme.ORANGE))
        layout.addWidget(self.bar)

        layout.addSpacing(16)

        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet(theme.label_style(28, theme.PINK, bold=False))
        layout.addWidget(self.status)

        layout.addSpacing(16)

        # 에러 시에만 표시되는 [다시 찍기] 버튼
        self.retry_btn = QPushButton("다시 찍기")
        self.retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retry_btn.setStyleSheet(theme.button_style(theme.PINK, size_px=28))
        self.retry_btn.clicked.connect(self._on_retry_clicked)
        self.retry_btn.hide()
        layout.addWidget(self.retry_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch(1)

    # ---- 외부 연동 -----------------------------------------------------
    def set_photo(self, photo: np.ndarray, frames: list | None = None) -> None:
        """Store the captured photo + optional burst (before the screen shows)."""
        self._photo = photo
        self._frames = frames if frames else [photo]

    # ---- 생명주기 ------------------------------------------------------
    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._photo is None:
            log.warning("분석할 사진이 없습니다")
            self.analysis_failed.emit()
            return
        self._reset_overlays()
        self._prepare_display()
        self.title.setText("감정을 분석하고 있어요...")  # 이전 에러 메시지 초기화
        self.bar.setValue(0)
        self.status.setText("")
        self.retry_btn.hide()
        self._error_timer.stop()

        self._thread = AnalysisThread(self._photo, self._frames)
        self._thread.progress.connect(self.update_progress)
        self._thread.face_detected.connect(self.show_face_box)
        self._thread.emotion_detected.connect(self.show_emotion_icon)
        self._thread.finished_all.connect(self.on_analysis_done)
        self._thread.error_occurred.connect(self.on_error)
        self._thread.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        if self._thread is not None and self._thread.isRunning():
            self._thread.wait(3000)
        self._reset_overlays()

    def _reset_overlays(self) -> None:
        for lbl in self._emoji_labels:
            lbl.deleteLater()
        self._emoji_labels.clear()
        self._anims.clear()
        self._boxes.clear()

    def _prepare_display(self) -> None:
        photo = self._photo
        h, w = photo.shape[:2]
        self._scale = min(_DISP_W / w, _DISP_H / h)
        dw, dh = int(w * self._scale), int(h * self._scale)
        self._offx = (_DISP_W - dw) // 2
        self._offy = (_DISP_H - dh) // 2

        rgb = cv2.cvtColor(photo, cv2.COLOR_BGR2RGB)
        img = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(img).scaled(
            dw, dh, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self._base_pix = pix
        self._work_pix = pix.copy()
        self.photo_label.setPixmap(self._work_pix)

    # ---- 시그널 슬롯 ---------------------------------------------------
    def update_progress(self, percent: int, message: str) -> None:
        self.bar.setValue(percent)
        self.status.setText(message)

    def show_face_box(self, face_num: int, info: dict) -> None:
        """Draw a detection box on the photo (accumulating)."""
        if self._work_pix is None:
            return
        self._boxes[face_num] = info["bbox"]
        x, y, w, h = info["bbox"]
        painter = QPainter(self._work_pix)
        pen = QPen(QColor(theme.WHITE), max(3, self._work_pix.width() // 200))
        painter.setPen(pen)
        painter.drawRect(
            int(x * self._scale), int(y * self._scale),
            int(w * self._scale), int(h * self._scale),
        )
        painter.end()
        self.photo_label.setPixmap(self._work_pix)

    def show_emotion_icon(self, face_num: int, emotion: str, confidence: float) -> None:
        """Pop an emotion emoji above the face with a fade-in."""
        bbox = self._boxes.get(face_num)
        if bbox is None:
            return
        x, y, w, _h = bbox
        emoji = EMOTION_EMOJI.get(emotion, "😐")
        lbl = QLabel(emoji, self.photo_host)
        lbl.setStyleSheet("font-size:44px; background:transparent;")
        lbl.adjustSize()
        cx = self._offx + int((x + w / 2) * self._scale) - lbl.width() // 2
        cy = self._offy + int(y * self._scale) - lbl.height()
        lbl.move(max(0, cx), max(0, cy))
        lbl.show()

        effect = QGraphicsOpacityEffect(lbl)
        lbl.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(300)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start()

        self._emoji_labels.append(lbl)
        self._anims.append(anim)

    def on_analysis_done(self, results: list) -> None:
        self.analysis_results = results
        self.analysis_complete.emit(self._photo, results)

    def on_error(self, message: str) -> None:
        log.info("분석 에러 표시: %s", message)
        self.title.setText(message)
        self.status.setText("다시 찍거나, 잠시 후 처음 화면으로 돌아갑니다...")
        self.bar.setValue(0)
        self.retry_btn.show()
        self._error_timer.start(_ERROR_RETURN_MS)  # 5초 후 자동 대기 복귀

    def _on_retry_clicked(self) -> None:
        """User chose to re-shoot: cancel auto-return and go to capture."""
        self._error_timer.stop()
        self.retake.emit()


if __name__ == "__main__":
    # 단독 테스트: python -m src.ui.screens.analysis <이미지경로>
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    screen = AnalysisScreen()
    if len(sys.argv) > 1:
        img = cv2.imread(sys.argv[1])
        if img is not None:
            screen.set_photo(img)
    screen.analysis_complete.connect(
        lambda p, r: print(f"[signal] analysis_complete: {len(r)}명")
    )
    screen.analysis_failed.connect(lambda: print("[signal] analysis_failed"))
    screen.resize(1280, 720)
    screen.show()
    sys.exit(app.exec())
