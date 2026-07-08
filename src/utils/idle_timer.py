"""Idle timeout timer for kiosk auto-reset.

Emits ``idle_timeout`` after ``timeout_ms`` of no ``reset()`` call. The main
window resets it on any user input (via an app-wide event filter), so the
signal only fires when a visitor walks away.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, QTimer, pyqtSignal


class IdleTimer(QObject):
    """Fires ``idle_timeout`` when no input arrives within the timeout."""

    idle_timeout = pyqtSignal()

    def __init__(self, timeout_ms: int = 60000, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.timeout_ms = int(timeout_ms)
        self._timer = QTimer(self)
        self._timer.setInterval(self.timeout_ms)
        self._timer.timeout.connect(self.idle_timeout.emit)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def reset(self) -> None:
        """Restart the countdown (called on user input)."""
        if self._timer.isActive():
            self._timer.start()  # QTimer.start()는 인터벌을 다시 시작


if __name__ == "__main__":
    # 단독 테스트: 2초 타임아웃, 1.5초 후 reset -> 이후 2초 뒤 발생
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    timer = IdleTimer(2000)
    timer.idle_timeout.connect(lambda: (print("idle_timeout 발생!"), app.quit()))
    timer.start()
    QTimer.singleShot(1500, lambda: (print("1.5초: reset"), timer.reset()))
    print("2초 무입력 시 타임아웃 (1.5초에 한 번 reset)")
    sys.exit(app.exec())
