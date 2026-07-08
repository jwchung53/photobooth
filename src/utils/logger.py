"""Logging setup - writes to both a rotating file and the console.

Reads ``logging.level`` and ``logging.file`` from config.yaml. Call
``setup_logging()`` once at startup, then use ``get_logger(__name__)`` in
every module.
"""

from __future__ import annotations

import logging
import sys
import time
from contextlib import contextmanager
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from src.utils.config import PROJECT_ROOT, Config, get_config

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 로그 파일 회전: 매일 자정 새 파일, 30일 보관
_ROTATE_WHEN = "midnight"
_BACKUP_DAYS = 30

_configured = False


def ensure_utf8_console() -> None:
    """Force stdout/stderr to UTF-8 so Korean text isn't garbled on Windows.

    Windows consoles default to a legacy code page (e.g. cp949), which mangles
    한국어 output. Safe to call multiple times; no-op if reconfigure is missing.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except Exception:
                pass


def setup_logging(config: Config | None = None) -> logging.Logger:
    """Configure the root logger with file + console handlers.

    Idempotent: repeated calls do not add duplicate handlers.
    """
    global _configured
    root = logging.getLogger()
    if _configured:
        return root

    ensure_utf8_console()

    cfg = config or get_config()
    level_name = str(cfg.get("logging.level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    log_file_raw = cfg.get("logging.file", "logs/photobooth.log")
    log_path = Path(log_file_raw)
    if not log_path.is_absolute():
        log_path = PROJECT_ROOT / log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root.setLevel(level)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    file_handler = TimedRotatingFileHandler(
        log_path, when=_ROTATE_WHEN, backupCount=_BACKUP_DAYS, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root.addHandler(file_handler)
    root.addHandler(console_handler)

    _configured = True
    root.info("로깅 초기화 완료 (level=%s, file=%s)", level_name, log_path)
    return root


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Ensures logging is configured first."""
    if not _configured:
        setup_logging()
    return logging.getLogger(name)


@contextmanager
def log_duration(logger: logging.Logger, label: str):
    """Context manager that logs how long a step took (performance logging)."""
    start = time.monotonic()
    try:
        yield
    finally:
        logger.info("⏱ %s: %.2f초", label, time.monotonic() - start)


if __name__ == "__main__":
    # 단독 테스트: 각 레벨 로그를 파일+콘솔로 출력
    setup_logging()
    log = get_logger("logger.selftest")
    log.debug("디버그 메시지 (레벨에 따라 안 보일 수 있음)")
    log.info("정보 메시지")
    log.warning("경고 메시지")
    log.error("에러 메시지")
    print("로그 파일을 확인하세요: logs/photobooth.log")
