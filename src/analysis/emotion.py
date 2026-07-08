"""Face detection + emotion analysis via DeepFace (RetinaFace backend).

Detects every face in a frame, reads its 7-way emotion distribution, and
remaps the dominant emotion onto one of the five positive frame categories.
DeepFace/TensorFlow are imported lazily because they are heavy to load.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from src.utils.config import get_config
from src.utils.logger import get_logger

log = get_logger(__name__)

# DeepFace 7감정 -> 5 프레임 카테고리 (모든 결과가 긍정적으로 보이도록)
EMOTION_TO_FRAME: dict[str, str] = {
    "happy": "joy",
    "surprise": "wow",
    "sad": "calm",
    "angry": "cool",
    "disgust": "cool",
    "fear": "chill",
    "neutral": "chill",
}
DEFAULT_FRAME = "chill"

# 다인 촬영 시 대표 프레임 선정 tie-break 우선순위 (긍정 우선)
FRAME_PRIORITY: list[str] = ["joy", "wow", "chill", "calm", "cool"]

# 감정 한글 표기 (콘솔/디버그/UI 라벨용)
EMOTION_KO: dict[str, str] = {
    "happy": "행복",
    "surprise": "놀람",
    "sad": "슬픔",
    "angry": "화남",
    "disgust": "불쾌",
    "fear": "두려움",
    "neutral": "무표정",
}

# 감정 이모지 (분석 화면 팝업 / 미리보기 라벨용)
EMOTION_EMOJI: dict[str, str] = {
    "happy": "😊",
    "surprise": "😮",
    "sad": "😢",
    "angry": "😠",
    "disgust": "🤢",
    "fear": "😨",
    "neutral": "😐",
}


def map_emotion_to_frame(emotion: str) -> str:
    """Map a DeepFace emotion label to a frame category."""
    return EMOTION_TO_FRAME.get(emotion.lower(), DEFAULT_FRAME)


def select_frame_category(faces: list["FaceResult"]) -> str:
    """Pick one representative frame category for a multi-face photo.

    Uses majority vote, breaking ties by the positive-first priority order.
    """
    if not faces:
        return DEFAULT_FRAME
    counts = Counter(f.frame_category for f in faces)
    top_n = max(counts.values())
    tied = [cat for cat, n in counts.items() if n == top_n]
    for cat in FRAME_PRIORITY:
        if cat in tied:
            return cat
    return tied[0]


@dataclass
class FaceResult:
    """One detected face: bounding box + emotion + mapped frame category."""

    box: tuple[int, int, int, int]  # (x, y, w, h)
    dominant_emotion: str
    frame_category: str
    scores: dict[str, float]
    confidence: float

    def __str__(self) -> str:
        ko = EMOTION_KO.get(self.dominant_emotion, self.dominant_emotion)
        return (
            f"얼굴 box={self.box} 감정={ko}({self.dominant_emotion}) "
            f"→ 프레임={self.frame_category} conf={self.confidence:.2f}"
        )


class EmotionAnalyzer:
    """Runs DeepFace.analyze and converts the output to ``FaceResult`` list."""

    def __init__(
        self,
        detector_backend: str | None = None,
        min_confidence: float | None = None,
    ) -> None:
        cfg = get_config()
        self.detector_backend = detector_backend or cfg.get(
            "analysis.detector_backend", "retinaface"
        )
        self.min_confidence = (
            min_confidence
            if min_confidence is not None
            else float(cfg.get("analysis.min_face_confidence", 0.9))
        )

    def analyze(self, image_bgr) -> list[FaceResult]:
        """Detect faces and analyze emotion. Returns [] on failure/no face."""
        # 지연 임포트: DeepFace/TensorFlow 로딩 비용을 실제 사용 시점으로 미룸
        try:
            from deepface import DeepFace
        except Exception as exc:  # noqa: BLE001
            log.error("DeepFace 임포트 실패: %s", exc)
            return []

        try:
            raw = DeepFace.analyze(
                img_path=image_bgr,
                actions=["emotion"],
                detector_backend=self.detector_backend,
                enforce_detection=False,  # 얼굴 없어도 예외 대신 빈 결과 처리
                silent=True,
            )
        except Exception as exc:  # noqa: BLE001
            log.error("감정 분석 실패: %s", exc)
            return []

        # DeepFace는 단일/다중 얼굴 모두 list[dict]로 반환
        if isinstance(raw, dict):
            raw = [raw]

        # 원본 크기 (무검출 fallback 판별용)
        try:
            img_h, img_w = image_bgr.shape[:2]
        except Exception:  # noqa: BLE001
            img_h, img_w = 0, 0

        faces: list[FaceResult] = []
        for item in raw:
            region = item.get("region", {}) or {}
            box = (
                int(region.get("x", 0)),
                int(region.get("y", 0)),
                int(region.get("w", 0)),
                int(region.get("h", 0)),
            )
            confidence = float(
                item.get("face_confidence", region.get("face_confidence", 0.0)) or 0.0
            )
            if box[2] <= 0 or box[3] <= 0:
                continue
            # 무검출 시 DeepFace가 전체 이미지를 얼굴로 반환하는 fallback 제거 (기하학적 판별)
            if (
                img_w
                and box[0] == 0
                and box[1] == 0
                and box[2] >= img_w * 0.98
                and box[3] >= img_h * 0.98
            ):
                continue
            # 신뢰도 필터는 백엔드가 신뢰도를 제공할 때만 적용
            # (opencv 등은 face_confidence=0 -> 필터 건너뜀)
            if confidence and confidence < self.min_confidence:
                continue

            emotion = str(item.get("dominant_emotion", "neutral"))
            scores = {k: float(v) for k, v in (item.get("emotion", {}) or {}).items()}
            faces.append(
                FaceResult(
                    box=box,
                    dominant_emotion=emotion,
                    frame_category=map_emotion_to_frame(emotion),
                    scores=scores,
                    confidence=confidence,
                )
            )

        log.info("감정 분석 완료: 얼굴 %d개 검출", len(faces))
        return faces


if __name__ == "__main__":
    # 단독 테스트: python -m src.analysis.emotion <이미지경로>
    import sys

    import cv2

    if len(sys.argv) < 2:
        print("사용법: python -m src.analysis.emotion <이미지경로>")
        raise SystemExit(1)

    img = cv2.imread(sys.argv[1])
    if img is None:
        print(f"이미지를 읽을 수 없습니다: {sys.argv[1]}")
        raise SystemExit(1)

    analyzer = EmotionAnalyzer()
    results = analyzer.analyze(img)
    if not results:
        print("얼굴을 찾지 못했습니다.")
    for i, face in enumerate(results, 1):
        print(f"[{i}] {face}")
    print(f"대표 프레임 카테고리: {select_frame_category(results)}")
