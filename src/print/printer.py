"""Printing via pywin32 - config-driven paper size (A4 test, 4x6 real).

``PrinterManager`` detects printers and prints PIL images. Paper size is chosen
by name (A4/4x6/5x7/L); non-standard sizes are set as a custom DEVMODE size, so
switching paper only needs a config change. All device access is guarded so a
missing/failed printer raises ``PrinterError`` instead of crashing.
"""

from __future__ import annotations

from PIL import Image, ImageWin

from src.utils.logger import get_logger

log = get_logger(__name__)

# 지원 용지 크기 (mm) - width x length (세로 기준 mm)
PAPER_SIZES_MM = {
    "A4": (210.0, 297.0),
    "4x6": (101.6, 152.4),
    "5x7": (127.0, 178.0),
    "L": (89.0, 127.0),
    "89x119": (89.0, 119.0),  # 실전 용지. 프레임(89:119)과 비율이 정확히 같다
}

try:
    import win32con
    import win32gui
    import win32print
    import win32ui

    _WIN = True
except Exception as exc:  # noqa: BLE001 - 비 Windows/환경 문제
    _WIN = False
    log.warning("pywin32 임포트 실패 (인쇄 불가): %s", exc)


class PrinterError(RuntimeError):
    """Raised on any printing failure (missing printer, driver error, ...)."""


class PrinterManager:
    """Detects printers and prints PIL images at a config-driven paper size."""

    def __init__(self, printer_name: str | None = None) -> None:
        self.printer_name = printer_name or self.get_default_printer()

    # ---- 감지 --------------------------------------------------------
    @staticmethod
    def list_printers() -> list[str]:
        """Return installed printer names (empty on non-Windows)."""
        if not _WIN:
            return []
        try:
            flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            return [p[2] for p in win32print.EnumPrinters(flags)]
        except Exception as exc:  # noqa: BLE001
            log.warning("프린터 목록 조회 실패: %s", exc)
            return []

    @staticmethod
    def get_default_printer() -> str | None:
        if not _WIN:
            return None
        try:
            return win32print.GetDefaultPrinter()
        except Exception as exc:  # noqa: BLE001
            log.warning("기본 프린터 조회 실패: %s", exc)
            return None

    # ---- DEVMODE (용지/방향) -----------------------------------------
    def _devmode(self, paper_size: str, orientation: str):
        hprinter = win32print.OpenPrinter(self.printer_name)
        try:
            devmode = win32print.GetPrinter(hprinter, 2)["pDevMode"]
        finally:
            win32print.ClosePrinter(hprinter)
        if devmode is None:
            raise PrinterError("프린터 설정(DEVMODE)을 가져올 수 없습니다")

        # 방향 (프레임이 세로라 config는 portrait)
        devmode.Orientation = (
            win32con.DMORIENT_LANDSCAPE if orientation == "landscape"
            else win32con.DMORIENT_PORTRAIT
        )
        devmode.Fields |= win32con.DM_ORIENTATION

        # 용지 크기: A4는 표준 코드, 나머지는 커스텀(0.1mm 단위)
        if paper_size == "A4":
            devmode.PaperSize = win32con.DMPAPER_A4
            devmode.Fields |= win32con.DM_PAPERSIZE
        else:
            w_mm, l_mm = PAPER_SIZES_MM.get(paper_size, PAPER_SIZES_MM["A4"])
            devmode.PaperSize = 0
            devmode.PaperWidth = int(w_mm * 10)
            devmode.PaperLength = int(l_mm * 10)
            devmode.Fields |= (
                win32con.DM_PAPERSIZE | win32con.DM_PAPERWIDTH | win32con.DM_PAPERLENGTH
            )
        return devmode

    # ---- 인쇄 --------------------------------------------------------
    def print_image(
        self,
        pil_image: Image.Image,
        paper_size: str = "A4",
        orientation: str = "landscape",
        fit_mode: str = "fit",
        copies: int = 1,
    ) -> None:
        """Print one PIL image at the given paper size (fit=여백 / fill=꽉)."""
        if not _WIN:
            raise PrinterError("Windows 인쇄 환경이 아닙니다")
        if not self.printer_name:
            raise PrinterError("프린터를 찾을 수 없어요. 연결을 확인해주세요.")

        devmode = self._devmode(paper_size, orientation)
        try:
            hdc = win32gui.CreateDC("WINSPOOL", self.printer_name, devmode)
            dc = win32ui.CreateDCFromHandle(hdc)
        except Exception as exc:  # noqa: BLE001
            raise PrinterError(f"프린터 DC 생성 실패: {exc}") from exc

        try:
            pw = dc.GetDeviceCaps(win32con.HORZRES)   # 인쇄 가능 폭(px)
            ph = dc.GetDeviceCaps(win32con.VERTRES)   # 인쇄 가능 높이(px)
            img = pil_image.convert("RGB")
            iw, ih = img.size
            # fit(전체 보이게, 여백) / fill(꽉 차게, 일부 잘림)
            scale = max(pw / iw, ph / ih) if fit_mode == "fill" else min(pw / iw, ph / ih)
            dw, dh = int(iw * scale), int(ih * scale)
            x1, y1 = (pw - dw) // 2, (ph - dh) // 2

            dc.StartDoc("2026 화동제 감정 포토부스")
            for _ in range(max(1, copies)):
                dc.StartPage()
                ImageWin.Dib(img).draw(dc.GetHandleOutput(), (x1, y1, x1 + dw, y1 + dh))
                dc.EndPage()
            dc.EndDoc()
            log.info("인쇄 완료 (용지=%s, %s, %dx%dpx, %d부)", paper_size, fit_mode, pw, ph, copies)
        except Exception as exc:  # noqa: BLE001
            raise PrinterError(f"인쇄 중 오류: {exc}") from exc
        finally:
            dc.DeleteDC()

    def print_multiple(
        self, images: list[Image.Image], paper_size: str = "A4",
        orientation: str = "landscape", fit_mode: str = "fit", copies: int = 1,
    ) -> None:
        for img in images:
            self.print_image(img, paper_size, orientation, fit_mode, copies)


if __name__ == "__main__":
    # 단독 테스트: 프린터 감지
    print("기본 프린터:", PrinterManager.get_default_printer())
    print("설치된 프린터:")
    for name in PrinterManager.list_printers():
        print("  -", name)
    print("지원 용지:", list(PAPER_SIZES_MM))
