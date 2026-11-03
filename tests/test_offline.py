"""Offline test: prompt building, folder layout, ASIN parsing.

Run:  python tests/test_offline.py
No network, no Playwright, no Gemini needed.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import load_config          # noqa: E402
from src.models import ProductData          # noqa: E402
from src.pipeline import Pipeline           # noqa: E402
from src.prompts import build_bundle        # noqa: E402
from src.utils import parse_asin_list       # noqa: E402
from src.downloader import clean_filename   # noqa: E402
from src.scraper import product_from_raw, hires_candidates  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "product.json"


def main() -> int:
    cfg = load_config()
    demo_root = ROOT / "output" / "_demo"
    if demo_root.exists():
        shutil.rmtree(demo_root)
    cfg.data["output"]["root"] = str(demo_root)
    # keep these tests hermetic: the wm engine runs from the remover's own venv
    cfg.data["watermark"] = {"enabled": False}

    # --- ASIN parsing
    parsed = parse_asin_list(
        "B0DEMO1234, b0demo5678\nhttps://www.amazon.in/dp/B0DEMO9012?th=1 # comment"
    )
    assert parsed == ["B0DEMO1234", "B0DEMO5678", "B0DEMO9012"], parsed
    print(f"[ok] ASIN parsing -> {parsed}")

    # --- product + prompts (AIIE studio pack, offline casting - no network)
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    product = ProductData.from_dict(raw)
    asin_dir = demo_root / product.asin
    (asin_dir / "base_images").mkdir(parents=True, exist_ok=True)

    bundle, master = build_bundle(product, asin_dir, cfg)
    assert len(bundle) == 8, f"expected 8 slots, got {len(bundle)}"
    assert master.strip(), "AIIE master message must not be empty"
    assert "AUDIENCE LOCK" in master and "MODEL CASTING LOCK" in master
    assert "FRESH CASTING RULE" in master  # never copy humans from the base images
    assert "FRESH CASTING" in bundle[0]["prompt"]
    print(f"[ok] {len(bundle)} prompts + AIIE master message ({len(master)} chars)")

    files = [b["target_file"] for b in bundle]
    assert len(set(files)) == 8 and files[0].startswith("01_") and files[-1].startswith("08_")
    print(f"[ok] slot files -> {files}")

    for item in bundle:
        prompt = item["prompt"]
        assert "{" not in prompt.replace("{}", ""), f"unformatted placeholder in {item['slot_id']}"
        assert "AIIE PANEL" in prompt
        assert "SINGLE SOURCE OF TRUTH" in prompt
        assert "IDENTITY & CONSISTENCY LOCK" in prompt
        assert "3:4" in prompt and "1600x1920" in prompt
        if not item["allowed_text"]:
            assert "NO text" in prompt
    print("[ok] every AIIE panel carries casting, ground truth, consistency, output spec")

    craft = next(b for b in bundle if b["slot_id"] == "04_craft_story")
    assert "NO close-up" in craft["prompt"], "craft story must forbid close-up crops"
    assert "close-up detail crops" not in craft["prompt"]
    print("[ok] craft story slot: ONE wide crafted-work scene, no close-up crops")

    md = (asin_dir / "prompts" / "prompts.md")
    assert md.exists() and md.stat().st_size > 4000
    sj = (asin_dir / "prompts" / "prompts.json")
    assert sj.exists() and json.loads(sj.read_text(encoding="utf-8"))["master"] == master
    print(f"[ok] prompts.md + prompts.json written ({md.stat().st_size // 1024} KB)")

    # --- legacy pack (slots.yaml) fallback still intact
    cfg.data["studio"]["templates"] = "_missing_/studio.yaml"
    legacy_dir = demo_root / "B0LEGACY01"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    bundle2, master2 = build_bundle(product, legacy_dir, cfg)
    cfg.data["studio"]["templates"] = "prompts/aiie_studio.yaml"
    assert len(bundle2) == 8 and master2 == "", "legacy pack must have no master message"
    assert "REFERENCE IMAGES" in bundle2[0]["prompt"]
    assert re.search(r"3000x3000", bundle2[0]["prompt"])
    print("[ok] legacy slots.yaml pack fallback intact")

    # --- prompt gallery: load/exclusion, candidate pool, sanitizer
    import src.prompt_gallery as pg                      # noqa: E402

    gallery_file = ROOT / "DOCUMENTATION" / "all_prompts_compilation.json"
    gp = pg.load(gallery_file)
    raw_total = sum(len(blk["prompts"]) for cat, blk in
                    json.loads(gallery_file.read_text(encoding="utf-8"))["categories"].items()
                    if cat != "SYSTEM TASK CODE")
    assert len(gp) == raw_total and len(gp) >= 200, (len(gp), raw_total)
    assert all(p.category != "SYSTEM TASK CODE" for p in gp)
    pool, keys = pg.candidate_pool(gp, ["WOMEN", "FEMALE MODEL", "GIRL"], 40)
    assert len(pool) == 40 and len(keys) == 40
    assert sum(1 for p in pool if p.category == "WOMEN") == 20
    assert sum(1 for p in pool if p.category == "FEMALE MODEL") == 10
    assert sum(1 for p in pool if p.category == "GIRL") >= 5
    assert sum(1 for p in pool if p.category == "GIRL") + \
        sum(1 for p in pool if p.category == "WOMEN") + \
        sum(1 for p in pool if p.category == "FEMALE MODEL") >= 35

    dirty = ("full-body portrait of the same young man (ensure strict facial "
             "consistency with prior reference), walked into a cafe with a coffee "
             "cup. Background: Identical environment and lighting. Aspect ratio "
             "must be 1600x2100 (portrait orientation).\u200e")
    clean = pg.sanitize(dirty, "Indian woman, 27")
    assert "facial consistency" not in clean.lower()
    assert "same young man" not in clean.lower()
    assert "freshly cast session model" in clean
    assert "identical environment" not in clean.lower()
    assert "1600x1920" in clean and "1600x2100" not in clean
    assert "MODEL DIRECTION" in clean
    assert "cafe with a coffee cup" in clean, "scene text must survive sanitising"
    assert "\u200e" not in clean and "\u200b" not in clean, "invisible marks stripped"
    print(f"[ok] prompt gallery: {len(gp)} usable prompts, pool spread + sanitizer verified")

    # --- manifest / tracking wiring (no browser)
    pipe = Pipeline(cfg, dry_run=True)
    manifest = pipe.load_manifest(product.asin)
    manifest["product"] = product.to_dict()
    for item in bundle:
        manifest["slots"][item["slot_id"]] = {"status": "ok", "file": item["target_file"]}
    pipe.save_manifest(product.asin, manifest)
    pipe._write_index(product.asin, manifest)
    pipe.report(product.asin, product, manifest, "generated")

    assert (asin_dir / "manifest.json").exists()
    assert (asin_dir / "README.md").exists()
    assert (ROOT / "data" / "tracking.csv").exists()
    print("[ok] manifest.json + README.md + tracking row written")

    # --- slot fallback retries: first slot fails twice, succeeds on attempt 3
    class FlakyGem:
        def __init__(self):
            self.calls = 0
            self.restarts = 0

        def begin_batch(self, master: str = "") -> None:
            pass

        def restart_batch(self) -> None:
            self.restarts += 1

        def generate_image(self, prompt, reference_images, dest, strategy="auto",
                           dry_run=False, prompt_record=None):
            self.calls += 1
            if self.calls <= 2:
                raise RuntimeError("simulated gemini failure")
            dest.write_bytes(b"\x89PNG\r\n\x1a\nfake")
            return {"ok": True, "path": str(dest)}

    cfg.data["gemini"]["slot_retries"] = 2
    cfg.data["gemini"]["slot_retry_delay_sec"] = [0, 0]   # keep the test fast
    flaky = FlakyGem()
    retry_dir = demo_root / "B0RETRY01"
    retry_dir.mkdir(parents=True, exist_ok=True)
    bundle3, _ = build_bundle(product, retry_dir, cfg)
    stats = pipe._generate_one(flaky, "B0RETRY01", product, bundle3, [], "M")
    assert flaky.calls == 10 and flaky.restarts == 2, (flaky.calls, flaky.restarts)
    assert stats["slots_ok"] == 8 and stats["slots_failed"] == 0, stats
    retry_manifest = pipe.load_manifest("B0RETRY01")
    assert all(v["status"] == "ok" for v in retry_manifest["slots"].values())
    assert retry_manifest["slots"]["01_hero_white"]["attempts"] == 3, retry_manifest["slots"]["01_hero_white"]
    print("[ok] slot retry loop: 10 attempts, 2 fresh-chat restarts, all 8 slots saved")

    # --- watermark cleanup wiring (offline: disabled -> image untouched)
    from src.wm_clean import clean_generated_image        # noqa: E402

    fake_png = retry_dir / "generated" / "01_hero_white.png"
    assert clean_generated_image(fake_png, cfg) == {"status": "disabled"}
    print("[ok] watermark cleanup stage wired (disabled mode leaves files untouched)")

    # --- sweep_generated: the batch-end second verification pass (wm disabled)
    from src.wm_clean import sweep_generated                 # noqa: E402

    sweep = sweep_generated(retry_dir, cfg, {"slots": {}})
    assert sum(sweep.values()) == 0, f"disabled sweep must be a no-op, got {sweep}"
    print("[ok] batch-end watermark sweep wired (per ASIN, every image re-checked)")
    print("[ok] filename sanitising:", clean_filename("Hello / World: #1 (2026).jpg"))

    # --- REGRESSION: the scraper's raw -> ProductData mapping (aplus bug, 2026-10-30)
    raw_js = {
        "title": "  Test   Product  ",
        "brand": "Test Brand",
        "canonical": "https://www.amazon.in/dp/B0TESTASIN",
        "price": "\u20b9999",
        "rating": "4.3 out of 5 stars",
        "reviews": "1,024 ratings",
        "availability": "In stock",
        "category": "A > B > C",
        "bullets": ["bullet one", "", "bullet two"],
        "attributes": {"Capacity": "1 L", "Empty": ""},
        "variants": ["Red", "Blue"],
        "aplus": "x" * 9000,
        "images": [
            "https://m.media-amazon.com/images/I/71aaa._AC_UL320_.jpg",
            "https://m.media-amazon.com/images/I/71aaa._AC_UL640_.jpg",   # same image id -> dedupe
            "https://m.media-amazon.com/images/I/72bbb._AC_SL1500_.jpg",
        ],
    }
    prod = product_from_raw(raw_js, "B0TESTASIN", cfg)
    assert prod.aplus_text and len(prod.aplus_text) == 4000, "aplus_text must be populated"
    assert prod.scrape_status == "ok"
    assert prod.title == "Test Product", prod.title
    assert len(prod.image_urls) == 2, prod.image_urls          # deduped by image id
    assert prod.attributes == {"Capacity": "1 L"}
    assert prod.bullets == ["bullet one", "bullet two"]
    assert ProductData.from_dict(prod.to_dict()).aplus_text == prod.aplus_text
    print(f"[ok] raw->ProductData mapping ({len(prod.image_urls)} unique images, aplus mirrored)")

    hc = hires_candidates("https://m.media-amazon.com/images/I/71abc._AC_UL320_.jpg")
    assert hc[0].endswith("_AC_SL2000_.jpg") and hc[1].endswith("_AC_SL1500_.jpg"), hc
    print("[ok] hi-res URL ladder ->", hc[0].rsplit("/", 1)[-1], "->", hc[1].rsplit("/", 1)[-1])

    # --- ASIN file handling errors are explicit, not silent
    from src.utils import read_asins
    try:
        read_asins("data/does_not_exist.txt")
        raise AssertionError("should have raised FileNotFoundError")
    except FileNotFoundError as exc:
        assert "not found" in str(exc)
    print("[ok] missing ASIN file raises a clear error")

    print("\n--- sample prompt (slot 01) ---\n")
    print(bundle[0]["prompt"][:900] + " ...\n")
    print("ALL OFFLINE TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
