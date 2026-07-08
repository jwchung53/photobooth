"""Emotion Photo Booth - application entry point.

Bootstraps config/logging, applies kiosk settings (no sleep, hidden cursor,
high priority), warms up camera + analysis models in the background, launches
the PyQt6 kiosk UI, and restores the environment on exit.
(The Phase 1 console pipeline still lives in ``phase1_pipeline.py``.)
"""

from __future__ import annotations

import os
import sys
import threading

from src.utils.config import Config
from src.utils.logger import get_logger, setup_logging


def _warmup_analysis(on_ready) -> None:
    """Preload detection + emotion models in the background (off the UI thread).

    Calls ``on_ready`` (a queued Qt signal emit) when done so the UI can enable
    capture. Failures are non-fatal - ``on_ready`` still fires.
    """
    log = get_logger("warmup")
    try:
        import numpy as np

        from deepface import DeepFace

        from src.utils.config import get_config

        # 검출기(mtcnn 등, TF 기반)와 감정 모델의 첫 추론(그래프 컴파일)까지 예열.
        backend = str(get_config().get("analysis.detector_backend", "mtcnn"))
        DeepFace.analyze(
            np.zeros((240, 320, 3), dtype=np.uint8), actions=["emotion"],
            detector_backend=backend, enforce_detection=False, silent=True,
        )
        DeepFace.analyze(
            np.zeros((100, 100, 3), dtype=np.uint8), actions=["emotion"],
            detector_backend="skip", enforce_detection=False, silent=True,
        )
        log.info("DeepFace 워밍업 완료")
    except Exception as exc:  # noqa: BLE001
        log.warning("DeepFace 워밍업 실패(무시): %s", exc)
    finally:
        on_ready()


def _warmup_camera() -> None:
    """Open the camera once to prime the DirectShow backend (reduces first-open
    latency). Runs while capture is still gated behind model warmup, so there is
    no contention. Non-fatal on failure."""
    log = get_logger("warmup")
    try:
        from src.camera.capture import Camera

        cam = Camera().open()
        cam.warmup()
        cam.release()
        log.info("카메라 워밍업 완료")
    except Exception as exc:  # noqa: BLE001
        log.warning("카메라 워밍업 실패(무시): %s", exc)


def main() -> int:
    # 1) 설정 로드
    try:
        config = Config.load()
    except FileNotFoundError as exc:
        print(f"[치명적] {exc}", file=sys.stderr)
        return 1

    # 2) 로거 초기화
    setup_logging(config)
    log = get_logger("main")
    log.info("감정 포토부스 GUI 시작")

    # 개발 모드: PHOTOBOOTH_DEV=1 이면 일반 창(커서 보임, X로 종료, 키오스크 잠금 해제)
    dev_mode = os.environ.get("PHOTOBOOTH_DEV") == "1"
    log.info("실행 모드: %s", "개발(창)" if dev_mode else "키오스크(풀스크린)")

    # 3) 키오스크 환경 설정 (개발 모드에선 건너뜀)
    from src.utils import kiosk_utils

    if not dev_mode:
        kiosk_utils.set_process_priority_high()
        if bool(config.get("kiosk.prevent_sleep", True)):
            kiosk_utils.prevent_sleep()

    # 4) PyQt 앱 실행 (지연 임포트)
    from PyQt6.QtWidgets import QApplication

    from src.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow(kiosk=not dev_mode)
    if dev_mode:
        window.resize(1280, 800)
        window.show()
    else:
        if bool(config.get("kiosk.hide_cursor", True)):
            kiosk_utils.hide_cursor()
        window.showFullScreen()

    # 5) 백그라운드 워밍업 (완료 시 촬영 버튼 활성화)
    threading.Thread(
        target=_warmup_analysis, args=(window.warmup_ready.emit,), daemon=True
    ).start()
    threading.Thread(target=_warmup_camera, daemon=True).start()

    # 6) 실행 + 종료 시 환경 복원
    try:
        exit_code = app.exec()
    finally:
        kiosk_utils.show_cursor()
        kiosk_utils.allow_sleep()

    log.info("감정 포토부스 종료 (code=%d)", exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
