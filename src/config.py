"""Config loader: config.yaml + ${ENV} expansion + .env support."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from .utils import PROJECT_ROOT, log

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _expand(value: Any) -> Any:
    if isinstance(value, str):
        return _ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), m.group(2) or ""), value)
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    return value


class Config:
    """Thin dict wrapper with dotted access: cfg.get('gemini.selectors.file_input')."""

    def __init__(self, data: dict[str, Any], path: Path | None = None):
        self.data = data
        self.path = path

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def root(self) -> Path:
        return PROJECT_ROOT

    def out_root(self) -> Path:
        p = Path(self.get("output.root", "output"))
        return p if p.is_absolute() else PROJECT_ROOT / p

    def asin_dir(self, asin: str) -> Path:
        return self.out_root() / asin

    def resolve(self, value: str | Path) -> Path:
        p = Path(value)
        return p if p.is_absolute() else PROJECT_ROOT / p


def load_config(path: str | Path | None = None) -> Config:
    _load_dotenv(PROJECT_ROOT / ".env")
    candidates = [Path(path)] if path else [
        PROJECT_ROOT / "config.yaml",
        PROJECT_ROOT / "config.example.yaml",
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            data = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
            data = _expand(data)
            # `python run.py ... --headed` sets HEADED=1 -> show the browser
            if os.environ.get("HEADED"):
                data.setdefault("browser", {})["headless"] = False
            cfg = Config(data, candidate)
            log.debug("config loaded from %s", candidate)
            return cfg
    raise FileNotFoundError("No config.yaml found. Copy config.example.yaml -> config.yaml")
