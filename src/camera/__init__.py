"""Camera module - USB webcam capture with backend fallback (DSHOW/MSMF/기본).

The MSMF slow-open workaround lives in ``src/__init__.py`` - it must run before
``cv2`` is imported anywhere.
"""
