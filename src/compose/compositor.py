"""Compositor - polaroid-style: full group photo on top + bottom color band.

For each detected person, ``compose_individual`` makes a 6x4 (1800x1200) image:
the FULL original group photo on top (1800x1000, aspect kept, never cropped,
white letterbox), a bottom emotion-pastel band (1800x200) with the booth title,
and that person's face highlighted with a dark-accent rectangle + emoji label.
All results share the same photo - only the highlighted face differs.
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from src.analysis.emotion import DEFAULT_FRAME
from src.utils.logger import get_logger

log = get_logger(__name__)

# ---- 레이아웃 (가로 6x4) ------------------------------------------------
CANVAS_W, CANVAS_H = 1800, 1200
PHOTO_W, PHOTO_H = 1800, 1000     # 상단 사진 영역 (전체 폭)
BAND_Y = 1000                     # 하단 색 띠 시작 y (높이 200)

# ---- 파스텔 프레임 색 / 진한 강조 색 / 라벨 -----------------------------
EMOTION_COLORS = {   # 연한 파스텔 (프레임 배경)
    "joy": "#FFE99A", "wow": "#FFD9A0", "calm": "#A8D0F0",
    "cool": "#F5A9B0", "chill": "#D8D8D8", "fear": "#D4A5DB",
}
EMOTION_ACCENT = {   # 진한 버전 (강조 사각형/텍스트)
    "joy": "#E6A800", "wow": "#E68A2E", "calm": "#4D96FF",
    "cool": "#E63946", "chill": "#808080", "fear": "#9C27B0",
}
EMOTION_LABELS = {
    "joy": ("😊", "행복"), "wow": ("😲", "놀람"), "calm": ("😢", "슬픔"),
    "cool": ("😠", "분노"), "chill": ("😐", "무표정"), "fear": ("😱", "두려움"),
}
FRAME_CATEGORIES = list(EMOTION_COLORS.keys())

_TITLE = "2026 화동제 감정 포토부스"
_LABEL_FONT = "C:/Windows/Fonts/malgun.ttf"
_BOLD_FONT = "C:/Windows/Fonts/malgunbd.ttf"
_EMOJI_FONT = "C:/Windows/Fonts/seguiemj.ttf"


def _hex(h: str) -> tuple:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except Exception:  # noqa: BLE001
        return None


def compose_individual(
    original_photo: np.ndarray,
    target_face: dict,
    all_faces: list[dict] | None = None,
    category: str | None = None,
) -> Image.Image:
    """One 6x4 image: full photo on top + emotion color band + face highlight."""
    cat = category or target_face.get("category", DEFAULT_FRAME)
    band_color = _hex(EMOTION_COLORS.get(cat, EMOTION_COLORS["chill"]))
    accent = _hex(EMOTION_ACCENT.get(cat, EMOTION_ACCENT["chill"]))

    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), (255, 255, 255))  # 흰 배경
    draw = ImageDraw.Draw(canvas)

    # 원본 단체사진 - 상단 1800x1000에 비율 유지 리사이즈 (crop 금지, 여백 흰색)
    photo = Image.fromarray(cv2.cvtColor(original_photo, cv2.COLOR_BGR2RGB))
    pw, ph = photo.size
    scale = min(PHOTO_W / pw, PHOTO_H / ph)
    rw, rh = int(pw * scale), int(ph * scale)
    resized = photo.resize((rw, rh), Image.LANCZOS)
    ox = (PHOTO_W - rw) // 2
    oy = (PHOTO_H - rh) // 2
    canvas.paste(resized, (ox, oy))

    # 하단 감정 색 띠 (y=1000~1200) + 중앙 제목 (80px 흰색 굵게)
    draw.rectangle([0, BAND_Y, CANVAS_W, CANVAS_H], fill=band_color)
    tfont = _font(_BOLD_FONT, 80) or _font(_LABEL_FONT, 80)
    if tfont:
        cy = (BAND_Y + CANVAS_H) // 2
        # 가독성 위해 옅은 그림자 후 흰 글자
        draw.text((CANVAS_W // 2 + 2, cy + 2), _TITLE, font=tfont,
                  fill=(0, 0, 0), anchor="mm")
        draw.text((CANVAS_W // 2, cy), _TITLE, font=tfont,
                  fill=(255, 255, 255), anchor="mm")

    # 대상 얼굴 강조 사각형 (사진 안, 진한 accent, 12px, 얼굴보다 20px 크게)
    x, y, w, h = target_face["bbox"]
    rx, ry = ox + int(x * scale), oy + int(y * scale)
    rbw, rbh = int(w * scale), int(h * scale)
    pad = 20
    draw.rectangle([rx - pad, ry - pad, rx + rbw + pad, ry + rbh + pad], outline=accent, width=12)

    # 사각형 옆 감정 말풍선 (감정 accent 색 + 흰 글자, 꼬리는 얼굴 쪽)
    emoji, ko = EMOTION_LABELS.get(cat, ("", cat))
    font = _font(_LABEL_FONT, 45)
    efont = _font(_EMOJI_FONT, 45)
    tw = int(draw.textlength(ko, font=font)) if font else len(ko) * 45
    ew = 56 if efont else 0
    ipad = 22
    bw, bh = ew + tw + ipad * 2, 45 + ipad
    side = "right"
    bx, by = rx + rbw + pad + 26, ry - pad
    if bx + bw > CANVAS_W - 16:                    # 오른쪽 공간 없으면 왼쪽
        side, bx = "left", rx - pad - bw - 26
        if bx < 16:                                # 왼쪽도 없으면 사각형 위
            side, bx, by = "top", rx - pad, ry - pad - bh - 26
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=bh // 3, fill=accent)
    cy = by + bh // 2
    if side == "right":
        draw.polygon([(bx, cy - 16), (bx, cy + 16), (bx - 22, cy)], fill=accent)
    elif side == "left":
        draw.polygon([(bx + bw, cy - 16), (bx + bw, cy + 16), (bx + bw + 22, cy)], fill=accent)
    else:
        mx = bx + bw // 2
        draw.polygon([(mx - 16, by + bh), (mx + 16, by + bh), (mx, by + bh + 22)], fill=accent)

    tx, ty = bx + ipad, by + (bh - 45) // 2
    if efont:
        try:
            draw.text((tx, ty - 4), emoji, font=efont, embedded_color=True)
        except Exception:  # noqa: BLE001
            pass
        tx += ew
    if font:
        draw.text((tx, ty), ko, font=font, fill=(255, 255, 255))

    return canvas


def compose_all(original_photo: np.ndarray, faces_info: list[dict]) -> list[Image.Image]:
    """One image per person - always the same original photo, different highlight."""
    results: list[Image.Image] = []
    for i, face in enumerate(faces_info):
        try:
            results.append(
                compose_individual(original_photo, face, faces_info, face.get("category")))
        except Exception as exc:  # noqa: BLE001 - 한 장 실패해도 계속
            log.warning("합성 실패(얼굴 %d): %s", i, exc)
    log.info("합성 완료: %d명 -> %d장", len(faces_info), len(results))
    return results


if __name__ == "__main__":
    dummy = np.full((720, 1280, 3), 120, dtype=np.uint8)
    faces = [
        {"bbox": (300, 200, 260, 260), "emotion": "happy", "category": "joy"},
        {"bbox": (820, 240, 220, 220), "emotion": "fear", "category": "fear"},
    ]
    for i, img in enumerate(compose_all(dummy, faces)):
        img.save(f"output/compose_test_{i}.png")
    print("저장: output/compose_test_*.png")
