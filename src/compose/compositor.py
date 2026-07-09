"""Compositor - polaroid: group photo on an emotion-colored card.

For each detected person, ``compose_individual`` makes a portrait 89:119
(1424x1904) image: the whole canvas is the emotion pastel color and the FULL
original landscape photo (aspect kept, never cropped) is scaled to the 1364px
width and pinned near the top, leaving a 30px border at the sides and 220px on
top. Everything below the photo is the thick bottom band carrying the booth
title; that person's face is highlighted with a dark-accent rectangle + emoji
label.
All results share the same photo - only the highlighted face differs.
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from src.analysis.emotion import DEFAULT_FRAME
from src.utils.logger import get_logger

log = get_logger(__name__)

# ---- 레이아웃 (폴라로이드, 세로 89:119) ----------------------------------
# 캔버스 전체가 감정 색. 가로 사진을 폭에 맞춰 위쪽에 붙이고, 남는 아래를
# 통째로 텍스트 띠로 쓴다 -> 옆 < 상단 << 하단 (고전 폴라로이드 실루엣).
CANVAS_W, CANVAS_H = 1424, 1904   # 89:119 세로형, 고해상도 인쇄용
SIDE_W = 30                       # 좌/우 색 여백 폭 (제일 얇게)
TOP_H = 220                       # 상단 색 여백 높이 (옆보다는 두껍게)
MIN_BOTTOM_H = 300                # 하단 색 띠 최소 높이 (텍스트 공간 보장)
PHOTO_X0 = SIDE_W                 # 사진 영역 좌측 경계 (30)
PHOTO_X1 = CANVAS_W - SIDE_W      # 사진 영역 우측 경계 (1394)
PHOTO_Y0 = TOP_H                  # 사진 영역 상단 경계 (220)
PHOTO_W = PHOTO_X1 - PHOTO_X0     # 1364 (가로 사진은 항상 이 폭을 꽉 채움)
PHOTO_MAX_H = CANVAS_H - TOP_H - MIN_BOTTOM_H  # 1384 (세로 사진 상한)
_BUBBLE_MARGIN = 16               # 말풍선이 사진 영역 안에서 유지할 여백
_TITLE_SIZE = 80                  # 하단 제목 폰트 크기
_LABEL_SIZE = 40                  # 감정 라벨 폰트 크기
_BOX_WIDTH = 14                   # 얼굴 강조 사각형 테두리 두께

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
    """One 89:119 polaroid: photo on an emotion-colored card + face highlight."""
    cat = category or target_face.get("category", DEFAULT_FRAME)
    band_color = _hex(EMOTION_COLORS.get(cat, EMOTION_COLORS["chill"]))
    accent = _hex(EMOTION_ACCENT.get(cat, EMOTION_ACCENT["chill"]))

    # 캔버스 전체가 감정 색 = 폴라로이드 대지. 사방 여백/하단 띠가 한 번에 칠해진다.
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), band_color)
    draw = ImageDraw.Draw(canvas)

    # 원본 단체사진 - 폭 1364에 맞춰 비율 유지 리사이즈 후 상단에 붙임 (crop 금지).
    # 세로로 긴 원본만 높이 상한에 걸려 좌우 레터박스가 생긴다.
    photo = Image.fromarray(cv2.cvtColor(original_photo, cv2.COLOR_BGR2RGB))
    pw, ph = photo.size
    scale = min(PHOTO_W / pw, PHOTO_MAX_H / ph)
    rw, rh = int(pw * scale), int(ph * scale)
    resized = photo.resize((rw, rh), Image.LANCZOS)
    ox = PHOTO_X0 + (PHOTO_W - rw) // 2
    oy = PHOTO_Y0
    canvas.paste(resized, (ox, oy))

    # 사진 아래 남은 영역 전체가 하단 띠 (이미 배경색) - 중앙 제목만 (80px 흰색 굵게)
    band_y = oy + rh
    tfont = _font(_BOLD_FONT, _TITLE_SIZE) or _font(_LABEL_FONT, _TITLE_SIZE)
    if tfont:
        cy = (band_y + CANVAS_H) // 2
        # 가독성 위해 옅은 그림자 후 흰 글자
        draw.text((CANVAS_W // 2 + 2, cy + 2), _TITLE, font=tfont,
                  fill=(0, 0, 0), anchor="mm")
        draw.text((CANVAS_W // 2, cy), _TITLE, font=tfont,
                  fill=(255, 255, 255), anchor="mm")

    # 대상 얼굴 강조 사각형 (사진 안, 진한 accent, 14px, 얼굴보다 20px 크게)
    x, y, w, h = target_face["bbox"]
    rx, ry = ox + int(x * scale), oy + int(y * scale)
    rbw, rbh = int(w * scale), int(h * scale)
    pad = 20
    draw.rectangle([rx - pad, ry - pad, rx + rbw + pad, ry + rbh + pad],
                   outline=accent, width=_BOX_WIDTH)

    # 사각형 옆 감정 말풍선 (감정 accent 색 + 흰 글자, 꼬리는 얼굴 쪽)
    emoji, ko = EMOTION_LABELS.get(cat, ("", cat))
    font = _font(_LABEL_FONT, _LABEL_SIZE)
    efont = _font(_EMOJI_FONT, _LABEL_SIZE)
    tw = int(draw.textlength(ko, font=font)) if font else len(ko) * _LABEL_SIZE
    ew = 50 if efont else 0
    ipad = 22
    bw, bh = ew + tw + ipad * 2, _LABEL_SIZE + ipad
    side = "right"
    bx, by = rx + rbw + pad + 26, ry - pad
    if bx + bw > PHOTO_X1 - _BUBBLE_MARGIN:        # 오른쪽 공간 없으면 왼쪽
        side, bx = "left", rx - pad - bw - 26
        if bx < PHOTO_X0 + _BUBBLE_MARGIN:         # 왼쪽도 없으면 사각형 위
            side, bx, by = "top", rx - pad, ry - pad - bh - 26
    by = max(by, PHOTO_Y0 + _BUBBLE_MARGIN)        # 상단 색 여백 침범 방지
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=bh // 3, fill=accent)
    cy = by + bh // 2
    if side == "right":
        draw.polygon([(bx, cy - 16), (bx, cy + 16), (bx - 22, cy)], fill=accent)
    elif side == "left":
        draw.polygon([(bx + bw, cy - 16), (bx + bw, cy + 16), (bx + bw + 22, cy)], fill=accent)
    else:
        mx = bx + bw // 2
        draw.polygon([(mx - 16, by + bh), (mx + 16, by + bh), (mx, by + bh + 22)], fill=accent)

    tx, ty = bx + ipad, by + (bh - _LABEL_SIZE) // 2
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
