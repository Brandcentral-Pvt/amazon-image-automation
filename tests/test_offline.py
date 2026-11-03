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
    # hermetic: never attempt NIM calls from the offline suite
    cfg.data["nim"] = {"enabled": False}
    # the retry/resume tests below write fake PNG bytes - the image gate is tested
    # separately with real images, so keep it off for the shared fixtures
    cfg.data["gemini"]["image_check"] = {"enabled": False}

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

        def begin_batch(self, master: str = "", reference_images: list = None) -> None:
            pass

        def restart_batch(self, reference_images: list = None) -> None:
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

    # --- Gemini model-picker: label fallback + configured XPath (fake page, no browser)
    from src.gemini_web import GeminiWeb                     # noqa: E402

    class _FakeLoc:
        def __init__(self, count=1, visible=True, text="", log=None):
            self._count, self._visible, self._text = count, visible, text
            self.log = log if log is not None else []
        def count(self): return self._count
        def is_visible(self, timeout=0): return self._visible
        @property
        def first(self): return self
        @property
        def last(self): return self
        def nth(self, i): return _FakeLoc(self._count, self._visible, self._text, self.log)
        def click(self, timeout=0, **kw): self.log.append("click"); return None
        def inner_text(self, timeout=0): return self._text
        def hover(self, timeout=0): return None

    class _FakePage:
        def __init__(self, label_text="Create image"):
            self.label_text = label_text
            self.clicks: list[str] = []
        def locator(self, sel):
            if "gem-menu-item-label" in sel:
                return _FakeLoc(count=3, visible=True, text=self.label_text, log=self.clicks)
            return _FakeLoc(count=1, visible=True, log=self.clicks)
        def wait_for_timeout(self, ms): pass
        @property
        def keyboard(self):
            class _K:
                def press(self, key): pass
            return _K()

    # (a) create_image_option NOT configured -> automatic label fallback must engage
    cfg.data["gemini"]["selectors"].pop("create_image_option", None)
    gem = GeminiWeb(cfg)
    gem.page = _FakePage(label_text="Create image")
    assert gem._pick_image_model() is True, "label fallback must select Create image"
    assert gem.page.clicks, "fallback must have clicked something"
    print("[ok] model picker: missing create_image_option -> div.gem-menu-item-label fallback works")

    # (b) configured XPath present -> used directly (label text matches nothing, so
    #     a fallback would fail -> proves the XPath path was taken)
    cfg.data["gemini"]["selectors"]["create_image_option"] = \
        "//*[@id='cdk-overlay-0']/mat-card/mat-action-list/div[2]/toolbox-drawer/div/div/toolbox-drawer-item[1]/button/span/span"
    gem2 = GeminiWeb(cfg)
    gem2.page = _FakePage(label_text="Something else entirely")
    assert gem2._pick_image_model() is True, "configured XPath must be used"
    print("[ok] model picker: configured create_image_option XPath is used when present")

    # (c) neither configured nor any label match -> honest False (caller retries/warns)
    cfg.data["gemini"]["selectors"].pop("create_image_option", None)
    gem3 = GeminiWeb(cfg)
    gem3.page = _FakePage(label_text="Chat")
    assert gem3._pick_image_model() is False
    print("[ok] model picker: no selector + no matching label -> returns False (no silent success)")
    cfg.data["gemini"]["selectors"]["create_image_option"] = \
        "//*[@id='cdk-overlay-0']/mat-card/mat-action-list/div[2]/toolbox-drawer/div/div/toolbox-drawer-item[1]/button/span/span"

    # --- resume: an ok-slot saved as .jpg (browser download) must NOT regenerate
    res_dir = demo_root / "B0RESUME01"
    (res_dir / "generated").mkdir(parents=True, exist_ok=True)
    bundle4, _ = build_bundle(product, res_dir, cfg)
    manifest4 = pipe.load_manifest("B0RESUME01")
    for item in bundle4:
        jpg = res_dir / "generated" / (Path(item["target_file"]).stem + ".jpg")
        jpg.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        manifest4["slots"][item["slot_id"]] = {"status": "ok", "file": f"generated/{jpg.name}"}
    pipe.save_manifest("B0RESUME01", manifest4)
    flaky2 = FlakyGem()
    stats4 = pipe._generate_one(flaky2, "B0RESUME01", product, bundle4, [], "M")
    assert flaky2.calls == 0 and flaky2.restarts == 0, (flaky2.calls, flaky2.restarts)
    assert stats4["slots_ok"] == 8 and stats4["slots_failed"] == 0, stats4
    print("[ok] resume: ok-slots recorded with a .jpg file are skipped (no regeneration)")

    # --- bugfix regression: downloader rejects undecodable / too-small images ---
    from src.downloader import _check_image               # noqa: E402
    from PIL import Image                                # noqa: E402

    junk = demo_root / "junk.bin"
    junk.write_bytes(b"not an image at all" * 100)
    ok, w, h = _check_image(junk, 500)
    assert not ok and (w, h) == (0, 0), (ok, w, h)       # w==0 used to slip through
    small = demo_root / "small.png"
    Image.new("RGB", (100, 100), "white").save(small)
    ok, w, h = _check_image(small, 500)
    assert not ok and (w, h) == (100, 100), (ok, w, h)
    big = demo_root / "big.png"
    Image.new("RGB", (1600, 1920), "white").save(big)
    ok, w, h = _check_image(big, 500)
    assert ok and (w, h) == (1600, 1920), (ok, w, h)
    print("[ok] downloader: corrupt (0x0) and too-small images are rejected, valid accepted")

    # --- bugfix regression: dotfile .tmp_* leftovers are never real images ---
    from src.utils import iter_real_files                 # noqa: E402

    bdir = demo_root / "B0DOTS01" / "base_images"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "01.jpg").write_bytes(b"x")
    (bdir / ".tmp_01.jpg").write_bytes(b"x")
    names = [p.name for p in iter_real_files(bdir)]
    assert names == ["01.jpg"], names
    assert iter_real_files(demo_root / "does-not-exist") == []
    print("[ok] iter_real_files: .tmp_* crash leftovers excluded, missing dir -> []")

    # --- bugfix regression: CsvTracker locates the asin column from the header ---
    import csv as _csv                                   # noqa: E402
    from src.tracker import CsvTracker, _col_letter      # noqa: E402

    cols = ["status", "asin", "error"]                   # asin NOT first
    csvt = CsvTracker(demo_root / "tracking_custom.csv", columns=cols)
    csvt.upsert({"asin": "B0AAA11111", "status": "scraped", "error": ""})
    csvt.upsert({"asin": "B0BBB22222", "status": "scraped", "error": ""})
    csvt.upsert({"asin": "B0AAA11111", "status": "generated", "error": ""})
    with open(demo_root / "tracking_custom.csv", newline="", encoding="utf-8") as fh:
        rows = list(_csv.reader(fh))
    assert rows[0] == cols and len(rows) == 3, rows
    by_asin = {r[1]: r for r in rows[1:]}
    assert by_asin["B0AAA11111"][0] == "generated", rows   # updated, not duplicated
    assert by_asin["B0BBB22222"][0] == "scraped", rows
    assert _col_letter(1) == "A" and _col_letter(26) == "Z" and _col_letter(27) == "AA"
    print("[ok] CsvTracker: upsert keyed by header's asin column (custom order), no dupes")

    # --- bugfix regression: gallery exclusions always keep SYSTEM TASK CODE ---
    cfg.data["gallery"]["exclude_categories"] = ["WOMEN"]
    exc = pg._excluded_categories(cfg)
    assert exc == {"SYSTEM TASK CODE", "WOMEN"}, exc
    cfg.data["gallery"]["exclude_categories"] = ["SYSTEM TASK CODE"]
    print("[ok] gallery: DEFAULT_EXCLUDED always unioned with user exclude_categories")

    # --- bugfix regression: casting bridge honours nim.enabled and never blocks ---
    from src.prompts import resolve_casting              # noqa: E402

    nim_dir = ROOT / "data" / "nim"
    before = set(p.name for p in nim_dir.glob("*.json"))
    c1 = resolve_casting(product, cfg, "")              # nim.enabled=False in tests
    assert c1["source"] == "local-fallback" and c1["model_required"] is False
    after = set(p.name for p in nim_dir.glob("*.json"))
    assert before == after, "local casting must not write a NIM cache file"
    cfg.data["nim"] = {"enabled": True}                  # no API key -> offline fallback
    p2 = ProductData(asin="B0NIMTEST01", title="Women Cotton Kurti")
    c2 = resolve_casting(p2, cfg, "")
    assert c2["source"] == "local-fallback" and c2["model_required"] is True, c2.get("source")
    cache2 = nim_dir / "B0NIMTEST01.json"
    assert cache2.exists(), "fallback casting should be cached"
    cache2.unlink()
    cfg.data["nim"] = {"enabled": False}
    print("[ok] casting: nim off -> local (no cache); nim on without key -> local fallback, cached")

    # --- bugfix regression: upload consumes _pending_files; stray chooser ignored ---
    class _FakePage2:
        """Minimal page for upload_images: direct file input + preview counter."""
        def __init__(self):
            self.previews = 0
        def locator(self, sel):
            page = self
            class _L:
                def count(self): return 1
                def is_visible(self, timeout=0): return True
                @property
                def first(self): return self
                def set_input_files(self, files): page.previews += len(files)
                def click(self, timeout=0, **kw): return None
            return _L()
        def evaluate(self, js):
            if "blob:" in js or "attachment" in js:
                return self.previews
            return 0
        def wait_for_timeout(self, ms): pass
        @property
        def frames(self): return [self]
        @property
        def main_frame(self): return self

    gem4 = GeminiWeb(cfg)
    gem4.page = _FakePage2()
    cfg.data["gemini"]["upload_wait_sec"] = 0
    cfg.data["gemini"]["upload_timeout_sec"] = 1
    src_img = retry_dir / "generated" / "01_hero_white.png"
    n = gem4.upload_images([src_img])
    assert n == 1 and gem4._pending_files == [], (n, gem4._pending_files)

    class _Chooser:
        def __init__(self): self.files = None
        def set_files(self, files): self.files = files

    ch = _Chooser()
    gem4._on_filechooser(ch)                 # pending empty -> must NOT feed files
    assert ch.files is None, ch.files
    gem4._pending_files = [src_img]
    gem4._on_filechooser(ch)                 # pending set -> chooser gets the files
    assert ch.files == [str(src_img)], ch.files
    print("[ok] upload: _pending_files cleared after attach; empty pending never feeds a chooser")

    # --- upload failure: zero verified previews must raise, never send text-only ---
    from src.gemini_web import GeminiError               # noqa: E402

    class _FakePage3:
        """No file input, no previews, chooser never fires -> upload must raise."""
        def __init__(self): self.url = "https://gemini.google.com/app"
        def locator(self, sel):
            class _L:
                def count(self): return 0
                def is_visible(self, timeout=0): return False
                @property
                def first(self): return self
                def click(self, timeout=0, **kw): return None
            return _L()
        def evaluate(self, js): return 0
        def wait_for_timeout(self, ms): pass
        def title(self): return ""
        def content(self): return ""
        def screenshot(self, path=None, **kw):
            if path:
                Path(path).write_bytes(b"")
        @property
        def frames(self): return [self]
        @property
        def main_frame(self): return self

    gem7 = GeminiWeb(cfg)
    gem7.page = _FakePage3()
    try:
        gem7.upload_images([src_img])
        raise AssertionError("upload with zero previews must raise")
    except GeminiError as exc:
        assert "could not attach" in str(exc), exc
    print("[ok] upload: nothing verifiably attached -> GeminiError (no silent text-only run)")

    # --- send_prompt: composer must actually receive the text before sending ---
    class _FakePage4:
        """Composer simulation: insert_text either lands in the box or not."""
        def __init__(self, lands=True):
            self.lands = lands
            self.typed = ""
        def locator(self, sel):
            page = self
            class _L:
                def __init__(self): self.sel = sel
                def count(self): return 1
                def is_visible(self, timeout=0): return "stop" not in self.sel.lower()
                @property
                def first(self): return self
                def click(self, timeout=0, **kw): return None
                def inner_text(self, timeout=0): return page.typed
            return _L()
        def evaluate(self, js): return 0
        def wait_for_timeout(self, ms): pass
        @property
        def keyboard(self):
            page = self
            class _K:
                def insert_text(self, t):
                    if page.lands:
                        page.typed = t
                def press(self, k): pass
            return _K()

    gem5 = GeminiWeb(cfg)
    gem5.page = _FakePage4(lands=True)
    gem5.send_prompt("X" * 200)
    assert gem5.page.typed == "X" * 200
    gem6 = GeminiWeb(cfg)
    gem6.page = _FakePage4(lands=False)
    try:
        gem6.send_prompt("Y" * 200)
        raise AssertionError("empty composer must raise")
    except GeminiError as exc:
        assert "composer did not accept" in str(exc), exc
    print("[ok] send_prompt: verifies the composer received the text; refuses to send empty")

    # --- image accuracy gate (pure helpers) ---
    from src.utils import (aspect_targets, normalize_image_ext, parse_aspect,  # noqa: E402
                           sha256_file, verify_generated_image)
    from PIL import Image as _Image                            # noqa: E402

    assert parse_aspect("3:4") == 0.75 and parse_aspect("1:1") == 1.0
    assert parse_aspect("junk") is None
    tg = aspect_targets(cfg)
    assert any(abs(t - 0.75) < 1e-9 for t in tg), tg            # UI ratio 3:4
    assert any(abs(t - 1600 / 1920) < 1e-9 for t in tg), tg     # panel spec 1600x1920

    vdir = demo_root / "B0IMGCHK01"
    vdir.mkdir(parents=True, exist_ok=True)
    good = vdir / "good.png"
    _Image.new("RGB", (1600, 1920), "white").save(good)
    r = verify_generated_image(good, targets=tg)
    assert r["ok"] and (r["w"], r["h"]) == (1600, 1920), r
    r34 = vdir / "r34.png"
    _Image.new("RGB", (1200, 1600), "white").save(r34)         # exact 3:4 also accepted
    assert verify_generated_image(r34, targets=tg)["ok"]
    square = vdir / "sq.png"
    _Image.new("RGB", (1200, 1200), "white").save(square)
    assert not verify_generated_image(square, targets=tg)["ok"]        # not portrait
    tiny = vdir / "tiny.png"
    _Image.new("RGB", (800, 600), "white").save(tiny)
    assert not verify_generated_image(tiny, targets=tg)["ok"]          # < 1000px long side
    junk2 = vdir / "junk.png"
    junk2.write_bytes(b"nope" * 100)
    assert not verify_generated_image(junk2, targets=tg)["ok"]         # undecodable
    h = sha256_file(good)
    assert not verify_generated_image(good, targets=tg, ref_hashes={h})["ok"]   # echoed upload
    assert not verify_generated_image(good, targets=tg, seen_hashes={h})["ok"]  # duplicate panel

    jpgf = vdir / "slot.jpg"
    _Image.new("RGB", (1600, 1920), "red").save(jpgf, "JPEG")
    dest_png = vdir / "slot.png"
    out = normalize_image_ext(jpgf, dest_png)
    assert out == dest_png and dest_png.exists() and not jpgf.exists()
    with _Image.open(dest_png) as im:
        assert im.size == (1600, 1920)
    print("[ok] image gate: portrait/aspect/min-px enforced; ref-echo + duplicate rejected; ext normalized")

    # --- pipeline image gate end-to-end through the slot retry loop ---
    cfg.data["gemini"]["image_check"] = {"enabled": True, "min_long_side_px": 1000,
                                         "aspect_tolerance": 0.06}
    cfg.data["gemini"]["slot_retries"] = 1
    cfg.data["gemini"]["slot_retry_delay_sec"] = [0, 0]

    class GoodGem:
        def __init__(self): self.calls = 0
        def begin_batch(self, master="", reference_images=None): pass
        def restart_batch(self, reference_images=None): pass
        def generate_image(self, prompt, reference_images, dest, strategy="auto",
                           dry_run=False, prompt_record=None):
            self.calls += 1
            _Image.new("RGB", (1600, 1920), "white").save(dest)
            return {"ok": True, "path": str(dest)}

    gdir = demo_root / "B0IMGOK01"
    gdir.mkdir(parents=True, exist_ok=True)
    bundle5, _ = build_bundle(product, gdir, cfg)
    gg = GoodGem()
    stats5 = pipe._generate_one(gg, "B0IMGOK01", product, bundle5, [], "M")
    assert stats5["slots_ok"] == 8 and gg.calls == 8, (stats5, gg.calls)

    class BadGem:
        def __init__(self): self.calls = 0
        def begin_batch(self, master="", reference_images=None): pass
        def restart_batch(self, reference_images=None): pass
        def generate_image(self, prompt, reference_images, dest, strategy="auto",
                           dry_run=False, prompt_record=None):
            self.calls += 1
            dest.write_bytes(b"\x89PNG\r\n\x1a\nnot-really")   # undecodable
            return {"ok": True, "path": str(dest)}

    bdir = demo_root / "B0IMGBAD1"
    bdir.mkdir(parents=True, exist_ok=True)
    bundle6, _ = build_bundle(product, bdir, cfg)
    bg = BadGem()
    stats6 = pipe._generate_one(bg, "B0IMGBAD1", product, bundle6, [], "M")
    assert stats6["slots_failed"] == 8 and bg.calls == 16, (stats6, bg.calls)  # 2 attempts each
    m6 = pipe.load_manifest("B0IMGBAD1")
    assert all(v["status"] == "failed" for v in m6["slots"].values())
    assert "final image check failed" in m6["slots"]["01_hero_white"]["error"]
    cfg.data["gemini"]["image_check"] = {"enabled": False}
    cfg.data["gemini"]["slot_retries"] = 2
    print("[ok] pipeline image gate: valid panels accepted; undecodable rejected, retried, marked failed")

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
