"""Attract screen - the idle welcome screen with a big start button."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from src.ui import theme


class AttractScreen(QWidget):
    """Idle screen. Emits ``start_capture`` when the user taps start."""

    start_capture = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        theme.apply_background(self, theme.ORANGE)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(2)

        title = QLabel("감정 포토부스")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(theme.label_style(80, theme.WHITE))
        layout.addWidget(title)

        self.subtitle = QLabel("친구들과 함께 찍어보세요!")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle.setStyleSheet(theme.label_style(30, theme.WHITE, bold=False))
        layout.addWidget(self.subtitle)

        layout.addStretch(1)

        # 중앙 원형 [촬영 시작] 버튼 (200x200)
        self.start_btn = QPushButton("촬영\n시작")
        self.start_btn.setFixedSize(200, 200)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setStyleSheet(
            theme.button_style(theme.PINK, size_px=34, radius=100, padding="0px")
        )
        self.start_btn.clicked.connect(self.start_capture.emit)
        layout.addWidget(self.start_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(2)

    def set_ready(self, ready: bool) -> None:
        """Enable the start button once analysis models are warmed up."""
        self.start_btn.setEnabled(ready)
        if ready:
            self.start_btn.setText("촬영\n시작")
            self.start_btn.setStyleSheet(
                theme.button_style(theme.PINK, size_px=34, radius=100, padding="0px")
            )
            self.subtitle.setText("친구들과 함께 찍어보세요!")
        else:
            self.start_btn.setText("준비\n중...")
            self.start_btn.setStyleSheet(
                theme.button_style(theme.GRAY_BTN, size_px=30, radius=100, padding="0px")
            )
            self.subtitle.setText("잠시만 기다려주세요...")


if __name__ == "__main__":
    # 단독 테스트: 창 모드로 띄우고 시그널을 콘솔에 출력
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    screen = AttractScreen()
    screen.start_capture.connect(lambda: print("[signal] start_capture"))
    screen.resize(1280, 720)
    screen.show()
    sys.exit(app.exec())
