"""Background camera capture thread for the UI.

Opens a webcam with the DirectShow backend and streams BGR frames to the GUI
via ``frame_ready`` so the UI thread never blocks on camera I/O. Keeps the most
recent frame so the capture moment can grab a still with ``get_latest_frame``.
"""

from __future__ import annotations

import cv2
import numpy as np

from PyQt6.QtCore import QThread, pyqtSignal

from src.camera.camera_utils import find_available_camera
from src.utils.config import get_config
from src.utils.logger import get_logger

log = get_logger(__name__)


class CameraThread(QThread):
    """Streams webcam frames (BGR numpy arrays) via ``frame_ready``."""

    frame_ready = pyqtSignal(np.ndarray)  # BGR frame
    error = pyqtSignal(str)               # 사용자 친화 메시지

    def __init__(self, camera_index: int | None = None) -> None:
        super().__init__()
        cfg = get_config()
        # 인자 미지정 시 config의 camera.index 사용 (단일 진실 공급원)
        self.camera_index = (
            camera_index if camera_index is not None else int(cfg.get("camera.index", 0))
        )
        self.width = int(cfg.get("camera.width", 1280))
        self.height = int(cfg.get("camera.height", 720))
        self.fps = int(cfg.get("camera.fps", 30))
        self.warmup_frames = int(cfg.get("camera.warmup_frames", 5))
        self._running = False
        self._latest: np.ndarray | None = None

    def _open(self) -> cv2.VideoCapture | None:
        """Open the configured index; fall back to auto-detection."""
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            log.warning("카메라 index=%d 열기 실패, 다른 인덱스 탐색", self.camera_index)
            idx = find_available_camera()
            if idx is None:
                return None
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap.release()
                return None
            self.camera_index = idx
        return cap

    def run(self) -> None:  # QThread 진입점 (별도 스레드)
        cap = self._open()
        if cap is None:
            self.error.emit("카메라를 찾을 수 없어요. USB 연결을 확인해주세요.")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        log.info(
            "카메라 스트림 시작 (index=%d, %dx%d)",
            self.camera_index,
            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )

        # 노출/화이트밸런스 안정화를 위해 첫 프레임들은 버림
        for _ in range(self.warmup_frames):
            cap.read()

        interval_ms = int(1000 / max(1, self.fps))
        try:
            while self._running:
                ret, frame = cap.read()
                if not ret or frame is None:
                    # 일시적 실패: 로깅 후 계속 시도 (크래시 금지)
                    log.warning("프레임 읽기 실패, 재시도")
                    self.msleep(interval_ms)
                    continue
                self._latest = frame
                # 소비자(GUI 스레드)가 안전하게 쓰도록 복사본 전달
                self.frame_ready.emit(frame.copy())
                self.msleep(interval_ms)
        finally:
            cap.release()
            log.info("카메라 스트림 종료")

    def get_latest_frame(self) -> np.ndarray | None:
        """Return a copy of the most recent frame (for the capture moment)."""
        return None if self._latest is None else self._latest.copy()

    def begin(self) -> None:
        """Start streaming (idempotent)."""
        if not self.isRunning():
            self._running = True
            self._latest = None
            self.start()

    def stop(self) -> None:
        """Stop streaming and wait for the thread to finish."""
        self._running = False
        self.wait(2000)


if __name__ == "__main__":
    # 단독 테스트: 라이브 프리뷰 창 (카메라 없으면 안내만 출력)
    import sys

    from PyQt6.QtGui import QImage, QPixmap
    from PyQt6.QtWidgets import QApplication, QLabel

    app = QApplication(sys.argv)
    label = QLabel("카메라 준비 중...")
    label.resize(640, 480)

    thread = CameraThread()

    def show(frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        label.setPixmap(QPixmap.fromImage(img).scaled(label.width(), label.height()))

    thread.frame_ready.connect(show)
    thread.error.connect(lambda m: (print(f"[camera] {m}"), label.setText(m)))
    thread.begin()

    label.show()
    code = app.exec()
    thread.stop()
    sys.exit(code)
