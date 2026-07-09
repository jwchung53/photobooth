"""Background emotion-analysis thread for the UI.

Reuses the Phase 1 ``EmotionAnalyzer`` (RetinaFace detection + DeepFace emotion)
off the UI thread. Because that analyzer detects and classifies in a single
pass, the results are replayed as staged signals (per-face detection, then
per-face emotion) so the analysis screen can animate progress.

Detection runs on a downscaled copy - the capture is 1440x1080 for print
quality, but feeding that to the detector costs ~4.7s versus ~1.2s at 640px
wide with identical results. Emitted boxes are scaled back to the original
photo's coordinates, so callers never see the downscale.
"""

from __future__ import annotations

import cv2
import numpy as np

from PyQt6.QtCore import QThread, pyqtSignal

from src.analysis.emotion import EmotionAnalyzer
from src.utils.logger import get_logger, log_duration

log = get_logger(__name__)

# 애니메이션용 단계 간 지연 (ms)
_STEP_MS = 400
# 검출/감정 분석에 쓰는 최대 가로 폭 (이보다 크면 축소). 정확도 손실 없이 4배 빠름
_ANALYSIS_WIDTH = 640


class AnalysisThread(QThread):
    """Runs emotion analysis and emits staged progress signals."""

    progress = pyqtSignal(int, str)            # (%, 메시지)
    face_detected = pyqtSignal(int, dict)      # (얼굴 번호, {bbox, confidence})
    emotion_detected = pyqtSignal(int, str, float)  # (얼굴 번호, 감정, 신뢰도)
    finished_all = pyqtSignal(list)            # [{bbox, emotion, category, ...}, ...]
    error_occurred = pyqtSignal(str)

    def __init__(self, photo: np.ndarray, frames: list | None = None) -> None:
        super().__init__()
        self.photo = photo
        # 감정 안정화용 버스트 프레임 (없으면 단일 프레임으로 처리)
        self.frames = frames if frames else [photo]

    @staticmethod
    def _downscale(frames: list[np.ndarray]) -> tuple[list[np.ndarray], float]:
        """Shrink frames to ``_ANALYSIS_WIDTH``; returns them + the scale used."""
        width = frames[0].shape[1]
        if width <= _ANALYSIS_WIDTH:
            return frames, 1.0
        scale = _ANALYSIS_WIDTH / width
        small = [
            cv2.resize(f, (int(f.shape[1] * scale), int(f.shape[0] * scale)),
                       interpolation=cv2.INTER_AREA)
            for f in frames
        ]
        log.info("분석용 축소: %dx%d -> %dx%d",
                 width, frames[0].shape[0], small[0].shape[1], small[0].shape[0])
        return small, scale

    def run(self) -> None:  # QThread 진입점 (별도 스레드)
        try:
            self.progress.emit(10, "얼굴을 찾는 중...")
            analyzer = EmotionAnalyzer()
            small, scale = self._downscale(self.frames)
            with log_duration(log, "얼굴 검출+감정 분석"):
                faces = analyzer.analyze_stabilized(small)  # 검출 + 감정 투표

            if not faces:
                log.info("얼굴 미검출")
                self.error_occurred.emit("얼굴을 찾을 수 없어요. 다시 찍어보시겠어요?")
                return

            # 축소본 좌표 -> 원본 좌표 (호출자는 항상 원본 기준 bbox를 받는다)
            if scale != 1.0:
                inv = 1.0 / scale
                for f in faces:
                    f.box = tuple(int(v * inv) for v in f.box)

            # 1) 얼굴 검출 단계 (박스 애니메이션)
            for i, f in enumerate(faces):
                self.face_detected.emit(i, {"bbox": f.box, "confidence": f.confidence})
                self.msleep(_STEP_MS)

            # 2) 감정 분석 단계 (이모지 팝업)
            self.progress.emit(40, "감정을 분석하는 중...")
            for i, f in enumerate(faces):
                score = float(f.scores.get(f.dominant_emotion, 0.0))
                self.emotion_detected.emit(i, f.dominant_emotion, score)
                self.msleep(_STEP_MS)

            # 3) 프레임 매핑 & 합성 준비
            self.progress.emit(70, "프레임을 만드는 중...")
            self.msleep(_STEP_MS)
            self.progress.emit(90, "합성 중...")

            results = [
                {
                    "bbox": f.box,
                    "emotion": f.dominant_emotion,
                    "category": f.frame_category,
                    "confidence": f.confidence,
                    "scores": f.scores,
                }
                for f in faces
            ]
            self.progress.emit(100, "완료!")
            log.info(
                "분석 완료: %d명 감정=%s",
                len(results),
                [f"{r['emotion']}({r['category']})" for r in results],
            )
            self.finished_all.emit(results)

        except Exception as exc:  # noqa: BLE001 - 크래시 절대 금지
            log.exception("분석 스레드 오류")
            self.error_occurred.emit("분석 중 문제가 생겼어요. 다시 시도해주세요.")


if __name__ == "__main__":
    # 단독 테스트: 이미지 경로를 받아 분석 결과를 콘솔에 출력
    import sys

    import cv2

    from PyQt6.QtCore import QCoreApplication

    if len(sys.argv) < 2:
        print("사용법: python -m src.analysis.analysis_thread <이미지경로>")
        raise SystemExit(1)

    img = cv2.imread(sys.argv[1])
    if img is None:
        print(f"이미지를 읽을 수 없습니다: {sys.argv[1]}")
        raise SystemExit(1)

    app = QCoreApplication(sys.argv)
    thread = AnalysisThread(img)
    thread.progress.connect(lambda p, m: print(f"[{p:3d}%] {m}"))
    thread.face_detected.connect(lambda n, info: print(f"  얼굴 {n}: {info}"))
    thread.emotion_detected.connect(lambda n, e, c: print(f"  감정 {n}: {e} ({c:.1f})"))
    thread.error_occurred.connect(lambda m: (print(f"[오류] {m}"), app.quit()))
    thread.finished_all.connect(lambda r: (print(f"결과: {r}"), app.quit()))
    thread.start()
    sys.exit(app.exec())
