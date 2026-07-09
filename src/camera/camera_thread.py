"""Background camera capture thread for the UI.

Opens a webcam - trying DirectShow, then MSMF, then OpenCV's default backend -
and streams BGR frames to the GUI via ``frame_ready`` so the UI thread never
blocks on camera I/O. Keeps the most recent frame so the capture moment can grab
a still with ``get_latest_frame``.
"""

from __future__ import annotations

from collections import deque

import cv2
import numpy as np

from PyQt6.QtCore import QThread, pyqtSignal

from src.camera.camera_utils import (
    backend_label,
    find_available_camera,
    find_camera_by_name,
    open_capture,
)
from src.utils.config import get_config
from src.utils.logger import get_logger

log = get_logger(__name__)

# OpenCV 캡처 백엔드 (config camera.backend). None = 백엔드 미지정(기본)
_BACKENDS: dict[str, int | None] = {
    "dshow": cv2.CAP_DSHOW,
    "msmf": cv2.CAP_MSMF,
    "any": None,
    "default": None,
}
# config 백엔드가 실패하면 이 순서로 폴백
_FALLBACK_ORDER: tuple[int | None, ...] = (cv2.CAP_DSHOW, cv2.CAP_MSMF, None)
# 백엔드가 열린 뒤 실제로 프레임이 나오는지 확인할 횟수 (첫 read는 종종 빈 프레임)
_PROBE_READS = 3
_PROBE_INTERVAL_MS = 100
# 이 횟수만큼 연속으로 프레임을 못 읽으면 스트림을 포기하고 에러 (무한 재시도 방지)
_MAX_CONSECUTIVE_FAILS = 30


def _resolve_backend(name) -> int | None:
    key = str(name).strip().lower()
    if key not in _BACKENDS:
        log.warning("알 수 없는 camera.backend='%s' -> dshow 사용", name)
        return cv2.CAP_DSHOW
    return _BACKENDS[key]


def _backend_order(preferred: int | None) -> list[int | None]:
    """Preferred backend first, then the remaining fallbacks in order."""
    return [preferred] + [b for b in _FALLBACK_ORDER if b != preferred]


