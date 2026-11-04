"""Watermark removal tests. Run: python tests/test_watermark.py
No network, no Playwright, no watermark engine needed.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import Config  # noqa: E402
from src.wm_clean import clean_generated_image  # noqa: E402


def test_disabled_returns_disabled():
    cfg = Config({"watermark": {"enabled": False}})
    result = clean_generated_image(Path("/tmp/nonexistent.png"), cfg)
    assert result == {"status": "disabled"}


def test_missing_file_returns_skipped():
    cfg = Config({"watermark": {"enabled": True, "engine_dir": "/tmp/whatever"}})
    result = clean_generated_image(Path("/tmp/nonexistent.png"), cfg)
    assert result["status"] == "skipped"


def test_missing_model_returns_skipped_never_raises():
    # watermark enabled, engine_dir points to a fake dir with no model
    # must return skipped, never raise
    cfg = Config({
        "watermark": {
            "enabled": True,
            "engine_dir": "/tmp/nonexistent_wm_engine",
            "model": "/tmp/nonexistent_wm_engine/models/lama_fp32.onnx",
        },
    })
    result = clean_generated_image(Path("/tmp/some_image.png"), cfg)
    assert result["status"] == "skipped", result


if __name__ == "__main__":
    test_disabled_returns_disabled()
    print("[ok] watermark disabled -> disabled")
    test_missing_file_returns_skipped()
    print("[ok] missing image file -> skipped")
    test_missing_model_returns_skipped_never_raises()
    print("[ok] missing model -> skipped, never raises")
    print("ALL WATERMARK TESTS PASSED")
