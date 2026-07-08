"""Preview screen - shows the real per-person composite results in a grid.

``set_results(photo, analysis_results)`` composes one highlighted image per
detected person (via ``compose_individual``) and lays them out sized to the
group. Buttons: [인쇄하기] -> ``print_start``, [다시 찍기] -> ``restart``.
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

from src.analysis.emotion import EMOTION_EMOJI, EMOTION_KO
from src.compose.compositor import compose_individual
from src.ui import theme
from src.utils.logger import get_logger

log = get_logger(__name__)

# 인원수 -> (행, 열) 레이아웃
_LAYOUTS = {1: (1, 1), 2: (1, 2), 3: (2, 2), 4: (2, 2), 5: (2, 3), 6: (2, 3)}
# 열 수 -> 셀 이미지 폭(px)
_CELL_WIDTH = {1: 680, 2: 540, 3: 380}


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
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 24, 40, 24)
        layout.addStretch(1)

        self.title = QLabel("결과가 나왔어요!")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet(theme.label_style(50, theme.DARK))
        layout.addWidget(self.title)

        layout.addSpacing(20)

        # 결과 그리드 (set_results에서 채움)
        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setSpacing(20)
        layout.addWidget(self._grid_host, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addSpacing(30)

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

    def _make_cell(self, pixmap: QPixmap, face: dict) -> QWidget:
        cell = QWidget()
        v = QVBoxLayout(cell)
        v.setSpacing(8)

        img_label = QLabel()
        img_label.setPixmap(pixmap)
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(img_label)

        emotion = face.get("emotion", "neutral")
        caption = QLabel(f"{EMOTION_EMOJI.get(emotion, '😐')} {EMOTION_KO.get(emotion, emotion)}")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caption.setStyleSheet(theme.label_style(28, theme.DARK))
        v.addWidget(caption)
        return cell

    def set_results(self, photo: np.ndarray, analysis_results: list[dict]) -> None:
        """Build the per-person composite grid from analysis results."""
        self._clear_grid()
        n = len(analysis_results)
        if n == 0:
            log.warning("표시할 결과가 없습니다")
            return

        rows, cols = _LAYOUTS.get(n, (2, 3))
        cell_w = _CELL_WIDTH.get(cols, 380)

        for idx, face in enumerate(analysis_results):
            try:
                pil = compose_individual(photo, face, analysis_results, max_dim=cell_w)
                pix = _pil_to_qpixmap(pil).scaledToWidth(
                    cell_w, Qt.TransformationMode.SmoothTransformation
                )
            except Exception as exc:  # noqa: BLE001 - 한 셀 실패가 전체를 막지 않게
                log.warning("셀 %d 합성 실패: %s", idx, exc)
                continue
            r, c = divmod(idx, cols)
            self._grid.addWidget(self._make_cell(pix, face), r, c)

        log.info("미리보기 그리드 구성: %d명 (%dx%d)", n, rows, cols)


if __name__ == "__main__":
    # 단독 테스트: 더미 사진 + 가짜 결과로 그리드 표시
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    screen = PreviewScreen()
    dummy = np.full((720, 1280, 3), 90, dtype=np.uint8)
    fake = [
        {"bbox": (300, 200, 260, 260), "emotion": "happy", "category": "joy"},
        {"bbox": (800, 240, 220, 220), "emotion": "sad", "category": "calm"},
    ]
    screen.set_results(dummy, fake)
    screen.print_start.connect(lambda: print("[signal] print_start"))
    screen.restart.connect(lambda: print("[signal] restart"))
    screen.resize(1280, 720)
    screen.show()
    sys.exit(app.exec())
