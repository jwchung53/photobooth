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

# 로그용 백엔드 이름. None = OpenCV 기본 백엔드 (백엔드 인자 없이 열기)
_BACKEND_LABELS = {cv2.CAP_DSHOW: "DSHOW", cv2.CAP_MSMF: "MSMF", cv2.CAP_ANY: "ANY"}


def backend_label(backend: int | None) -> str:
    """Return a human-readable name for an OpenCV capture backend."""
    if backend is None:
        return "기본(backend 미지정)"
    return _BACKEND_LABELS.get(backend, f"backend={backend}")


def open_capture(index: int, backend: int | None = None) -> cv2.VideoCapture:
    """Open a VideoCapture; ``backend=None`` uses OpenCV's default backend."""
    if backend is None:
        return cv2.VideoCapture(index)
    return cv2.VideoCapture(index, backend)


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


def find_camera_by_name(name: str) -> int | None:
    """Return the index of the first camera whose name contains ``name``.

    Case-insensitive substring match against pygrabber device names. The device
    order matches OpenCV's DirectShow index order. Returns None if not found.
    """
    if not name or not str(name).strip():
        return None
    target = str(name).strip().lower()
    for idx, dev in enumerate(list_cameras()):
        if target in dev.lower():
            log.info("이름 매칭 카메라 선택: index=%d ('%s' ⊇ '%s')", idx, dev, name)
            return idx
    log.info("이름에 '%s' 포함된 카메라를 찾지 못함 -> index 폴백", name)
    return None


def find_available_camera(
    candidates: tuple[int, ...] = _CANDIDATE_INDICES, backend: int | None = cv2.CAP_DSHOW
) -> int | None:
    """Return the first index that opens AND yields a frame, else None.

    ``backend=None`` probes with OpenCV's default backend.
    """
    label = backend_label(backend)
    for idx in candidates:
        cap = open_capture(idx, backend)
        opened = cap.isOpened()
        ret = False
        if opened:
            ret, _ = cap.read()
        cap.release()
        if opened and ret:
            log.info("사용 가능한 카메라 발견: index=%d (backend=%s)", idx, label)
            return idx
    log.warning(
        "사용 가능한 카메라를 찾지 못했습니다 (후보=%s, backend=%s)", candidates, label
    )
    return None


if __name__ == "__main__":
    # 단독 테스트: 장치 목록 + 백엔드별로 어떤 인덱스가 실제로 열리는지 출력
    print("카메라 목록:")
    for i, name in enumerate(list_cameras()):
        print(f"  [{i}] {name}")

    print("\n백엔드별 프레임 확인:")
    for be in (cv2.CAP_DSHOW, cv2.CAP_MSMF, None):
        for idx in _CANDIDATE_INDICES:
            cap = open_capture(idx, be)
            ok = cap.isOpened() and cap.read()[0]
            cap.release()
            print(f"  {backend_label(be):>18} index={idx}: {'OK' if ok else '실패'}")
