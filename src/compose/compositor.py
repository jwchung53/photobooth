"""Composition helpers for the preview screen.

Builds PIL images from the captured photo + analysis results, reusing the
Phase 1 frame styles. ``compose_individual`` highlights one person with their
emotion's accent; ``compose_group`` boxes everyone on the whole photo.
"""

from __future__ import annotations

from collections import Counter

import cv2
import numpy as np
from PIL import Image, ImageDraw

from src.analysis.emotion import DEFAULT_FRAME, FRAME_PRIORITY
from src.compose.composer import FRAME_STYLES
from src.utils.logger import get_logger

log = get_logger(__name__)

# 합성 결과 최대 변 길이 (미리보기용 리사이즈)
_MAX_DIM = 800


def _to_pil(photo_bgr: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(photo_bgr, cv2.COLOR_BGR2RGB)).convert("RGB")


def _style(category: str) -> dict:
    return FRAME_STYLES.get(category, FRAME_STYLES[DEFAULT_FRAME])


def _draw_border(draw: ImageDraw.ImageDraw, w: int, h: int, color, thickness: int) -> None:
    for i in range(thickness):
        draw.rectangle([i, i, w - 1 - i, h - 1 - i], outline=color)


def _fit_max(img: Image.Image, max_dim: int) -> Image.Image:
    scale = min(1.0, max_dim / max(img.width, img.height))
    if scale >= 1.0:
        return img
    return img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)


def _representative_category(faces_info: list[dict]) -> str:
    if not faces_info:
        return DEFAULT_FRAME
    counts = Counter(f.get("category", DEFAULT_FRAME) for f in faces_info)
    top = max(counts.values())
    tied = [c for c, n in counts.items() if n == top]
    for cat in FRAME_PRIORITY:
        if cat in tied:
            return cat
    return tied[0]


def compose_individual(
    photo_bgr: np.ndarray,
    face_info: dict,
    all_faces: list[dict] | None = None,
    max_dim: int = _MAX_DIM,
) -> Image.Image:
    """Whole photo with one person's face highlighted + emotion-colored border."""
    img = _to_pil(photo_bgr)
    draw = ImageDraw.Draw(img)
    color = tuple(_style(face_info.get("category", DEFAULT_FRAME))["accent"])

    x, y, w, h = face_info["bbox"]
    box_lw = max(4, img.width // 160)
    draw.rectangle([x, y, x + w, y + h], outline=color, width=box_lw)

    _draw_border(draw, img.width, img.height, color, max(12, img.width // 34))
    return _fit_max(img, max_dim)


def compose_group(photo_bgr: np.ndarray, faces_info: list[dict], max_dim: int = _MAX_DIM) -> Image.Image:
    """Whole photo with every face boxed and a representative-emotion border."""
    img = _to_pil(photo_bgr)
    draw = ImageDraw.Draw(img)
    box_lw = max(3, img.width // 200)

    for face in faces_info:
        color = tuple(_style(face.get("category", DEFAULT_FRAME))["accent"])
        x, y, w, h = face["bbox"]
        draw.rectangle([x, y, x + w, y + h], outline=color, width=box_lw)

    rep_color = tuple(_style(_representative_category(faces_info))["accent"])
    _draw_border(draw, img.width, img.height, rep_color, max(12, img.width // 34))
    return _fit_max(img, max_dim)


if __name__ == "__main__":
    # 단독 테스트: 더미 사진 + 가짜 얼굴 정보로 합성 후 저장
    dummy = np.full((720, 1280, 3), 90, dtype=np.uint8)
    faces = [
        {"bbox": (300, 200, 260, 260), "emotion": "happy", "category": "joy"},
        {"bbox": (800, 240, 220, 220), "emotion": "sad", "category": "calm"},
    ]
    compose_group(dummy, faces).save("output/compositor_group.png")
    compose_individual(dummy, faces[0], faces).save("output/compositor_indiv.png")
    print("합성 테스트 저장: output/compositor_group.png, output/compositor_indiv.png")
