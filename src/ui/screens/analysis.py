"""Analysis screen - dummy progress bar with rotating status text."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

from src.ui import theme

# 진행 단계별 안내 문구 (진행률 구간에 매핑)
_STATUS_TEXTS = ("얼굴 찾는 중...", "감정 분석 중...", "프레임 합성 중...")


class AnalysisScreen(QWidget):
    """Animates a 3s progress bar, then emits ``analysis_done``."""

    analysis_done = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        theme.apply_background(self, theme.SOFT)
        self._progress = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(120, 0, 120, 0)
        layout.addStretch(2)

        title = QLabel("감정을 분석하고 있어요...")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(theme.label_style(60, theme.DARK))
        layout.addWidget(title)

        layout.addSpacing(40)

        self.bar = QProgressBar()
        self.bar.setRange(0, theme.PROGRESS_STEPS)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setStyleSheet(theme.progressbar_style(theme.ORANGE))
        layout.addWidget(self.bar)

        layout.addSpacing(24)

        self.status = QLabel(_STATUS_TEXTS[0])
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet(theme.label_style(28, theme.PINK, bold=False))
        layout.addWidget(self.status)

        layout.addStretch(3)

    def start(self) -> None:
        """Reset and begin the analysis animation (called on entry)."""
        self._progress = 0
        self.bar.setValue(0)
        self.status.setText(_STATUS_TEXTS[0])
        self._timer.start(theme.PROGRESS_TICK_MS)

    def _tick(self) -> None:
        self._progress += 1
        self.bar.setValue(self._progress)

        # 진행률 3등분으로 안내 문구 교체
        idx = min(len(_STATUS_TEXTS) - 1, self._progress * len(_STATUS_TEXTS) // theme.PROGRESS_STEPS)
        self.status.setText(_STATUS_TEXTS[idx])

        if self._progress >= theme.PROGRESS_STEPS:
            self._timer.stop()
            self.analysis_done.emit()


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    screen = AnalysisScreen()
    screen.analysis_done.connect(lambda: print("[signal] analysis_done"))
    screen.resize(1280, 720)
    screen.show()
    screen.start()
    sys.exit(app.exec())
