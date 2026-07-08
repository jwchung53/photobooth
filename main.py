"""Emotion Photo Booth - application entry point.

Bootstraps configuration and logging, then launches the PyQt6 kiosk UI.
(The Phase 1 console pipeline still lives in ``phase1_pipeline.py``.)
"""

from __future__ import annotations

import sys
import threading

from src.utils.config import Config
from src.utils.logger import get_logger, setup_logging


def _warmup_analysis(on_ready) -> None:
    """Preload DeepFace/RetinaFace models in the background (off the UI thread).

    Runs a tiny dummy analysis so the first real analysis is fast, then calls
    ``on_ready`` (a queued Qt signal emit) so the UI can enable capture. Failures
    are non-fatal - ``on_ready`` still fires so the button never stays stuck.
    """
    log = get_logger("warmup")
    try:
        import numpy as np

        from deepface import DeepFace

        from src.utils.config import get_config

        # 검출기(mtcnn 등, TF 기반)와 감정 모델의 첫 추론(그래프 컴파일)까지 예열한다.
        backend = str(get_config().get("analysis.detector_backend", "mtcnn"))
        DeepFace.analyze(
            np.zeros((240, 320, 3), dtype=np.uint8),
            actions=["emotion"],
            detector_backend=backend,
            enforce_detection=False,
            silent=True,
        )
        # detector_backend="skip"은 전체를 얼굴로 간주 -> 감정 모델 추론 예열
        DeepFace.analyze(
            np.zeros((100, 100, 3), dtype=np.uint8),
            actions=["emotion"],
            detector_backend="skip",
            enforce_detection=False,
            silent=True,
        )
        log.info("DeepFace 워밍업 완료")
    except Exception as exc:  # noqa: BLE001
        log.warning("DeepFace 워밍업 실패(무시): %s", exc)
    finally:
        on_ready()


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

    # 3) PyQt 앱 실행 (지연 임포트: GUI 미사용 경로에서 비용 회피)
    from PyQt6.QtWidgets import QApplication

    from src.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow()
    window.showFullScreen()

    # 4) DeepFace 모델 백그라운드 워밍업 (완료 시 촬영 버튼 활성화)
    #    데몬 스레드에서 완료 후 warmup_ready 시그널을 emit (큐 연결로 UI 안전)
    threading.Thread(
        target=_warmup_analysis, args=(window.warmup_ready.emit,), daemon=True
    ).start()

    exit_code = app.exec()

    log.info("감정 포토부스 종료 (code=%d)", exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
