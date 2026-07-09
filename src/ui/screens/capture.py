"""Capture screen - live webcam preview, a preparation phase, then a countdown.

Flow on entry: live preview appears immediately with a "자세를 잡아주세요!" guide
for a few seconds, then a 3-2-1 countdown, a "찰칵!" beat, a white flash, and
finally the frame is captured and emitted via ``photo_captured``.

The CameraThread runs only while this screen is visible (show/hide events).
"""

from __future__ import annotations

import cv2
import numpy as np

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from src.camera.camera_thread import CameraThread
from src.ui import theme
from src.utils.config import get_config
from src.utils.logger import get_logger
from src.utils.sound import SoundPlayer

log = get_logger(__name__)

_PREVIEW_W = 800
_PREVIEW_H = 600
_FLASH_MS = 200   # 흰색 셔터 플래시 지속
_SNAP_MS = 500    # "찰칵!" 표시 후 실제 캡처까지


class CaptureScreen(QWidget):
    """Live preview + prepare + countdown. Emits ``photo_captured(np.ndarray)``."""

    photo_captured = pyqtSignal(np.ndarray)
    camera_failed = pyqtSignal()  # 재시도 모두 실패 -> 대기 화면 복귀 요청

    def __init__(self) -> None:
        super().__init__()
        theme.apply_background(self, theme.DARK)
        cfg = get_config()
        # 인덱스를 넘기지 않아야 CameraThread가 preferred_name 이름 매칭을 사용
        # (가상 카메라가 index 0을 차지하는 경우가 있음)
        self.camera = CameraThread()
        self.sound = SoundPlayer()

        self._first_frame_seen = False  # 첫 프레임 도착 전에는 카운트다운 금지
        self._prepare_ms = int(float(cfg.get("capture.prepare_seconds", 5)) * 1000)
        self._countdown_start = int(cfg.get("capture.countdown_seconds", 3))
        self.count = self._countdown_start

        # 카메라 재시도 설정
        self._camera_max = int(cfg.get("retry.camera_max_attempts", 3))
        self._camera_delay = int(cfg.get("retry.camera_retry_delay_ms", 1000))
        self._camera_attempts = 0

        # 감정 안정화용 버스트 프레임 수
        self._emotion_frames = int(cfg.get("analysis.emotion_frames", 5))
        self.captured_burst: list = []

        # 준비 타이머(단발) + 카운트다운 타이머(1초 반복)
        self._prepare_timer = QTimer(self)
        self._prepare_timer.setSingleShot(True)
        self._prepare_timer.timeout.connect(self.start_countdown)
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self.tick)

        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)

        # 프리뷰 + 카운트다운 숫자를 같은 셀에 겹쳐 배치
        host = QWidget()
        grid = QGridLayout(host)
        grid.setContentsMargins(0, 0, 0, 0)

        self.preview = QLabel("카메라를 준비하고 있어요...")
        self.preview.setFixedSize(_PREVIEW_W, _PREVIEW_H)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet(
            "background:#3A5563; border-radius:16px;"
            f"font-family:'{theme.FONT_FAMILY}'; font-size:28px; color:{theme.WHITE};"
        )
        grid.addWidget(self.preview, 0, 0, Qt.AlignmentFlag.AlignCenter)

        self.number = QLabel(str(self.count))
        self.number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number.setStyleSheet(theme.label_style(300, theme.WHITE))
        grid.addWidget(self.number, 0, 0, Qt.AlignmentFlag.AlignCenter)

        outer.addWidget(host, alignment=Qt.AlignmentFlag.AlignHCenter)
        outer.addSpacing(30)

        # 하단 안내 문구 (준비 시간 동안 표시)
        self.guide = QLabel("자세를 잡아주세요!")
        self.guide.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.guide.setStyleSheet(theme.label_style(60, theme.WHITE))
        outer.addWidget(self.guide, alignment=Qt.AlignmentFlag.AlignHCenter)

        outer.addStretch(1)

        # 셔터 플래시 (전체 화면 흰색, 평소 숨김)
        self.flash = QWidget(self)
        self.flash.setStyleSheet(f"background:{theme.WHITE};")
        self.flash.hide()

    # ---- 화면 표시/숨김에 따른 카메라 생명주기 -------------------------
    def showEvent(self, event) -> None:
        super().showEvent(event)
        # 초기 상태: 프리뷰 + 안내 문구, 숫자 숨김
        self.preview.setText("카메라를 준비하고 있어요...")
        self.guide.show()
        self.number.hide()
        self.flash.hide()
        self.count = self._countdown_start
        self._camera_attempts = 0
        self._first_frame_seen = False

        self.camera.frame_ready.connect(self.update_preview)
        self.camera.error.connect(self.on_camera_error)
        self.camera.begin()

        # 준비 타이머는 첫 프레임이 들어온 뒤 시작 (카메라 오픈이 느린 백엔드 대비).
        # 그 전에 카운트다운이 돌면 검은 프레임이 찍힌다.

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._prepare_timer.stop()
        self._countdown_timer.stop()
        self.camera.stop()
        for sig, slot in (
            (self.camera.frame_ready, self.update_preview),
            (self.camera.error, self.on_camera_error),
        ):
            try:
                sig.disconnect(slot)
            except TypeError:
                pass  # 이미 해제됨

    # ---- 프레임 표시 ---------------------------------------------------
    def update_preview(self, frame: np.ndarray) -> None:
        """Slot: show a live BGR frame (runs on the UI thread - keep light)."""
        if not self._first_frame_seen:
            self._first_frame_seen = True
            log.info("첫 프레임 수신 -> 준비 타이머 시작")
            self._prepare_timer.start(self._prepare_ms)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(img).scaled(
            self.preview.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview.setPixmap(pix)

    def on_camera_error(self, message: str) -> None:
        """Slot: camera error - retry a few times, then bail to attract."""
        self._camera_attempts += 1
        log.warning(
            "카메라 오류(%d/%d): %s", self._camera_attempts, self._camera_max, message
        )
        if self._camera_attempts < self._camera_max:
            self.preview.setText("카메라를 준비 중입니다...")
            QTimer.singleShot(self._camera_delay, self._retry_camera)
        else:
            self.preview.setText("카메라 연결을 확인해주세요")
            QTimer.singleShot(1500, self.camera_failed.emit)

    def _retry_camera(self) -> None:
        """Restart the camera thread (only while this screen is visible)."""
        if not self.isVisible():
            return
        log.info("카메라 재시도 %d/%d", self._camera_attempts, self._camera_max)
        self._first_frame_seen = False
        self.camera.stop()
        self.camera.begin()

    # ---- 준비 -> 카운트다운 -> 촬영 ------------------------------------
    def start_countdown(self) -> None:
        """After the prepare phase: hide the guide and count down 3-2-1."""
        self.guide.hide()
        self.number.setStyleSheet(theme.label_style(300, theme.WHITE))
        self.number.show()
        self.count = self._countdown_start
        self.tick()  # 첫 숫자 즉시 표시
        self._countdown_timer.start(theme.COUNTDOWN_INTERVAL_MS)

    def tick(self) -> None:
        if self.count > 0:
            self.number.setText(str(self.count))
            self.count -= 1
        else:
            self._countdown_timer.stop()
            self.number.setStyleSheet(theme.label_style(200, theme.WHITE))
            self.number.setText("찰칵!")
            QTimer.singleShot(_SNAP_MS, self.capture_photo)

    def capture_photo(self) -> None:
        """Flash, grab a burst of frames, play the shutter, and emit the photo."""
        # 감정 안정화용 최근 N프레임 확보 (마지막 프레임을 대표 사진으로)
        burst = self.camera.get_recent_frames(self._emotion_frames)
        frame = burst[-1] if burst else self.camera.get_latest_frame()
        self.sound.shutter()

        # 흰색 플래시 200ms
        self.number.hide()
        self.flash.setGeometry(self.rect())
        self.flash.show()
        self.flash.raise_()
        QTimer.singleShot(_FLASH_MS, self.flash.hide)

        if frame is None:
            # 카메라 미연결 등: 크래시 대신 검은 프레임으로 흐름 유지
            log.warning("캡처할 프레임이 없어 검은 프레임으로 대체")
            frame = np.zeros((_PREVIEW_H, _PREVIEW_W, 3), dtype=np.uint8)
            burst = [frame]

        self.captured_burst = burst
        log.info("사진 캡처 완료 (대표 shape=%s, 버스트 %d장)", frame.shape, len(burst))
        # 플래시가 잠깐 보인 뒤 다음 화면으로
        QTimer.singleShot(_FLASH_MS, lambda: self.photo_captured.emit(frame))


if __name__ == "__main__":
    # 단독 테스트: 준비 -> 카운트다운 -> 캡처 (창 모드)
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    screen = CaptureScreen()
    screen.photo_captured.connect(
        lambda f: print(f"[signal] photo_captured shape={f.shape}")
    )
    screen.resize(1280, 720)
    screen.show()
    sys.exit(app.exec())