class CameraThread(QThread):
    """Streams webcam frames (BGR numpy arrays) via ``frame_ready``."""

    frame_ready = pyqtSignal(np.ndarray)  # BGR frame
    error = pyqtSignal(str)               # 사용자 친화 메시지

    def __init__(self, camera_index: int | None = None) -> None:
        super().__init__()
        cfg = get_config()
        # 카메라 선택: 인자 > preferred_name(이름 매칭) > config.index
        if camera_index is not None:
            self.camera_index = camera_index
        else:
            preferred = str(cfg.get("camera.preferred_name", "") or "")
            by_name = find_camera_by_name(preferred) if preferred else None
            self.camera_index = by_name if by_name is not None else int(cfg.get("camera.index", 0))
        self.width = int(cfg.get("camera.width", 1280))
        self.height = int(cfg.get("camera.height", 720))
        self.fps = int(cfg.get("camera.fps", 30))
        self.warmup_frames = int(cfg.get("camera.warmup_frames", 5))
        self.backend = _resolve_backend(cfg.get("camera.backend", "dshow"))
        self.active_backend: int | None = None  # 실제로 열린 백엔드
        self._running = False
        self._latest: np.ndarray | None = None
        # 감정 안정화용 최근 프레임 버퍼
        self._recent: deque[np.ndarray] = deque(maxlen=10)

    @staticmethod
    def _safe_read(cap: cv2.VideoCapture):
        """``cap.read()`` that never raises - a broken stream can throw cv2.error."""
        try:
            return cap.read()
        except cv2.error as exc:  # 드라이버/포맷 문제로 내부 Mat 생성 실패
            log.warning("프레임 읽기 예외: %s", exc)
            return False, None

    def _probe(self, cap: cv2.VideoCapture) -> bool:
        """True if the capture yields a real frame within a few attempts."""
        for _ in range(_PROBE_READS):
            ret, frame = self._safe_read(cap)
            if ret and frame is not None:
                return True
            self.msleep(_PROBE_INTERVAL_MS)
        return False

    def _try_open(self, index: int, backend: int | None) -> cv2.VideoCapture | None:
        """Open ``index`` with ``backend`` and verify a frame actually arrives."""
        label = backend_label(backend)
        cap = open_capture(index, backend)
        if not cap.isOpened():
            cap.release()
            log.warning("카메라 열기 실패 (index=%d, backend=%s)", index, label)
            return None

        if self._probe(cap):
            log.info("카메라 열림 (index=%d, backend=%s)", index, label)
            return cap

        cap.release()
        log.warning("열렸지만 프레임 없음 (index=%d, backend=%s)", index, label)
        return None

    def _open_at_size(self, index: int, backend: int | None) -> cv2.VideoCapture | None:
        """Open ``index``/``backend`` only if it streams the configured size.

        The resolution MUST be set right after opening, before the first read:
        changing the format on an already-streaming capture breaks it (MSMF then
        dies with a broken Mat, DSHOW silently keeps the native size). Setting it
        first also lets a probe prove the format works - ``get()`` happily
        reports back a resolution the camera cannot actually stream. A None
        return means this backend cannot deliver the requested size, so the
        caller should try another rather than settle for native.
        """
        label = backend_label(backend)
        cap = open_capture(index, backend)
        if not cap.isOpened():
            cap.release()
            log.warning("카메라 열기 실패 (index=%d, backend=%s)", index, label)
            return None

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        if self._probe(cap):
            log.info("카메라 열림 (index=%d, backend=%s, %dx%d)",
                     index, label, self.width, self.height)
            return cap

        cap.release()
        log.warning("%dx%d 스트리밍 불가 (backend=%s) -> 다른 백엔드 시도",
                    self.width, self.height, label)
        return None

    def _open(self) -> cv2.VideoCapture | None:
        """Open a camera that actually delivers frames at the configured size.

        Pass 1 exhausts every backend (config 우선 → dshow → msmf → 기본) on the
        selected index, because that index is the camera we actually want - some
        webcams only open under MSMF, and some only stream high resolutions under
        DSHOW. Pass 2 auto-detects a different index. Only if no backend can
        deliver the configured resolution do we settle for the native one, since
        an upscaled 640x480 still visibly degrades the print.
        """
        backends = _backend_order(self.backend)

        # 1단계: 원하는 카메라 + 원하는 해상도
        for backend in backends:
            cap = self._open_at_size(self.camera_index, backend)
            if cap is not None:
                self.active_backend = backend
                return cap

        # 2단계: 다른 인덱스 자동 탐색 (다른 카메라로 대체), 역시 원하는 해상도로
        log.warning(
            "index=%d를 %dx%d로 열지 못함 -> 다른 카메라 탐색",
            self.camera_index, self.width, self.height,
        )
        for backend in backends:
            idx = find_available_camera(backend=backend)
            if idx is None or idx == self.camera_index:
                continue
            cap = self._open_at_size(idx, backend)
            if cap is not None:
                log.warning(
                    "원하던 카메라 대신 index=%d로 대체 (backend=%s)",
                    idx,
                    backend_label(backend),
                )
                self.camera_index = idx
                self.active_backend = backend
                return cap

        # 3단계: 해상도를 포기하고 네이티브로라도 스트리밍 (화질 저하 경고)
        for backend in backends:
            cap = self._try_open(self.camera_index, backend)
            if cap is not None:
                self.active_backend = backend
                log.warning(
                    "%dx%d를 지원하는 백엔드가 없음 -> 네이티브 %dx%d로 진행 (인쇄 화질 저하)",
                    self.width, self.height,
                    int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                )
                return cap

        log.error("모든 백엔드(DSHOW/MSMF/기본)로 카메라를 열지 못했습니다")
        return None

    def run(self) -> None:  # QThread 진입점 (별도 스레드)
        cap = self._open()  # 해상도 적용/검증까지 끝난 캡처
        if cap is None:
            self.error.emit("카메라를 찾을 수 없어요. USB 연결을 확인해주세요.")
            return

        log.info(
            "카메라 스트림 시작 (index=%d, backend=%s, %dx%d)",
            self.camera_index,
            backend_label(self.active_backend),
            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )

        # 노출/화이트밸런스 안정화를 위해 첫 프레임들은 버림
        for _ in range(self.warmup_frames):
            self._safe_read(cap)

        interval_ms = int(1000 / max(1, self.fps))
        fails = 0
        try:
            while self._running:
                ret, frame = self._safe_read(cap)
                if not ret or frame is None:
                    # 일시적 실패: 로깅 후 계속 시도 (크래시 금지)
                    fails += 1
                    if fails >= _MAX_CONSECUTIVE_FAILS:
                        log.error("프레임 %d회 연속 실패 -> 스트림 중단", fails)
                        self.error.emit("카메라 연결이 끊겼어요. USB를 확인해주세요.")
                        return
                    log.warning("프레임 읽기 실패, 재시도")
                    self.msleep(interval_ms)
                    continue
                fails = 0
                self._latest = frame
                self._recent.append(frame)
                # 소비자(GUI 스레드)가 안전하게 쓰도록 복사본 전달
                self.frame_ready.emit(frame.copy())
                self.msleep(interval_ms)
        finally:
            cap.release()
            log.info("카메라 스트림 종료")

    def get_latest_frame(self) -> np.ndarray | None:
        """Return a copy of the most recent frame (for the capture moment)."""
        return None if self._latest is None else self._latest.copy()

    def get_recent_frames(self, n: int) -> list[np.ndarray]:
        """Return copies of up to the last ``n`` frames (for emotion voting)."""
        return [f.copy() for f in list(self._recent)[-n:]]

    def begin(self) -> None:
        """Start streaming (idempotent)."""
        if not self.isRunning():
            self._running = True
            self._latest = None
            self._recent.clear()
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
