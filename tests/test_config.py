"""Config validation tests. Run: python tests/test_config.py
No network, no Playwright, no Gemini needed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import Config, ConfigError, load_config  # noqa: E402


def test_missing_required_field_raises():
    cfg = Config({"browser": {"headless": True}})
    try:
        cfg.validate()
        raise AssertionError("should have raised ConfigError")
    except ConfigError as exc:
        assert "amazon.domain" in str(exc)


def test_env_expansion():
    os.environ["AMZ_TEST_VAR"] = "hello-world"
    cfg = Config({"key": "${AMZ_TEST_VAR}"})
    assert cfg.get("key") == "hello-world"


def test_env_expansion_with_default():
    cfg = Config({"key": "${UNDEFINED_VAR:-fallback}"})
    assert cfg.get("key") == "fallback"


def test_dotted_get():
    cfg = Config({"a": {"b": {"c": 42}}})
    assert cfg.get("a.b.c") == 42
    assert cfg.get("a.b.missing", "default") == "default"


def test_watermark_engine_required_when_enabled():
    cfg = Config({
        "amazon": {"domain": "amazon.in"},
        "output": {"root": "output"},
        "gemini": {"url": "https://gemini.google.com/app"},
        "watermark": {"enabled": True},
    })
    try:
        cfg.validate()
        raise AssertionError("should have raised ConfigError")
    except ConfigError as exc:
        assert "watermark.engine_dir" in str(exc)


def test_watermark_engine_not_required_when_disabled():
    # should not raise even without engine_dir when disabled
    cfg = Config({
        "amazon": {"domain": "amazon.in"},
        "output": {"root": "output"},
        "gemini": {"url": "https://gemini.google.com/app"},
        "watermark": {"enabled": False},
    })
    cfg.validate()
    assert cfg.get("watermark.enabled") is False


def test_load_config_validates_config_yaml():
    # config.yaml ships with all required fields; this should not raise ConfigError
    try:
        load_config(str(ROOT / "config.yaml"))
    except FileNotFoundError:
        pass  # config.yaml may not exist yet; that's fine for this test


if __name__ == "__main__":
    test_missing_required_field_raises()
    print("[ok] missing required field raises ConfigError")
    test_env_expansion()
    print("[ok] ${ENV} expansion works")
    test_env_expansion_with_default()
    print("[ok] ${ENV:-default} expansion works")
    test_dotted_get()
    print("[ok] dotted key access works")
    test_watermark_engine_required_when_enabled()
    print("[ok] watermark.engine_dir required when watermark.enabled")
    test_watermark_engine_not_required_when_disabled()
    print("[ok] watermark.engine_dir not required when disabled")
    test_load_config_validates_config_yaml()
    print("[ok] load_config validates config.yaml")
    print("ALL CONFIG TESTS PASSED")
