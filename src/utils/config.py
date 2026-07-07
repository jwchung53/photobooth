"""Config loader and accessor for config.yaml.

Loads the YAML config once and provides dotted-key access, e.g.
``config.get("camera.width")``. Keeps all tunable values out of the code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# 프로젝트 루트: src/utils/config.py 기준 두 단계 위
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


class Config:
    """Wraps the parsed config.yaml with dotted-key access."""

    def __init__(self, data: dict[str, Any], source: Path | None = None) -> None:
        self._data = data
        self.source = source

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Config":
        """Load config from the given path (defaults to <root>/config.yaml)."""
        cfg_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
        if not cfg_path.exists():
            raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {cfg_path}")
        with cfg_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(data, source=cfg_path)

    def get(self, key: str, default: Any = None) -> Any:
        """Fetch a value by dotted key, e.g. "camera.width".

        Returns ``default`` if any segment along the path is missing.
        """
        node: Any = self._data
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def require(self, key: str) -> Any:
        """Like get() but raises KeyError when the key is absent."""
        sentinel = object()
        value = self.get(key, sentinel)
        if value is sentinel:
            raise KeyError(f"필수 설정값이 없습니다: {key}")
        return value

    def resolve_path(self, key: str, default: str | None = None) -> Path:
        """Resolve a config path value against the project root."""
        raw = self.get(key, default)
        if raw is None:
            raise KeyError(f"경로 설정값이 없습니다: {key}")
        p = Path(raw)
        return p if p.is_absolute() else PROJECT_ROOT / p

    def as_dict(self) -> dict[str, Any]:
        """Return the raw config dict."""
        return self._data


# 모듈 레벨 편의 함수 (싱글턴처럼 사용)
_default: Config | None = None


def get_config(path: str | Path | None = None, reload: bool = False) -> Config:
    """Return a cached default Config instance."""
    global _default
    if _default is None or reload:
        _default = Config.load(path)
    return _default


if __name__ == "__main__":
    # 단독 테스트: config.yaml 로드 후 주요 값 출력
    cfg = Config.load()
    print(f"[config] loaded from: {cfg.source}")
    print(f"  camera.index  = {cfg.get('camera.index')}")
    print(f"  camera.width  = {cfg.get('camera.width')}")
    print(f"  camera.height = {cfg.get('camera.height')}")
    print(f"  output.dir    = {cfg.get('output.dir')}  -> {cfg.resolve_path('output.dir')}")
    print(f"  frames.dir    = {cfg.get('frames.dir')}  -> {cfg.resolve_path('frames.dir')}")
    print(f"  logging.level = {cfg.get('logging.level')}")
    print(f"  missing.key   = {cfg.get('missing.key', '(default)')}")
