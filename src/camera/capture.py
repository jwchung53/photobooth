"""USB webcam capture via OpenCV (DirectShow backend, required on Windows).

Exposes a small ``Camera`` class with context-manager support. All device
access is guarded so an unavailable camera raises a friendly ``CameraError``
instead of crashing the pipeline.
"""

from __future__ import annotations

import cv2

from src.utils.config import PROJECT_ROOT, get_config
from src.utils.logger import get_logger

log = get_logger(__name__)

# 자동노출/화이트밸런스 안정화를 위해 버리는 워밍업 프레임 수
_WARMUP_FRAMES = 8


class CameraError(RuntimeError):
    """Raised when the camera cannot be opened or a frame cannot be read."""


class Camera:
    """Thin wrapper around cv2.VideoCapture using the DSHOW backend."""

    def __init__(
        self,
        index: int | None = None,
        width: int | None = None,
        height: int | None = None,
        fps: int | None = None,
    ) -> None:
        cfg = get_config()
        self.index = index if index is not None else int(cfg.get("camera.index", 0))
        self.width = int(width or cfg.get("camera.width", 1280))
        self.height = int(height or cfg.get("camera.height", 720))
        self.fps = int(fps or cfg.get("camera.fps", 30))
        self._cap: cv2.VideoCapture | None = None

    def open(self) -> "Camera":
        """Open the device and apply the configured resolution/fps."""
        # CAP_DSHOW: Windows USB 웹캠에서 필수 (지연/해상도 설정 안정)
        cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            raise CameraError(f"카메라를 열 수 없습니다 (index={self.index})")

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        self._cap = cap

        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        log.info(
            "카메라 열림 (index=%d, 요청=%dx%d, 실제=%dx%d)",
            self.index,
            self.width,
            self.height,
            actual_w,
            actual_h,
        )
        return self

    def read(self):
        """Read a single frame (BGR numpy array). Raises on failure."""
        if self._cap is None:
            raise CameraError("카메라가 열려있지 않습니다. open()을 먼저 호출하세요.")
        ok, frame = self._cap.read()
        if not ok or frame is None:
            raise CameraError("프레임을 읽지 못했습니다.")
        return frame

    def warmup(self, frames: int = _WARMUP_FRAMES) -> None:
        """Discard a few frames so exposure/white-balance can settle."""
        if self._cap is None:
            raise CameraError("카메라가 열려있지 않습니다.")
        for _ in range(max(0, frames)):
            self._cap.read()

    def capture(self):
        """Warm up, then return one still frame (BGR numpy array)."""
        self.warmup()
        frame = self.read()
        log.info("프레임 캡처 완료 (shape=%s)", getattr(frame, "shape", None))
        return frame

    def release(self) -> None:
        """Release the underlying device."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            log.info("카메라 해제 완료")

    def __enter__(self) -> "Camera":
        return self.open()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


if __name__ == "__main__":
    # 단독 테스트: 한 장 캡처해서 output/camera_test.png 저장
    out_path = PROJECT_ROOT / "output" / "camera_test.png"
    try:
        with Camera() as cam:
            frame = cam.capture()
        cv2.imwrite(str(out_path), frame)
        print(f"카메라 테스트 성공 → {out_path}")
    except CameraError as exc:
        print(f"카메라 테스트 실패(카메라 미연결이면 정상): {exc}")
