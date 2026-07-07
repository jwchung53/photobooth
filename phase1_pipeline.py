"""Phase 1 console MVP pipeline: capture -> analyze -> compose -> save.

Runs the whole flow from the terminal with no GUI. Use ``--image PATH`` to
feed an existing photo instead of the live camera (handy for testing the
analysis/compose stages without a webcam).
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2

from src.analysis.emotion import EMOTION_KO, EmotionAnalyzer, FaceResult
from src.camera.capture import Camera, CameraError
from src.compose.composer import Composer
from src.utils.config import Config
from src.utils.logger import get_logger, setup_logging
from src.utils.sound import SoundPlayer


def _acquire_from_camera(sound: SoundPlayer, countdown: int):
    """Run a countdown, play the shutter, and grab one frame from the camera."""
    with Camera() as cam:
        print("\n카메라를 바라봐 주세요!")
        for remaining in range(countdown, 0, -1):
            print(f"  {remaining}...")
            sound.beep()
            time.sleep(1)
        sound.shutter()
        print("  찰칵!")
        return cam.capture()


def _print_face_summary(faces: list[FaceResult]) -> None:
    """Print a friendly Korean summary of the detected emotions."""
    if not faces:
        print("얼굴을 찾지 못했어요. 그래도 예쁜 프레임을 씌워드릴게요!")
        return
    print(f"{len(faces)}명을 찾았어요:")
    for i, face in enumerate(faces, 1):
        ko = EMOTION_KO.get(face.dominant_emotion, face.dominant_emotion)
        print(f"  [{i}] {ko} → '{face.frame_category}' 프레임")


def run(image_path: str | None = None) -> Path:
    """Execute the full pipeline once and return the saved file path."""
    config = Config.load()
    setup_logging(config)
    log = get_logger("phase1")
    log.info("Phase 1 파이프라인 시작 (image=%s)", image_path or "camera")

    sound = SoundPlayer()
    countdown = int(config.get("pipeline.countdown", 3))

    # 1) 이미지 확보 (파일 또는 카메라)
    if image_path:
        frame = cv2.imread(image_path)
        if frame is None:
            raise FileNotFoundError(f"이미지를 읽을 수 없습니다: {image_path}")
        print(f"입력 이미지 사용: {image_path}")
    else:
        frame = _acquire_from_camera(sound, countdown)

    # 2) 감정 분석
    print("\n감정을 분석하는 중...")
    analyzer = EmotionAnalyzer()
    faces = analyzer.analyze(frame)
    _print_face_summary(faces)

    # 3) 합성
    print("\n프레임을 합성하는 중...")
    composer = Composer()
    result = composer.compose(frame, faces)

    # 4) 저장
    out_path = composer.save(result)
    sound.success()
    print(f"\n완성됐어요! → {out_path}")

    sound.close()
    log.info("Phase 1 파이프라인 종료")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Emotion Photo Booth - Phase 1 콘솔 파이프라인")
    parser.add_argument(
        "--image",
        metavar="PATH",
        help="카메라 대신 사용할 입력 이미지 경로 (테스트용)",
    )
    args = parser.parse_args()

    try:
        run(image_path=args.image)
        return 0
    except CameraError as exc:
        print(f"\n[카메라 오류] {exc}")
        print("카메라 연결을 확인하거나, --image 옵션으로 이미지를 지정해 테스트하세요.")
        return 1
    except FileNotFoundError as exc:
        print(f"\n[입력 오류] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
