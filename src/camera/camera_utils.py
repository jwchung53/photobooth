"""Camera discovery helpers.

``list_cameras`` returns human-readable device names (via pygrabber/DirectShow);
``find_available_camera`` probes indices and returns the first one that actually
delivers a frame. Both degrade gracefully - never raise to the caller.
"""

from __future__ import annotations

import cv2

from src.utils.logger import get_logger

log = get_logger(__name__)

# 탐색할 후보 인덱스
_CANDIDATE_INDICES = (0, 1, 2)


def list_cameras() -> list[str]:
    """Return connected camera device names (empty list on any failure)."""
    try:
        from pygrabber.dshow_graph import FilterGraph

        names = FilterGraph().get_input_devices()
        log.info("연결된 카메라: %s", names or "(없음)")
        return names
    except Exception as exc:  # noqa: BLE001 - pygrabber/COM 환경 이슈 방어
        log.warning("카메라 목록 조회 실패: %s", exc)
        return []


def find_available_camera(candidates: tuple[int, ...] = _CANDIDATE_INDICES) -> int | None:
    """Return the first index that opens AND yields a frame, else None."""
    for idx in candidates:
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        opened = cap.isOpened()
        ret = False
        if opened:
            ret, _ = cap.read()
        cap.release()
        if opened and ret:
            log.info("사용 가능한 카메라 발견: index=%d", idx)
            return idx
    log.warning("사용 가능한 카메라를 찾지 못했습니다 (후보=%s)", candidates)
    return None


if __name__ == "__main__":
    # 단독 테스트: 장치 목록 + 사용 가능한 인덱스 출력
    print("카메라 목록:")
    for i, name in enumerate(list_cameras()):
        print(f"  [{i}] {name}")
    print(f"사용 가능한 첫 인덱스: {find_available_camera()}")
