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

# DeepFace 7감정 -> 6 프레임 카테고리 (모든 결과가 긍정적으로 보이도록)
# fear는 chill에서 분리해 독립 카테고리(판타지 컨셉)로 재해석
EMOTION_TO_FRAME: dict[str, str] = {
    "happy": "joy",
    "surprise": "wow",
    "sad": "calm",
    "angry": "cool",
    "disgust": "cool",
    "fear": "fear",
    "neutral": "chill",
}
DEFAULT_FRAME = "chill"

# 다인 촬영 시 대표 프레임 선정 tie-break 우선순위 (긍정 우선)
FRAME_PRIORITY: list[str] = ["joy", "wow", "fear", "chill", "calm", "cool"]

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
        self.rel_size_ratio = float(cfg.get("analysis.rel_size_ratio", 0.35))
        self.min_area_pct = float(cfg.get("analysis.min_face_area_pct", 0.8))
        self.dedup_iou = float(cfg.get("analysis.dedup_iou", 0.4))
        self.neutral_bias = float(cfg.get("analysis.neutral_bias", 0.5))

    def _pick_dominant(self, scores: dict) -> str:
        """Pick the dominant emotion, discounting neutral so expressions surface."""
        if not scores:
            return "neutral"
        adjusted = dict(scores)
        if "neutral" in adjusted:
            adjusted["neutral"] *= self.neutral_bias
        return max(adjusted, key=adjusted.get)

    @staticmethod
    def _iou(a: tuple, b: tuple) -> float:
        """Intersection-over-union of two (x, y, w, h) boxes."""
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        ix1, iy1 = max(ax, bx), max(ay, by)
        ix2, iy2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        union = aw * ah + bw * bh - inter
        return inter / union if union > 0 else 0.0

    def _postprocess(self, faces: list["FaceResult"], img_w: int, img_h: int) -> list["FaceResult"]:
        """Merge duplicate boxes, then drop background faces by relative size.

        The largest face is always kept (so a valid poser is never filtered to
        zero); others must be a big-enough fraction of the largest AND above a
        tiny absolute floor.
        """
        if not faces:
            return faces
        # 1) 중복 박스 제거 (큰 얼굴 우선)
        deduped: list[FaceResult] = []
        for f in sorted(faces, key=lambda f: f.box[2] * f.box[3], reverse=True):
            if all(self._iou(f.box, k.box) < self.dedup_iou for k in deduped):
                deduped.append(f)
        if not deduped:
            return deduped

        # 2) 상대 크기 필터 (가장 큰 얼굴 기준) - 최대 얼굴은 항상 유지
        largest = deduped[0]  # 면적 내림차순 정렬됨
        max_area = largest.box[2] * largest.box[3] or 1
        img_area = (img_w * img_h) or 1
        out: list[FaceResult] = [largest]
        for f in deduped[1:]:
            area = f.box[2] * f.box[3]
            if area < max_area * self.rel_size_ratio:
                continue  # 가장 큰 얼굴 대비 너무 작음 (먼 배경)
            if (area / img_area * 100) < self.min_area_pct:
                continue  # 순수 노이즈
            out.append(f)
        return out

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

            scores = {k: float(v) for k, v in (item.get("emotion", {}) or {}).items()}
            emotion = self._pick_dominant(scores)  # neutral 억제 반영
            faces.append(
                FaceResult(
                    box=box,
                    dominant_emotion=emotion,
                    frame_category=map_emotion_to_frame(emotion),
                    scores=scores,
                    confidence=confidence,
                )
            )

        before = len(faces)
        faces = self._postprocess(faces, img_w, img_h)
        if before != len(faces):
            log.info("후처리: %d개 -> %d개 (크기/중복 필터)", before, len(faces))
        log.info("감정 분석 완료: 얼굴 %d개 검출", len(faces))
        return faces

    @staticmethod
    def _expressiveness(scores: dict) -> float:
        """Strength of the strongest NON-neutral emotion (표정이 얼마나 뚜렷한가)."""
        return max((v for k, v in scores.items() if k != "neutral"), default=0.0)

    def analyze_stabilized(self, frames: list) -> list["FaceResult"]:
        """Analyze a few frames properly (detect+align) and, per face, adopt the
        reading with the strongest non-neutral expression (peak). This surfaces a
        brief smile/surprise instead of averaging everything toward neutral.
        """
        if not frames:
            return []
        n = len(frames)
        # 균등하게 최대 3프레임만 제대로 분석 (속도) - 마지막이 대표
        idxs = sorted(set([0, n // 2, n - 1]))
        per_frame = [self.analyze(frames[i]) for i in idxs]
        primary = per_frame[-1]
        others = per_frame[:-1]
        if not primary or not others:
            return primary

        for face in primary:
            best_scores = face.scores
            best_expr = self._expressiveness(face.scores)
            for other in others:
                # 같은 얼굴(IoU)을 찾아 표정이 더 강하면 채택
                match = None
                best_iou = 0.3
                for g in other:
                    iou = self._iou(face.box, g.box)
                    if iou > best_iou:
                        best_iou, match = iou, g
                if match is not None:
                    expr = self._expressiveness(match.scores)
                    if expr > best_expr:
                        best_expr, best_scores = expr, match.scores
            face.scores = best_scores
            face.dominant_emotion = self._pick_dominant(best_scores)
            face.frame_category = map_emotion_to_frame(face.dominant_emotion)

        log.info("감정 안정화: %d프레임 중 표정 강한 것 채택", len(idxs))
        return primary


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
