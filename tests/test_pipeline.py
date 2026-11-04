"""Pipeline resumability tests. Run: python tests/test_pipeline.py
No network, no Playwright needed - uses a mock Gemini driver.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import Config  # noqa: E402
from src.models import ProductData  # noqa: E402
from src.pipeline import Pipeline  # noqa: E402
from src.prompts import build_bundle  # noqa: E402


class SilentGem:
    """Mock Gemini driver that writes a fake PNG and records calls."""

    def __init__(self):
        self.calls = 0
        self.restarts = 0

    def begin_batch(self, master: str = "", reference_images: list = None) -> None:
        pass

    def restart_batch(self, reference_images: list = None) -> None:
        self.restarts += 1

    def generate_image(self, prompt, reference_images, dest, dry_run=False):
        self.calls += 1
        Path(dest).write_bytes(b"\x89PNG\r\n\x1a\nfake")
        return {"ok": True, "path": str(dest)}


def make_cfg():
    cfg = Config({
        "amazon": {"domain": "amazon.in"},
        "output": {"root": str(ROOT / "output" / "_pipeline_test")},
        "gemini": {
            "enabled": True,
            "url": "https://gemini.google.com/app",
            "slot_retries": 0,
            "slot_retry_delay_sec": [0, 0],
            "watermark": {"enabled": False},
        },
        "watermark": {"enabled": False},
    })
    return cfg


def make_product(asin="B0TEST01"):
    return ProductData(
        asin=asin,
        domain="amazon.in",
        url=f"https://www.amazon.in/dp/{asin}",
        title="Test Product",
        brand="Test Brand",
        category="Home > Kitchen",
        price="$19.99",
        rating="4.5",
        reviews="100",
        availability="In stock",
        bullets=["bullet one", "bullet two"],
        attributes={"Capacity": "1 L"},
        variants=["Red", "Blue"],
        aplus_text="",
        image_urls=[],
        scraped_at="2026-01-01T00:00:00",
        scrape_status="ok",
    )


def test_rerun_skips_completed_slots():
    """Second generate() with force=False skips slots already marked ok."""
    cfg = make_cfg()
    pipe = Pipeline(cfg, dry_run=False, force=False)
    adir = Path(cfg.asin_dir("B0TEST01"))
    adir.mkdir(parents=True, exist_ok=True)
    (adir / "base_images").mkdir(parents=True, exist_ok=True)

    product = make_product()
    bundle, master = build_bundle(product, adir, cfg)

    # First run: generate all 8 slots
    gem = SilentGem()
    stats1 = pipe._generate_one(gem, "B0TEST01", product, bundle, [], "notes")
    assert stats1["slots_ok"] == 8, stats1
    assert gem.calls == 8, f"expected 8 calls on first run, got {gem.calls}"

    # Manifest should mark all 8 as ok
    manifest = pipe.load_manifest("B0TEST01")
    assert all(s.get("status") == "ok" for s in manifest["slots"].values())

    # Second run: should skip all 8 (force=False)
    gem2 = SilentGem()
    stats2 = pipe._generate_one(gem2, "B0TEST01", product, bundle, [], "notes")
    assert stats2["slots_ok"] == 8, stats2
    assert gem2.calls == 0, f"expected 0 calls on rerun (all skipped), got {gem2.calls}"

    print("[ok] rerun with force=False skips all completed slots (0 Gemini calls)")


def test_force_rerun_regenerates_slots():
    """force=True regenerates all slots even if already marked ok."""
    cfg = make_cfg()
    pipe = Pipeline(cfg, dry_run=False, force=True)
    adir = Path(cfg.asin_dir("B0FORCE01"))
    adir.mkdir(parents=True, exist_ok=True)
    (adir / "base_images").mkdir(parents=True, exist_ok=True)

    product = make_product(asin="B0FORCE01")
    bundle, master = build_bundle(product, adir, cfg)

    gem = SilentGem()
    stats = pipe._generate_one(gem, "B0FORCE01", product, bundle, [], "notes")
    assert stats["slots_ok"] == 8, stats
    assert gem.calls == 8, f"expected 8 calls with force=True, got {gem.calls}"

    print("[ok] force=True regenerates all 8 slots")


if __name__ == "__main__":
    test_rerun_skips_completed_slots()
    test_force_rerun_regenerates_slots()
    print("ALL PIPELINE TESTS PASSED")
