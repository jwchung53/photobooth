"""Emotion Photo Booth - source package.

OpenCV reads its VIDEOIO env vars when ``cv2`` is imported, so the MSMF tweak
below must run before any submodule does ``import cv2``. This package's
``__init__`` is the earliest such point.
"""

import os

# MSMF 백엔드는 하드웨어 변환 파이프라인이 켜져 있으면 카메라 오픈에 ~10초가 걸린다.
# 끄면 ~0.5초. (외장 웹캠은 DSHOW로 안 열려서 MSMF를 쓴다)
os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")
