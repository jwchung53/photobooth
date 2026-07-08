"""Windows kiosk helpers: cursor, sleep prevention, process priority.

All OS-level calls are guarded so the app still runs (with a warning) on
non-Windows or restricted environments.
"""

from __future__ import annotations

import ctypes
import sys

from src.utils.logger import get_logger

log = get_logger(__name__)

# SetThreadExecutionState 플래그
_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001
_ES_DISPLAY_REQUIRED = 0x00000002
# SetPriorityClass
_HIGH_PRIORITY_CLASS = 0x00000080

_IS_WINDOWS = sys.platform == "win32"


def hide_cursor() -> None:
    """Hide the mouse cursor application-wide."""
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication

        QApplication.setOverrideCursor(Qt.CursorShape.BlankCursor)
        log.info("마우스 커서 숨김")
    except Exception as exc:  # noqa: BLE001
        log.warning("커서 숨김 실패: %s", exc)


def show_cursor() -> None:
    """Restore the mouse cursor."""
    try:
        from PyQt6.QtWidgets import QApplication

        QApplication.restoreOverrideCursor()
    except Exception as exc:  # noqa: BLE001
        log.warning("커서 복원 실패: %s", exc)


def prevent_sleep() -> None:
    """Keep the display and system awake (Windows)."""
    if not _IS_WINDOWS:
        return
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(
            _ES_CONTINUOUS | _ES_SYSTEM_REQUIRED | _ES_DISPLAY_REQUIRED
        )
        log.info("절전 모드 방지 활성화")
    except Exception as exc:  # noqa: BLE001
        log.warning("절전 방지 실패: %s", exc)


def allow_sleep() -> None:
    """Restore normal power management (Windows)."""
    if not _IS_WINDOWS:
        return
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)
    except Exception as exc:  # noqa: BLE001
        log.warning("절전 복원 실패: %s", exc)


def set_process_priority_high() -> None:
    """Raise the process priority for smoother UI (Windows)."""
    if not _IS_WINDOWS:
        return
    try:
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.kernel32.SetPriorityClass(handle, _HIGH_PRIORITY_CLASS)
        log.info("프로세스 우선순위 상향")
    except Exception as exc:  # noqa: BLE001
        log.warning("우선순위 설정 실패: %s", exc)


def disable_windows_key() -> None:
    """Placeholder: disabling the Windows key needs a low-level keyboard hook.

    Not implemented (optional in spec) - documented so it isn't silently
    assumed to work. Consider a WH_KEYBOARD_LL hook if truly required.
    """
    log.info("disable_windows_key: 미구현 (선택 기능)")


if __name__ == "__main__":
    hide_cursor()
    show_cursor()
    prevent_sleep()
    allow_sleep()
    set_process_priority_high()
    disable_windows_key()
    print("kiosk_utils 셀프테스트 완료")
