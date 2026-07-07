"""Compose a captured photo with an emotion-based frame (Pillow).

The photo is placed on a print-sized canvas whose border reflects the group's
representative emotion. If a real frame PNG exists at ``<frames_dir>/<cat>.png``
it is overlaid; otherwise a colored placeholder frame is generated so the
pipeline is runnable before any art assets exist.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont

from src.analysis.emotion import DEFAULT_FRAME, FaceResult, select_frame_category
from src.utils.config import get_config
from src.utils.logger import get_logger

log = get_logger(__name__)

# 프레임 카테고리별 스타일 (실제 PNG가 없을 때 플레이스홀더 생성에 사용)
FRAME_STYLES: dict[str, dict] = {
    "joy": {"label": "기쁨", "accent": (255, 138, 91), "concept": "꽃·폭죽·따뜻한 톤"},
    "wow": {"label": "놀라움", "accent": (245, 190, 64), "concept": "별·반짝이"},
    "calm": {"label": "차분", "accent": (86, 149, 214), "concept": "블루"},
    "cool": {"label": "쿨", "accent": (58, 61, 84), "concept": "다크·불꽃"},
    "chill": {"label": "여유", "accent": (139, 168, 136), "concept": "미니멀 자연톤"},
}


class Composer:
    """Builds the final print-ready image from a frame + face analysis."""

    def __init__(self) -> None:
        cfg = get_config()
        size = cfg.get("compose.output_size", [1800, 1200])
        self.canvas_w, self.canvas_h = int(size[0]), int(size[1])
        self.border = int(cfg.get("compose.border", 48))
        self.draw_labels = bool(cfg.get("compose.draw_face_labels", True))
        self.font_path = cfg.get("compose.font", "C:/Windows/Fonts/malgun.ttf")
        self.frames_dir = cfg.resolve_path("frames.dir", "assets/frames")
        self.output_dir = cfg.resolve_path("output.dir", "output")
        self.output_format = str(cfg.get("output.format", "png")).lower()

    # ---- font ---------------------------------------------------------
    def _load_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Load the Korean-capable font, falling back to PIL default."""
        try:
            return ImageFont.truetype(self.font_path, size)
        except Exception:
            try:
                return ImageFont.truetype("malgun.ttf", size)
            except Exception:
                log.warning("한글 폰트를 찾지 못해 기본 폰트 사용 (한글 깨질 수 있음)")
                return ImageFont.load_default()

    # ---- geometry -----------------------------------------------------
    @staticmethod
    def _fit_contain(img: Image.Image, box_w: int, box_h: int) -> Image.Image:
        """Resize img to fit within (box_w, box_h) preserving aspect ratio."""
        scale = min(box_w / img.width, box_h / img.height)
        new_w = max(1, int(img.width * scale))
        new_h = max(1, int(img.height * scale))
        return img.resize((new_w, new_h), Image.LANCZOS)

    # ---- drawing ------------------------------------------------------
    def _draw_faces(self, photo: Image.Image, faces: list[FaceResult]) -> None:
        """Draw per-face boxes + positive category labels on the photo."""
        draw = ImageDraw.Draw(photo)
        font = self._load_font(max(20, photo.height // 28))
        box_w = max(2, photo.height // 200)
        for face in faces:
            x, y, w, h = face.box
            style = FRAME_STYLES.get(face.frame_category, FRAME_STYLES[DEFAULT_FRAME])
            color = style["accent"]
            draw.rectangle([x, y, x + w, y + h], outline=color, width=box_w)
            label = style["label"]
            tb = draw.textbbox((0, 0), label, font=font)
            tw, th = tb[2] - tb[0], tb[3] - tb[1]
            ly = max(0, y - th - 10)
            draw.rectangle([x, ly, x + tw + 12, ly + th + 10], fill=color)
            draw.text((x + 6, ly + 4), label, fill=(255, 255, 255), font=font)

    def _draw_title(self, canvas: Image.Image, category: str) -> None:
        """Draw the emotion title in the bottom border strip."""
        style = FRAME_STYLES[category]
        draw = ImageDraw.Draw(canvas)
        font = self._load_font(max(28, self.canvas_h // 22))
        text = f"오늘의 감정 · {style['label']}"
        tb = draw.textbbox((0, 0), text, font=font)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        x = (self.canvas_w - tw) // 2
        y = self.canvas_h - self.border // 2 - th
        draw.text((x, y), text, fill=(255, 255, 255), font=font)

    def _apply_frame(self, canvas: Image.Image, category: str) -> Image.Image:
        """Overlay a real frame PNG if present, else draw a placeholder title."""
        frame_png = self.frames_dir / f"{category}.png"
        if frame_png.exists():
            try:
                overlay = Image.open(frame_png).convert("RGBA")
                overlay = overlay.resize((self.canvas_w, self.canvas_h), Image.LANCZOS)
                base = canvas.convert("RGBA")
                base.alpha_composite(overlay)
                log.info("실제 프레임 오버레이 적용: %s", frame_png.name)
                return base.convert("RGB")
            except Exception as exc:  # noqa: BLE001
                log.warning("프레임 PNG 로드 실패(%s), 플레이스홀더 사용: %s", frame_png, exc)
        # 실제 프레임이 없으면 캔버스 테두리(색상) + 타이틀로 대체
        self._draw_title(canvas, category)
        return canvas

    # ---- public API ---------------------------------------------------
    def compose(self, image_bgr, faces: list[FaceResult]) -> Image.Image:
        """Compose the print-ready image and return it as a PIL RGB image."""
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        photo = Image.fromarray(rgb)

        if self.draw_labels and faces:
            self._draw_faces(photo, faces)

        category = select_frame_category(faces)
        style = FRAME_STYLES[category]

        # 카테고리 색상의 테두리 캔버스에 사진을 중앙 배치
        inner_w = self.canvas_w - 2 * self.border
        inner_h = self.canvas_h - 2 * self.border
        fitted = self._fit_contain(photo, inner_w, inner_h)
        canvas = Image.new("RGB", (self.canvas_w, self.canvas_h), style["accent"])
        ox = (self.canvas_w - fitted.width) // 2
        oy = (self.canvas_h - fitted.height) // 2
        canvas.paste(fitted, (ox, oy))

        canvas = self._apply_frame(canvas, category)
        log.info("합성 완료 (카테고리=%s, 얼굴=%d개)", category, len(faces))
        return canvas

    def save(self, image: Image.Image, name: str | None = None) -> Path:
        """Save the composed image to the output dir with a timestamped name."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if name is None:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = f"photobooth_{stamp}.{self.output_format}"
        out_path = self.output_dir / name
        image.save(out_path)
        log.info("결과 저장: %s", out_path)
        return out_path


if __name__ == "__main__":
    # 단독 테스트: 합성용 더미 이미지 + 가짜 얼굴 결과로 저장까지 검증
    import numpy as np

    dummy = np.full((720, 1280, 3), 70, dtype=np.uint8)
    cv2.rectangle(dummy, (200, 150), (420, 370), (120, 90, 60), -1)
    cv2.rectangle(dummy, (760, 180), (960, 380), (60, 90, 120), -1)
    fake_faces = [
        FaceResult((200, 150, 220, 220), "happy", "joy", {"happy": 92.0}, 0.99),
        FaceResult((760, 180, 200, 200), "sad", "calm", {"sad": 71.0}, 0.98),
    ]
    composer = Composer()
    result = composer.compose(dummy, fake_faces)
    saved = composer.save(result, name="compose_test.png")
    print(f"합성 테스트 성공 → {saved}")
