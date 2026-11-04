"""Bot command handler tests. Run: python tests/test_bot_commands.py
No network, no Playwright needed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import Config  # noqa: E402
from src.bot_commands import cmd_status, cmd_clean  # noqa: E402


def make_cfg():
    return Config({
        "amazon": {"domain": "amazon.in"},
        "output": {"root": str(ROOT / "output" / "_bot_test")},
        "watermark": {"enabled": False},
    })


def write_manifest(asin: str, cfg: Config, slots: dict):
    adir = Path(cfg.asin_dir(asin))
    adir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "asin": asin,
        "stages": {"generate": {"status": "generated", "ok": 8, "failed": 0}},
        "slots": slots,
    }
    (adir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return adir


def test_cmd_status_returns_manifest_summary():
    cfg = make_cfg()
    slots = {
        "01_hero_white": {"status": "ok", "file": "generated/01_hero_white.png", "attempts": 1},
        "02_back_view": {"status": "ok", "file": "generated/02_back_view.png", "attempts": 1},
        "03_side_view": {"status": "failed", "error": "timeout", "attempts": 3},
    }
    write_manifest("B0BOT01", cfg, slots)

    result = cmd_status("B0BOT01", cfg)
    assert result["asin"] == "B0BOT01"
    assert result["slots_done"] == "2/3"
    assert result["status"] == "partial"
    assert result["slots"]["03_side_view"]["status"] == "failed"


def test_cmd_status_missing_manifest():
    cfg = make_cfg()
    result = cmd_status("B0NOPE", cfg)
    assert result["status"] == "not_found"
    assert "no manifest" in result.get("error", "").lower()


def test_cmd_clean_disabled_watermark():
    cfg = make_cfg()
    adir = Path(cfg.asin_dir("B0CLEAN01"))
    adir.mkdir(parents=True, exist_ok=True)
    (adir / "generated").mkdir(parents=True, exist_ok=True)

    result = cmd_clean("B0CLEAN01", cfg)
    assert result == {}


if __name__ == "__main__":
    test_cmd_status_returns_manifest_summary()
    print("[ok] /status returns manifest summary with slots_done")
    test_cmd_status_missing_manifest()
    print("[ok] /status on unknown ASIN returns not_found")
    test_cmd_clean_disabled_watermark()
    print("[ok] /clean with watermark disabled returns empty dict")
    print("ALL BOT COMMAND TESTS PASSED")
