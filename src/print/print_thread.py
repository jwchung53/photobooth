"""Background printing thread.

Prints the preview images off the UI thread. Reads all print settings
(paper_size, fit_mode, copies, ...) from config so paper only changes there.
"""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from src.print.printer import PrinterError, PrinterManager
from src.utils.config import get_config
from src.utils.logger import get_logger

log = get_logger(__name__)


class PrintThread(QThread):
    """Prints a list of PIL images, one per page."""

    progress = pyqtSignal(int, int)   # (현재 장, 전체 장)
    finished_all = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, images: list) -> None:
        super().__init__()
        self.images = images

    def run(self) -> None:  # QThread 진입점
        try:
            cfg = get_config()
            manager = PrinterManager(str(cfg.get("print.printer_name", "")) or None)
            paper = str(cfg.get("print.paper_size", "A4"))
            orientation = str(cfg.get("print.orientation", "landscape"))
            fit_mode = str(cfg.get("print.fit_mode", "fit"))
            copies = int(cfg.get("print.copies_per_person", 1))

            total = len(self.images)
            log.info("인쇄 시작: %d장 (용지=%s, %s)", total, paper, fit_mode)
            for i, img in enumerate(self.images, 1):
                self.progress.emit(i, total)
                manager.print_image(img, paper, orientation, fit_mode, copies)
            self.finished_all.emit()
        except PrinterError as exc:
            log.error("인쇄 실패: %s", exc)
            self.error.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - 크래시 금지
            log.exception("인쇄 스레드 오류")
            self.error.emit("인쇄 중 문제가 생겼어요. 프린터를 확인해주세요.")
