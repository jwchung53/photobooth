"""Emotion Photo Booth - application entry point.

Bootstraps configuration and logging, then launches the PyQt6 kiosk UI.
(The Phase 1 console pipeline still lives in ``phase1_pipeline.py``.)
"""

from __future__ import annotations

import sys

from src.utils.config import Config
from src.utils.logger import get_logger, setup_logging


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
    exit_code = app.exec()

    log.info("감정 포토부스 종료 (code=%d)", exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
