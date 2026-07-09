"""Generate the 6 emotion frame PNGs (1200x1800, 4x6 portrait, 300DPI).

Each frame: themed gradient background + decorations + a transparent center
photo window (1000x1200, 100px margin) + a bottom 500px band with the emotion
label. Standalone (no project imports).

    uv run python assets/frames/generate_all_frames.py
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---- 공통 사양 -----------------------------------------------------------
W, H = 1200, 1800
PHOTO = (100, 100, 1100, 1300)  # 사진 투명창 (좌,상,우,하) = 1000x1200
OUT_DIR = Path(__file__).resolve().parent
FONT_PATH = "C:/Windows/Fonts/malgun.ttf"
EMOJI_PATH = "C:/Windows/Fonts/seguiemj.ttf"


# ---- 헬퍼 함수 -----------------------------------------------------------
def _hex(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def create_gradient_background(size, color_start, color_end) -> Image.Image:
    """세로 그라디언트 RGBA 배경."""
    w, h = size
    t = np.array(_hex(color_start), dtype=float)
    b = np.array(_hex(color_end), dtype=float)
    ramp = np.linspace(0, 1, h)[:, None]
    rows = (t[None, :] * (1 - ramp) + b[None, :] * ramp).astype(np.uint8)
    arr = np.repeat(rows[:, None, :], w, axis=1)
    rgba = np.dstack([arr, np.full((h, w), 255, np.uint8)])
    return Image.fromarray(rgba, "RGBA")


def draw_star(draw, x, y, size, color, points=5) -> None:
    """5각 별."""
    pts = []
    for i in range(points * 2):
        ang = math.pi / points * i - math.pi / 2
        rad = size if i % 2 == 0 else size * 0.42
        pts.append((x + rad * math.cos(ang), y + rad * math.sin(ang)))
    draw.polygon(pts, fill=color)


def draw_cloud(draw, x, y, size, color) -> None:
    """여러 원을 겹친 둥근 구름."""
    for dx, dy, r in [(-1.1, 0, 0.75), (-0.4, -0.35, 0.95), (0.5, -0.3, 1.0),
                      (1.1, 0, 0.7), (0.1, 0.2, 0.9)]:
        rr = r * size
        draw.ellipse([x + dx * size - rr, y + dy * size - rr,
                      x + dx * size + rr, y + dy * size + rr], fill=color)


def draw_balloon(draw, x, y, size, color) -> None:
    """풍선 + 검은 실."""
    rx, ry = size, int(size * 1.2)
    draw.ellipse([x - rx, y - ry, x + rx, y + ry], fill=color)
    draw.polygon([(x - 7, y + ry), (x + 7, y + ry), (x, y + ry + 16)], fill=color)
    draw.line([(x, y + ry + 16), (x, y + ry + 130)], fill=(30, 30, 30), width=2)


def draw_lightning(draw, points, color) -> None:
    """지그재그 번개 (두께 5px)."""
    draw.line(points, fill=color, width=5, joint="curve")


def draw_ghost(draw, x, y, size, alpha) -> None:
    """반투명 유령 (투명 오버레이 draw에 그림). 둥근 머리 + 물결 하단."""
    c = (255, 255, 255, alpha)
    hw = size // 2
    draw.ellipse([x - hw, y - size * 0.55, x + hw, y + size * 0.15], fill=c)
    draw.rectangle([x - hw, y - size * 0.2, x + hw, y + size * 0.45], fill=c)
    bump = size / 5
    for k in range(-2, 3):
        bx = x + k * bump
        draw.ellipse([bx - bump * 0.55, y + size * 0.32, bx + bump * 0.55,
                      y + size * 0.6], fill=c)
    # 눈
    er = size * 0.09
    for ex in (x - size * 0.2, x + size * 0.2):
        draw.ellipse([ex - er, y - size * 0.25 - er, ex + er, y - size * 0.25 + er],
                     fill=(40, 0, 60, min(255, alpha + 120)))


def draw_tornado(draw, x, y, size) -> None:
    """반투명 회오리 토네이도 (위 넓고 아래 좁은 원뿔, 투명 오버레이 draw에)."""
    layers = 16
    for i in range(layers):
        frac = i / layers
        half = int(size * (1 - frac * 0.85))
        cy = int(y - size * 1.1 + frac * size * 2.2)
        a = int(150 * (1 - frac * 0.4))
        sway = int(math.sin(frac * 6) * size * 0.15)
        draw.ellipse([x + sway - half, cy - 16, x + sway + half, cy + 16],
                     fill=(170, 170, 185, a))


def soft_glow(img: Image.Image, x, y, r, color, alpha=110) -> None:
    """은은한 빛 번짐 (반투명 원 + 블러)."""
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse([x - r, y - r, x + r, y + r], fill=(*color, alpha))
    img.alpha_composite(g.filter(ImageFilter.GaussianBlur(int(r * 0.55))))


def draw_photo_area(img: Image.Image) -> None:
    """둥근 모서리 흰 매트 + 그림자 + 투명 사진창 (폴라로이드 느낌)."""
    x1, y1, x2, y2 = PHOTO
    radius = 46
    pad = 18
    # 1) 부드러운 그림자
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [x1 - pad + 6, y1 - pad + 14, x2 + pad + 6, y2 + pad + 14],
        radius=radius + 14, fill=(0, 0, 0, 90))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(16)))
    # 2) 흰색 매트 테두리
    ImageDraw.Draw(img).rounded_rectangle(
        [x1 - pad, y1 - pad, x2 + pad, y2 + pad], radius=radius + 10,
        fill=(255, 255, 255, 255))
    # 3) 둥근 사진창 투명 처리
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=255)
    arr = np.array(img)
    arr[..., 3] = np.where(np.array(mask) > 0, 0, arr[..., 3])
    img.paste(Image.fromarray(arr, "RGBA"), (0, 0))


def _load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return None


def draw_text_area(draw, text, emoji, color) -> None:
    """하단 밴드에 '<이모지> <감정텍스트>' 중앙 정렬."""
    font = _load_font(FONT_PATH, 80) or ImageFont.load_default()
    emoji_font = _load_font(EMOJI_PATH, 80)
    y = 1560
    tw = draw.textlength(text, font=font)
    ew = 90 if emoji_font else 0
    total = ew + (24 if ew else 0) + tw
    x = (W - total) / 2
    if emoji_font:
        try:
            draw.text((x, y), emoji, font=emoji_font, embedded_color=True)
        except Exception:
            pass
        x += ew + 24
    draw.text((x, y + 6), text, font=font, fill=color)


def _overlay():
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    return layer, ImageDraw.Draw(layer)


# ---- 6개 프레임 -----------------------------------------------------------
def create_joy_frame() -> Image.Image:
    img = create_gradient_background((W, H), "#87CEEB", "#E0F6FF")
    d = ImageDraw.Draw(img)
    sx, sy = 155, 155
    soft_glow(img, sx, sy, 180, (255, 235, 130), 150)  # 태양 빛번짐
    for i in range(8):  # 태양 광선 8개
        a = math.pi / 4 * i
        d.line([(sx, sy), (sx + 175 * math.cos(a), sy + 175 * math.sin(a))],
               fill=(255, 215, 0), width=13)
    d.ellipse([sx - 88, sy - 88, sx + 88, sy + 88], fill=(255, 215, 0))
    cols = ["#FF6B6B", "#FFD93D", "#6BCB77", "#4D96FF", "#FF6BE7", "#FFA36B"]
    spots = [(1055, 210), (1085, 500), (120, 520), (1060, 820), (150, 840), (600, 1470)]
    for i, (cx, cy) in enumerate(spots):
        draw_balloon(d, cx, cy, random.Random(i).randint(50, 60), _hex(cols[i % len(cols)]))
    draw_photo_area(img)
    draw_text_area(ImageDraw.Draw(img), "행복", "😊", (30, 30, 30))
    return img


def create_wow_frame() -> Image.Image:
    img = create_gradient_background((W, H), "#FFF200", "#FFD700")
    d = ImageDraw.Draw(img)
    rng = random.Random(21)
    cols = [(255, 255, 255), (255, 215, 0), (255, 165, 0)]
    # 중심 방사형 + 랜덤 폭죽
    ccx, ccy = W // 2, 650
    for gx, gy in [(160, 250), (1040, 260), (150, 1480), (1050, 1500)]:
        soft_glow(img, gx, gy, 90, (255, 255, 255), 120)  # 코너 반짝임
    for _ in range(46):
        if rng.random() < 0.45:
            ang = rng.uniform(0, math.tau)
            dist = rng.randint(60, 520)
            x, y = ccx + dist * math.cos(ang), ccy + dist * math.sin(ang)
        else:
            x, y = rng.randint(0, W), rng.randint(0, H)
        r = rng.randint(6, 22)
        c = rng.choice(cols)
        if rng.random() < 0.55:
            draw_star(d, x, y, r, c)
        else:
            d.ellipse([x - r, y - r, x + r, y + r], fill=c)
    draw_photo_area(img)
    draw_text_area(ImageDraw.Draw(img), "놀람", "😲", (30, 30, 30))
    return img


def create_calm_frame() -> Image.Image:
    img = create_gradient_background((W, H), "#4A4A4A", "#A0A0A0")
    d = ImageDraw.Draw(img)
    for cx, cy in [(230, 150), (600, 110), (990, 160)]:  # 먹구름
        draw_cloud(d, cx, cy, 130, _hex("#5A5A5A"))
    soft_glow(img, 585, 340, 90, (255, 235, 120), 130)  # 번개 빛
    draw_lightning(d, [(600, 210), (560, 320), (615, 320), (555, 450)], (255, 235, 120))
    rng = random.Random(7)
    for _ in range(140):  # 비
        x, y = rng.randint(0, W), rng.randint(0, H)
        ln = rng.randint(20, 40)
        d.line([(x, y), (x - int(ln * 0.27), y + ln)], fill=(240, 240, 255), width=2)
    draw_photo_area(img)
    draw_text_area(ImageDraw.Draw(img), "슬픔", "😢", (255, 255, 255))
    return img


def create_cool_frame() -> Image.Image:
    img = create_gradient_background((W, H), "#1A0000", "#B71C1C")
    d = ImageDraw.Draw(img)
    soft_glow(img, 600, 1400, 260, (255, 120, 0), 140)  # 화산 불빛
    for bx in (350, 600, 850):  # 화산 실루엣 여러 개
        d.polygon([(bx - 230, 1800), (bx, 1400), (bx + 230, 1800)], fill=(8, 8, 8))
    for cx in (520, 600, 680):  # 불꽃
        d.polygon([(cx - 45, 1420), (cx - 10, 1290), (cx, 1360), (cx + 12, 1280),
                   (cx + 45, 1420)], fill=_hex("#FF6B00"))
        d.polygon([(cx - 22, 1420), (cx, 1330), (cx + 22, 1420)], fill=_hex("#FFD700"))
    rng = random.Random(4)
    for _ in range(45):  # 불티
        x, y = rng.randint(320, 880), rng.randint(950, 1400)
        r = rng.randint(3, 8)
        d.ellipse([x - r, y - r, x + r, y + r],
                  fill=rng.choice([(255, 0, 0), (255, 107, 0)]))
    draw_photo_area(img)
    draw_text_area(ImageDraw.Draw(img), "분노", "😠", (255, 255, 255))
    return img


def create_chill_frame() -> Image.Image:
    img = create_gradient_background((W, H), "#E0F6FF", "#F5E6D3")
    layer, ld = _overlay()  # 반투명 흰 구름 (알파 200)
    for cx, cy, s in [(220, 170, 110), (700, 120, 150), (1010, 210, 95),
                      (380, 1500, 120), (930, 1560, 100)]:
        draw_cloud(ld, cx, cy, s, (255, 255, 255, 200))
    img.alpha_composite(layer)
    draw_photo_area(img)
    draw_text_area(ImageDraw.Draw(img), "무표정", "😐", (30, 30, 30))
    return img


def create_fear_frame() -> Image.Image:
    img = create_gradient_background((W, H), "#4A148C", "#1A0033")
    d = ImageDraw.Draw(img)
    # 초승달 (상단 테두리 우측, 보이는 영역) + 달빛
    soft_glow(img, 1040, 55, 90, (230, 230, 255), 120)
    d.ellipse([1000, 12, 1085, 97], fill=(245, 245, 220))
    d.ellipse([1022, 4, 1107, 89], fill=_hex("#4A148C"))
    # 별 (상단 얇은 테두리)
    rng = random.Random(9)
    for _ in range(16):
        draw_star(d, rng.randint(40, W - 40), rng.randint(15, 90),
                  rng.randint(8, 13), (255, 255, 255))
    # 토네이도 + 유령은 하단 밴드(보이는 영역)에 배치, 텍스트를 감싸도록
    layer, ld = _overlay()
    draw_tornado(ld, 260, 1500, 150)
    draw_ghost(ld, 980, 1470, 210, 95)
    img.alpha_composite(layer)
    draw_photo_area(img)
    draw_text_area(ImageDraw.Draw(img), "두려움", "😱", (255, 255, 255))
    return img


FRAMES = {
    "joy": create_joy_frame, "wow": create_wow_frame, "calm": create_calm_frame,
    "cool": create_cool_frame, "chill": create_chill_frame, "fear": create_fear_frame,
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ok = 0
    for name, builder in FRAMES.items():
        try:
            print(f"{name}.png 생성 중...")
            builder().save(OUT_DIR / f"{name}.png")
            print(f"{name}.png 생성 완료!")
            ok += 1
        except Exception as exc:  # 한 프레임 실패해도 계속
            print(f"[오류] {name}.png 생성 실패: {exc}")
    print(f"{ok}개 프레임 생성 완료! assets/frames/ 폴더 확인하세요.")


if __name__ == "__main__":
    main()
