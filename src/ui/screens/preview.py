"""Preview screen - shows a dummy 3x2 result grid with action buttons."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.ui import theme

_GRID_COLS = 3
_GRID_ROWS = 2
_CELL = 200


class PreviewScreen(QWidget):
    """Result preview. Emits ``print_start`` or ``restart``."""

    print_start = pyqtSignal()
    restart = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        theme.apply_background(self, theme.WHITE)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.addStretch(1)

        title = QLabel("결과가 나왔어요!")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(theme.label_style(50, theme.DARK))
        layout.addWidget(title)

        layout.addSpacing(30)

        # 3x2 더미 결과 그리드 (6칸)
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setSpacing(16)
        for i in range(_GRID_ROWS * _GRID_COLS):
            cell = QLabel()
            cell.setFixedSize(_CELL, _CELL)
            cell.setStyleSheet(f"background:{theme.GRAY}; border-radius:12px;")
            grid.addWidget(cell, i // _GRID_COLS, i % _GRID_COLS)
        layout.addWidget(grid_host, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(40)

        # 하단 버튼: [인쇄하기] / [다시 찍기]
        buttons = QHBoxLayout()
        buttons.addStretch(1)

        print_btn = QPushButton("인쇄하기")
        print_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        print_btn.setStyleSheet(theme.button_style(theme.GREEN, size_px=30))
        print_btn.clicked.connect(self.print_start.emit)
        buttons.addWidget(print_btn)

        buttons.addSpacing(40)

        retry_btn = QPushButton("다시 찍기")
        retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        retry_btn.setStyleSheet(theme.button_style(theme.GRAY_BTN, size_px=30))
        retry_btn.clicked.connect(self.restart.emit)
        buttons.addWidget(retry_btn)

        buttons.addStretch(1)
        layout.addLayout(buttons)

        layout.addStretch(1)


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    screen = PreviewScreen()
    screen.print_start.connect(lambda: print("[signal] print_start"))
    screen.restart.connect(lambda: print("[signal] restart"))
    screen.resize(1280, 720)
    screen.show()
    sys.exit(app.exec())
