"""Emotion Photo Booth - application entry point.

Bootstraps configuration and logging, then announces the current phase.
Actual capture / analysis / compose / print flows are added in later phases.
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
        # 로거가 아직 없으므로 표준 출력으로 안내
        print(f"[치명적] {exc}", file=sys.stderr)
        return 1

    # 2) 로거 초기화
    setup_logging(config)
    log = get_logger("main")

    # 3) 시작 안내
    log.info("=" * 50)
    log.info("Emotion Photo Booth 시작")
    log.info("설정 파일: %s", config.source)
    log.info("Phase 1부터 시작합니다")
    log.info("=" * 50)

    print("Phase 1부터 시작합니다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
