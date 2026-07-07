"""Sound effects via pygame.mixer.

Plays short kiosk cues: shutter, beep, success. All hardware/file access is
guarded so a missing sound file or an unavailable audio device never crashes
the app - it only logs a warning.
"""

from __future__ import annotations

from pathlib import Path

from src.utils.config import PROJECT_ROOT
from src.utils.logger import get_logger

log = get_logger(__name__)

# 사운드 파일 폴더 및 논리 이름 -> 파일 매핑 (매직 문자열 상수화)
SOUNDS_DIR = PROJECT_ROOT / "assets" / "sounds"
_SOUND_FILES: dict[str, str] = {
    "shutter": "shutter.wav",
    "beep": "beep.wav",
    "success": "success.wav",
}


class SoundPlayer:
    """Loads and plays named sound effects. Degrades gracefully when audio
    hardware or files are unavailable (common on dev machines / kiosks)."""

    def __init__(self, sounds_dir: Path | None = None) -> None:
        self.sounds_dir = sounds_dir or SOUNDS_DIR
        self._sounds: dict[str, object] = {}
        self._enabled = False
        self._init_mixer()
        if self._enabled:
            self._load_sounds()

    def _init_mixer(self) -> None:
        try:
            import pygame

            pygame.mixer.init()
            self._pygame = pygame
            self._enabled = True
            log.info("사운드 믹서 초기화 완료")
        except Exception as exc:  # 오디오 장치 없음 등
            self._pygame = None
            self._enabled = False
            log.warning("사운드 믹서 초기화 실패 - 무음 모드로 동작: %s", exc)

    def _load_sounds(self) -> None:
        for name, filename in _SOUND_FILES.items():
            path = self.sounds_dir / filename
            if not path.exists():
                log.warning("사운드 파일 없음 (건너뜀): %s", path)
                continue
            try:
                self._sounds[name] = self._pygame.mixer.Sound(str(path))
                log.debug("사운드 로드: %s", name)
            except Exception as exc:
                log.warning("사운드 로드 실패 %s: %s", path, exc)

    def play(self, name: str) -> None:
        """Play a named sound effect. No-op if unavailable."""
        if not self._enabled:
            return
        sound = self._sounds.get(name)
        if sound is None:
            log.debug("재생할 사운드 없음: %s", name)
            return
        try:
            sound.play()
        except Exception as exc:
            log.warning("사운드 재생 실패 %s: %s", name, exc)

    # 편의 메서드
    def shutter(self) -> None:
        self.play("shutter")

    def beep(self) -> None:
        self.play("beep")

    def success(self) -> None:
        self.play("success")

    def close(self) -> None:
        """Release the audio device."""
        if self._enabled and self._pygame is not None:
            try:
                self._pygame.mixer.quit()
            except Exception:
                pass


if __name__ == "__main__":
    # 단독 테스트: 믹서 초기화 후 각 효과음 재생 시도 (파일 없으면 경고만)
    import time

    player = SoundPlayer()
    for cue in ("shutter", "beep", "success"):
        print(f"[sound] play: {cue}")
        player.play(cue)
        time.sleep(0.8)
    player.close()
    print("사운드 셀프테스트 완료 (파일이 없으면 무음이 정상입니다)")
