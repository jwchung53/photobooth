"""Preview screen - one solid-color emotion frame image per person, in a grid.

``set_results(photo, faces_info)`` builds N 4x6 images (via ``compose_all``) and
lays them out by headcount. Buttons: [인쇄하기] -> ``print_start``,
[다시 찍기] -> ``restart``.
"""

from __future__ import annotations

import numpy as np

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.compose.compositor import compose_all
from src.ui import theme
from src.utils.logger import get_logger

log = get_logger(__name__)

# 인원수 -> (행, 열)
_LAYOUTS = {1: (1, 1), 2: (1, 2), 3: (2, 2), 4: (2, 2), 5: (2, 3), 6: (2, 3)}
# 인원수 -> 셀 이미지 폭(px) (6x4 가로라 높이 = 폭*0.67)
_CELL_W_BY_N = {1: 680, 2: 540, 3: 460, 4: 460, 5: 380, 6: 380}


def _pil_to_qpixmap(img) -> QPixmap:
    img = img.convert("RGB")
    data = img.tobytes("raw", "RGB")
    qimg = QImage(data, img.width, img.height, 3 * img.width, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


class PreviewScreen(QWidget):
    """Result preview. Emits ``print_start`` or ``restart``."""

    print_start = pyqtSignal()
    restart = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        theme.apply_background(self, theme.WHITE)
        self.images: list = []  # 합성 결과(인쇄용)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 20)
        layout.addStretch(1)

        self.title = QLabel("결과가 나왔어요!")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet(theme.label_style(46, theme.DARK))
        layout.addWidget(self.title)

        layout.addSpacing(16)

        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setSpacing(18)
        layout.addWidget(self._grid_host, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addSpacing(24)

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

    def _clear_grid(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def set_results(self, photo: np.ndarray, faces_info: list[dict]) -> None:
        """Build one emotion-frame image per person and lay them in a grid."""
        self._clear_grid()
        n = len(faces_info)
        if n == 0:
            log.warning("표시할 결과가 없습니다")
            return
        rows, cols = _LAYOUTS.get(n, (2, 3))
        cell_w = _CELL_W_BY_N.get(n, 250)
        try:
            images = compose_all(photo, faces_info)
        except Exception:  # noqa: BLE001
            log.exception("미리보기 합성 실패")
            self.images = []
            return
        self.images = images  # 인쇄용 보관
        for idx, img in enumerate(images):
            pix = _pil_to_qpixmap(img).scaledToWidth(
                cell_w, Qt.TransformationMode.SmoothTransformation
            )
            label = QLabel()
            label.setPixmap(pix)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            r, c = divmod(idx, cols)
            self._grid.addWidget(label, r, c)
        log.info("미리보기 그리드: %d명 (%dx%d)", n, rows, cols)


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    screen = PreviewScreen()
    dummy = np.full((720, 1280, 3), 90, dtype=np.uint8)
    fake = [
        {"bbox": (300, 200, 260, 260), "emotion": "happy", "category": "joy"},
        {"bbox": (800, 240, 220, 220), "emotion": "fear", "category": "fear"},
    ]
    screen.set_results(dummy, fake)
    screen.print_start.connect(lambda: print("[signal] print_start"))
    screen.restart.connect(lambda: print("[signal] restart"))
    screen.resize(1280, 720)
    screen.show()
    sys.exit(app.exec())
