"""Drive Arena.ai's Image Arena (https://arena.ai/image) with Playwright.

Same driver interface as src/gemini_web.GeminiWeb, so the pipeline can swap
backends via `image.backend: arena_web` in config.yaml:

    with ArenaWeb(cfg, headless=...) as drv:
        drv.begin_batch(master, reference_images=refs)
        drv.generate_image(prompt=..., reference_images=refs, dest=...) -> {"ok", "path"}

Arena specifics handled here:
  * BATTLE MODE: every prompt returns TWO anonymous model outputs - `arena.pick`
    decides which one we keep ("largest" bytes / "left" / "right").
  * Arbitrary output aspect: `arena.fit_panel: true` (default) center-crops and
    resizes the chosen image to the studio panel (1600x1920) so the pipeline's
    image accuracy gate passes and Amazon gets consistent 3:4-ish panels.
  * Reference uploads work like Gemini's (filechooser interception) but are
    optional - Arena image mode is prompt-first.
  * The AIIE master message is NOT sent: Arena treats every prompt as an image
    generation, so the self-contained slot prompts are used directly.
  * All selectors live in config `arena.selectors.*` - capture them from the live
    page with:  python run.py probe --backend arena --url https://arena.ai/image --steps

Cloudflare may challenge the datacenter IP: arena.block_markers detects the
interstitial and waits out arena.block_wait_sec.
"""
from __future__ import annotations

import base64
import datetime as dt
import time
from pathlib import Path
from typing import Any

from .backends import image_check_cfg
from .config import Config
from .gemini_web import dump_page_diagnostics
from .utils import (PROJECT_ROOT, aspect_targets, ensure_dir, human_delay, log,
                    normalize_image_ext, sha256_file, verify_generated_image)

DEFAULT_ARENA_URL = "https://arena.ai/image"

# images currently on the page (battle mode shows two per generation)
JS_ARENA_COUNT_IMAGES = """
() => {
  const imgs = Array.from(document.querySelectorAll('img'));
  return imgs.filter(i => {
    const s = i.currentSrc || i.src || '';
    return !s.startsWith('data:image/svg') && (i.naturalWidth || 0) >= 300 && (i.naturalHeight || 0) >= 300;
  }).length;
}
"""

# every candidate generated image with its bytes (b64 via fetch, CORS-safe fallback
# in collect_images via page.request)
JS_ARENA_COLLECT = """
async () => {
  const imgs = Array.from(document.querySelectorAll('img')).filter(i => {
    const s = i.currentSrc || i.src || '';
    return !s.startsWith('data:image/svg') && (i.naturalWidth || 0) >= 300 && (i.naturalHeight || 0) >= 300;
  });
  const out = [];
  for (const img of imgs) {
    const src = img.currentSrc || img.src || '';
    const w = img.naturalWidth || 0, h = img.naturalHeight || 0;
    let b64 = '';
    try {
      const resp = await fetch(src, {credentials: 'include'});
      const blob = await resp.blob();
      const bytes = new Uint8Array(await blob.arrayBuffer());
      let bin = '';
      const CH = 0x8000;
      for (let i = 0; i < bytes.length; i += CH) {
        bin += String.fromCharCode.apply(null, bytes.subarray(i, i + CH));
      }
      b64 = btoa(bin);
    } catch (e) { b64 = ''; }
    out.push({src: src, w: w, h: h, b64: b64});
  }
  return out;
}
"""

JS_ARENA_LAST_TEXT = """
() => (document.body.innerText || '').slice(-800)
"""


class ArenaError(RuntimeError):
    pass


# --------------------------------------------------------------------- helpers
def fit_panel_image(src: Path | str, dest: Path | str, width: int, height: int) -> Path:
    """Center-crop to the panel aspect and resize to width x height (LANCZOS).

    Arena models output arbitrary aspect ratios; this makes every slot a
    consistent studio panel (default 1600x1920) so the accuracy gate and the
    Amazon layout stay uniform. Returns dest.
    """
    from PIL import Image

    src, dest = Path(src), Path(dest)
    with Image.open(src) as im:
        im = im.convert("RGB")
        w, h = im.size
        target = width / height
        cur = w / h
        if cur > target:      # too wide -> crop sides
            new_w = int(h * target)
            x0 = (w - new_w) // 2
            im = im.crop((x0, 0, x0 + new_w, h))
        elif cur < target:    # too tall -> crop top/bottom
            new_h = int(w / target)
            y0 = (h - new_h) // 2
            im = im.crop((0, y0, w, y0 + new_h))
        im = im.resize((width, height), Image.LANCZOS)
        fmt = "PNG" if dest.suffix.lower() == ".png" else "JPEG"
        params = {"quality": 95} if fmt == "JPEG" else {}
        im.save(dest, fmt, **params)
    if src.resolve() != dest.resolve():
        src.unlink(missing_ok=True)
    return dest


def pick_image(items: list[dict[str, Any]], how: str = "largest") -> dict[str, Any] | None:
    """Battle mode returns two outputs - pick one: largest | left | right."""
    if not items:
        return None
    how = (how or "largest").lower()
    if how == "left":
        return items[0]
    if how == "right":
        return items[-1]
    return max(items, key=lambda i: len(i.get("bytes") or b""))


class ArenaWeb:
    """Playwright driver for Arena.ai Image Arena - same interface as GeminiWeb."""

    def __init__(self, cfg: Config, headless: bool = False):
        self.cfg = cfg
        self.headless = headless
        self.page = None
        self._ctx = None
        self._pw = None
        self._pending_files: list[Path] = []
        self._chooser_fired = False
        self._files_set = False
        self._baseline_images = 0
        self._refs_attached = False
        self._ref_hashes: set[str] = set()
        self._seen_hashes: set[str] = set()
        self._pending_dest: Path | None = None
        self._handled_download: Path | None = None

    # ------------------------------------------------------------- lifecycle
    def __enter__(self) -> "ArenaWeb":
        self.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def _arena_url(self) -> str:
        return str(self.cfg.get("arena.url", DEFAULT_ARENA_URL) or DEFAULT_ARENA_URL)

    def _sel(self, key: str, default: str = "") -> str:
        return self.cfg.get(f"arena.selectors.{key}", default) or default

    def start(self) -> None:
        from playwright.sync_api import sync_playwright
        from .scraper import launch_context  # shared persistent profile (login reuse)

        self._pw = sync_playwright().start()
        self._ctx, _ = launch_context(self._pw, self.cfg, headless=self.headless)
        self.page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        self.page.on("filechooser", self._on_filechooser)
        self.page.on("download", self._on_download)
        self.page.goto(self._arena_url(), wait_until="domcontentloaded")
        self.page.wait_for_timeout(2500)
        self._cool_down_on_block()
        self._dismiss_overlays()
        self._assert_ready()

    def close(self) -> None:
        try:
            if self._ctx:
                self._ctx.close()
        finally:
            if self._pw:
                self._pw.stop()

    # ------------------------------------------------------------- file chooser / download
    def _on_filechooser(self, chooser) -> None:
        self._chooser_fired = True
        if not self._pending_files:
            return
        try:
            chooser.set_files([str(p) for p in self._pending_files])
            self._files_set = True
            log.info("arena: file chooser fed %d file(s)", len(self._pending_files))
        except Exception as exc:  # noqa: BLE001
            log.warning("arena: could not set files on chooser: %s", exc)

    def _on_download(self, download) -> None:
        try:
            name = download.suggested_filename or f"arena_{dt.datetime.now():%Y%m%d_%H%M%S}.png"
            suffix = Path(name).suffix or ".png"
            if self._pending_dest is not None:
                target = self._pending_dest.with_suffix(suffix)
            else:
                target = ensure_dir(self.cfg.out_root() / "_downloads") / name
            ensure_dir(target.parent)
            download.save_as(str(target))
            self._handled_download = target
            log.info("arena: download captured -> %s", target)
        except Exception as exc:  # noqa: BLE001
            log.debug("arena: download handler issue: %s", exc)

    # ------------------------------------------------------------- block / overlays / login
    def _looks_blocked(self) -> bool:
        try:
            url = self.page.url or ""
            if any(m in url.lower() for m in ("/sorry/", "challenge", "blocked")):
                return True
            markers = self.cfg.get("arena.block_markers") or [
                "verify you are human", "unusual traffic", "rate limit",
                "challenge-platform", "attention required",
            ]
            body = (self.page.content() or "")[:400000].lower()
            return any(str(m).lower() in body for m in markers)
        except Exception:  # noqa: BLE001
            return False

    def _cool_down_on_block(self) -> None:
        if not self._looks_blocked():
            return
        wait = int(self.cfg.get("arena.block_wait_sec", 120))
        log.warning("arena: block/challenge page detected - cooling down %ds", wait)
        try:
            out = ensure_dir(PROJECT_ROOT / "logs" / "arena")
            self.page.screenshot(path=str(out / f"blocked_{dt.datetime.now():%Y%m%d_%H%M%S}.png"))
        except Exception:  # noqa: BLE001
            pass
        self.page.wait_for_timeout(wait * 1000)
        try:
            self.page.goto(self._arena_url(), wait_until="domcontentloaded")
            self.page.wait_for_timeout(2500)
        except Exception:  # noqa: BLE001
            pass
        if self._looks_blocked():
            raise ArenaError(
                "Arena.ai is still showing a challenge/block page. Use a residential proxy "
                "(browser.proxy), log in first via `python run.py login --headed`, or try later.")

    def _dismiss_overlays(self) -> None:
        for sel in self.cfg.get("arena.selectors.consent_buttons", []) or [
                'button:has-text("Accept")', 'button:has-text("Accept all")',
                'button:has-text("Got it")', 'button:has-text("I agree")']:
            try:
                btn = self.page.locator(sel).first
                if btn.is_visible(timeout=1200):
                    btn.click(timeout=2000)
                    self.page.wait_for_timeout(600)
            except Exception:  # noqa: BLE001
                pass

    def _assert_ready(self) -> None:
        box = self._sel("prompt_box", 'textarea, [contenteditable="true"]')
        try:
            if not self.page.locator(box).first.is_visible(timeout=10000):
                raise ArenaError("prompt box not visible")
        except ArenaError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ArenaError(
                "Arena.ai page did not load / not signed in. Run: python run.py login --headed "
                "(opens the arena URL in the shared profile) and sign in, then retry."
            ) from exc

    # ------------------------------------------------------------- small click helpers
    def _click_first(self, selectors: list[str], per_selector_ms: int = 1200) -> str | None:
        for sel in selectors:
            try:
                loc = self.page.locator(sel).first
                if loc.count() == 0:
                    continue
                if not loc.is_visible(timeout=per_selector_ms):
                    continue
                loc.click(timeout=3000)
                log.debug("arena: clicked %s", sel)
                return sel
            except Exception:  # noqa: BLE001
                continue
        return None

    def _frames(self):
        try:
            return self.page.frames or [self.page.main_frame]
        except Exception:  # noqa: BLE001
            return [self.page.main_frame]

    def find_file_input(self):
        for frame in self._frames():
            for sel in (self._sel("file_input", 'input[type="file"]'),
                        'input[type="file"]', 'input[accept*="image"]'):
                try:
                    loc = frame.locator(sel)
                    if loc.count() > 0:
                        return loc.first
                except Exception:  # noqa: BLE001
                    continue
        return None

    def _preview_count(self) -> int:
        try:
            return int(self.page.evaluate(
                "() => Array.from(document.querySelectorAll('img'))"
                ".filter(i => { const s = i.currentSrc || i.src || '';"
                " return s.startsWith('blob:') || (s.startsWith('data:image') && !s.startsWith('data:image/svg')); }).length"))
        except Exception:  # noqa: BLE001
            return -1

    # ------------------------------------------------------------- upload
    def upload_images(self, paths: list[Path]) -> int:
        max_refs = int(self.cfg.get("arena.max_reference_images", 4))
        paths = [Path(p) for p in paths if Path(p).exists()][:max_refs]
        if not paths:
            return 0
        self._pending_files = paths
        self._chooser_fired = False
        self._files_set = False
        upload_wait = int(self.cfg.get("arena.upload_wait_sec", 6))
        baseline = self._preview_count()

        fi = self.find_file_input()
        if fi is not None:
            try:
                fi.set_input_files([str(p) for p in paths])
                self.page.wait_for_timeout(upload_wait * 1000)
                now = self._preview_count()
                if now > baseline:
                    n = max(1, min((now - baseline) if now >= 0 and baseline >= 0 else len(paths), len(paths)))
                    log.info("arena: attached %d image(s) via <input type=file>", n)
                    self._pending_files = []
                    return n
                log.debug("arena: input accepted files but no preview - falling back to chooser")
            except Exception as exc:  # noqa: BLE001
                log.debug("arena: direct input failed (%s) - chooser fallback", exc)

        clicked = self._click_first(self.cfg.get("arena.selectors.attach_buttons") or [
            'button[aria-label*="Add" i]', 'button[aria-label*="Upload" i]',
            'button[aria-label*="Attach" i]', '[data-test-id*="upload" i]',
            '[data-test-id*="attach" i]', 'button:has-text("Upload")',
        ])
        if clicked and not self._chooser_fired:
            self.page.wait_for_timeout(1200)
            if not self._chooser_fired:
                self._click_first(self.cfg.get("arena.selectors.upload_menu_items") or [
                    'text="Upload files"', 'text="Upload image"', '[role="menuitem"]:has-text("Upload")',
                ])

        deadline = time.time() + int(self.cfg.get("arena.upload_timeout_sec", 25))
        attached = False
        while time.time() < deadline:
            if self._files_set or self._preview_count() > baseline:
                attached = True
                break
            self.page.wait_for_timeout(700)

        if attached:
            self.page.wait_for_timeout(upload_wait * 1000)
            now = self._preview_count()
            delta = (now - baseline) if (now >= 0 and baseline >= 0 and now > baseline) else len(paths)
            n = max(1, min(delta, len(paths)))
            log.info("arena: attached %d reference image(s)", n)
            self._pending_files = []
            return n

        self.dump_diagnostics("arena_upload_failed")
        raise ArenaError("arena: could not attach images (no file chooser fired) - "
                         "see logs/arena/ for diagnostics; set arena.selectors.attach_buttons")

    # ------------------------------------------------------------- chat / prompt
    def new_chat(self) -> None:
        try:
            self.page.goto(self._arena_url(), wait_until="domcontentloaded")
            self.page.wait_for_timeout(1500)
            self._cool_down_on_block()
            self._dismiss_overlays()
            btn = self._sel("new_chat_button", "")
            if btn:
                self._click_first([btn], per_selector_ms=800)
                self.page.wait_for_timeout(600)
        except ArenaError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("arena: new_chat navigation issue: %s", exc)
        self._refs_attached = False

    def begin_batch(self, master: str = "", reference_images: list | None = None) -> None:
        """Fresh Arena page + reference upload. The AIIE master is intentionally NOT
        sent: every Arena prompt is an image generation, and slot prompts are
        self-contained."""
        self.new_chat()
        self._pending_dest = None
        self._handled_download = None
        self._seen_hashes = set()
        if reference_images:
            log.info("arena: uploading %d reference image(s)", len(reference_images))
            try:
                self.upload_images(reference_images)
                self._refs_attached = True
                self._ref_hashes = {sha256_file(p) for p in reference_images if Path(p).exists()}
            except ArenaError as exc:
                self._refs_attached = False
                if (self.cfg.get("arena.on_upload_failure", "fail") or "fail").lower() == "continue":
                    log.warning("arena: %s -> continuing without references", exc)
                else:
                    raise
        else:
            log.debug("arena: no reference images for this batch")
        log.info("arena: ready for image generation (url=%s)", self._arena_url())

    def restart_batch(self, reference_images: list | None = None) -> None:
        log.info("arena: restarting (fresh page + re-upload)")
        self.begin_batch(reference_images=reference_images)

    def send_prompt(self, prompt: str) -> None:
        try:
            self._baseline_images = int(self.page.evaluate(JS_ARENA_COUNT_IMAGES))
        except Exception:  # noqa: BLE001
            self._baseline_images = 0

        stop_sel = self._sel("stop_button", "")
        if stop_sel:
            try:
                deadline = time.time() + 30
                while time.time() < deadline:
                    if not self.page.locator(stop_sel).first.is_visible():
                        break
                    self.page.wait_for_timeout(1000)
            except Exception:  # noqa: BLE001
                pass

        box = self.page.locator(self._sel("prompt_box", 'textarea, [contenteditable="true"]')).first
        box.click(timeout=15000)
        self.page.wait_for_timeout(400)
        if "textarea" in (self._sel("prompt_box", "") or ""):
            box.fill(prompt)
        else:
            self.page.keyboard.insert_text(prompt)
        self.page.wait_for_timeout(600)

        # verify the composer actually received the text
        try:
            got = box.inner_text(timeout=3000) or box.input_value(timeout=3000) or ""
        except Exception:  # noqa: BLE001
            try:
                got = box.input_value(timeout=3000) or ""
            except Exception:  # noqa: BLE001
                got = ""
        if len(got) < max(50, len(prompt) // 2):
            log.warning("arena: composer text check failed (%d/%d) - retrying once", len(got), len(prompt))
            box.click(timeout=5000)
            self.page.keyboard.press("Control+a")
            self.page.keyboard.insert_text(prompt)
            self.page.wait_for_timeout(600)
            try:
                got = box.inner_text(timeout=3000) or box.input_value(timeout=3000) or ""
            except Exception:  # noqa: BLE001
                got = ""
            if len(got) < max(50, len(prompt) // 2):
                raise ArenaError(f"arena: composer did not accept the prompt ({len(got)}/{len(prompt)})")

        sent = False
        try:
            btn = self.page.locator(self._sel("send_button",
                                              'button[type="submit"], button:has-text("Generate")')).first
            if btn.is_visible(timeout=1500):
                btn.click(timeout=4000)
                sent = True
        except Exception:  # noqa: BLE001
            pass
        if not sent:
            self.page.keyboard.press("Enter")
        log.debug("arena: prompt sent (%d chars)", len(prompt))

    # ------------------------------------------------------------- wait / collect
    def wait_for_generation(self) -> None:
        timeout = int(self.cfg.get("arena.generation_timeout_sec", 240))
        deadline = time.time() + timeout
        started = time.time()
        self.page.wait_for_timeout(2500)
        last_count = -1
        stable = 0
        while time.time() < deadline:
            try:
                count = int(self.page.evaluate(JS_ARENA_COUNT_IMAGES))
            except Exception:  # noqa: BLE001
                count = last_count
            if count > self._baseline_images:
                if count == last_count:
                    stable += 1
                    if stable >= 2:      # count grew and stayed - generation settled
                        self.page.wait_for_timeout(2000)
                        log.info("arena: %d new image(s) in %.0fs", count - self._baseline_images,
                                 time.time() - started)
                        return
                else:
                    stable = 0
            last_count = count
            self.page.wait_for_timeout(2000)
        excerpt = ""
        try:
            excerpt = (self.page.evaluate(JS_ARENA_LAST_TEXT) or "").strip()[-300:]
        except Exception:  # noqa: BLE001
            pass
        raise ArenaError("arena: no new image within %ds%s" % (timeout, f" | page says: {excerpt!r}" if excerpt else ""))

    def collect_images(self) -> list[dict[str, Any]]:
        items = self.page.evaluate(JS_ARENA_COLLECT) or []
        out: list[dict[str, Any]] = []
        for item in items:
            raw: bytes | None = None
            if item.get("b64"):
                try:
                    raw = base64.b64decode(item["b64"])
                except Exception:  # noqa: BLE001
                    raw = None
            if raw is None and str(item.get("src", "")).startswith("http"):
                try:
                    resp = self.page.request.get(item["src"], timeout=30000)
                    if resp.ok:
                        raw = resp.body()
                except Exception:  # noqa: BLE001
                    raw = None
            if raw and len(raw) > 5000:
                out.append({"bytes": raw, "w": item.get("w"), "h": item.get("h"), "src": item.get("src")})
        return out

    def download_via_button(self, dest: Path) -> Path | None:
        if self._handled_download is not None and self._handled_download.exists():
            return self._handled_download
        try:
            img = self.page.locator(self._sel("generated_image", "img")).last
            img.hover(timeout=5000)
            self.page.wait_for_timeout(700)
            btn = self.page.locator(self._sel(
                "download_button", 'button[aria-label*="Download" i], [data-test-id*="download" i]')).last
            with self.page.expect_download(timeout=25000) as dl_info:
                btn.click(timeout=5000)
            download = dl_info.value
            ensure_dir(dest.parent)
            suffix = Path(download.suggested_filename or "").suffix or ".png"
            target = dest.with_suffix(suffix)
            download.save_as(str(target))
            return target
        except Exception as exc:  # noqa: BLE001
            log.warning("arena: button download failed: %s", exc)
            return None

    # ------------------------------------------------------------- diagnostics / capture
    def dump_diagnostics(self, tag: str = "probe") -> dict[str, Any]:
        return dump_page_diagnostics(self.page, tag, out_dir=PROJECT_ROOT / "logs" / "arena")

    CAPTURE_STEPS = [
        ("step_1_home", "home: prompt box, attach (+), consent banners"),
        ("step_2_attach", "attach menu open: 'Upload' item + file input"),
        ("step_3_generated", "after ONE generation: both battle images + download buttons"),
    ]

    def capture_steps(self, interactive: bool = False) -> list[dict[str, Any]]:
        reports: list[dict[str, Any]] = []

        def _pause(msg: str) -> None:
            if interactive:
                log.info("%s - then press Enter here", msg)
                try:
                    input("  Enter... ")
                except EOFError:
                    pass

        reports.append(self.dump_diagnostics("step_1_home"))
        _pause("STEP 2: click the attach/+ button so its menu is open")
        self._click_first(self.cfg.get("arena.selectors.attach_buttons") or [
            'button[aria-label*="Add" i]', 'button[aria-label*="Upload" i]'])
        self.page.wait_for_timeout(1500)
        reports.append(self.dump_diagnostics("step_2_attach"))
        try:
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(500)
        except Exception:  # noqa: BLE001
            pass
        _pause("STEP 3: type any prompt and generate ONCE, wait for both images, "
               "hover one so its Download button shows")
        reports.append(self.dump_diagnostics("step_3_generated"))
        return reports

    # ------------------------------------------------------------- one slot
    def generate_image(self, prompt: str, reference_images: list[Path], dest: Path,
                       strategy: str = "auto", dry_run: bool = False,
                       prompt_record: str | None = None) -> dict[str, Any]:
        ensure_dir(dest.parent)
        if dry_run:
            p = dest.with_suffix(".txt")
            p.write_text(prompt_record or prompt, encoding="utf-8")
            log.info("[dry-run] prompt saved -> %s", p.name)
            return {"ok": True, "path": str(p), "dry_run": True}

        self._dismiss_overlays()
        self._pending_dest = dest
        self._handled_download = None

        every_slot = bool(self.cfg.get("arena.attach_references_every_slot", True))
        if reference_images and (every_slot or not self._refs_attached):
            try:
                self.upload_images(reference_images)
                self._refs_attached = True
            except ArenaError as exc:
                self._refs_attached = False
                if (self.cfg.get("arena.on_upload_failure", "fail") or "fail").lower() == "continue":
                    log.warning("arena: %s -> continuing without references", exc)
                else:
                    raise

        self.send_prompt(prompt)
        self.wait_for_generation()

        saved: Path | None = None
        if strategy in ("auto", "dom_fetch"):
            items = self.collect_images()
            if items:
                item = pick_image(items, str(self.cfg.get("arena.pick", "largest")))
                if item:
                    raw_tmp = dest.with_name(dest.stem + ".raw" + (Path(str(item.get("src") or "")).suffix or ".png"))
                    raw_tmp.write_bytes(item["bytes"])
                    saved = raw_tmp
                    log.info("arena: captured %s (%dx%d, %.0f KB)",
                             raw_tmp.name, item.get("w"), item.get("h"), len(item["bytes"]) / 1024)
        if saved is None and self._handled_download is not None and self._handled_download.exists():
            saved = self._handled_download
        if saved is None and strategy in ("auto", "button"):
            saved = self.download_via_button(dest)
        if saved is None:
            raise ArenaError(f"arena: no image could be captured for {dest.name}")

        # canonical slot filename, then fit the studio panel (Arena outputs are
        # arbitrary aspect) so the accuracy gate + Amazon layout stay uniform
        saved = normalize_image_ext(saved, dest)
        if bool(self.cfg.get("arena.fit_panel", True)):
            w = int(self.cfg.get("studio.panel_width", 1600))
            h = int(self.cfg.get("studio.panel_height", 1920))
            saved = fit_panel_image(saved, dest, w, h)
            log.info("arena: fitted panel %dx%d -> %s", w, h, saved.name)

        self._pending_dest = None

        # accuracy gate (same rules as the Gemini backend)
        check = image_check_cfg(self.cfg)
        if check.get("enabled", True):
            res = verify_generated_image(
                saved,
                targets=aspect_targets(self.cfg),
                min_long_side=int(check.get("min_long_side_px", 1000)),
                aspect_tol=float(check.get("aspect_tolerance", 0.06)),
                ref_hashes=self._ref_hashes if check.get("reject_reference_echo", True) else None,
                seen_hashes=self._seen_hashes if check.get("reject_duplicate_panel", True) else None,
            )
            if not res["ok"]:
                log.warning("arena: image check REJECTED %s: %s (%dx%d)", saved.name, res["reason"],
                            res["w"], res["h"])
                Path(saved).unlink(missing_ok=True)
                raise ArenaError(f"generated image rejected by checks: {res['reason']} "
                                 f"({res['w']}x{res['h']})")
            self._seen_hashes.add(res["sha256"])
            log.info("arena: image check ok: %s %dx%d", saved.name, res["w"], res["h"])

        human_delay(self.cfg.get("arena.between_slots_sec", [10, 20]), "between slots")
        return {"ok": True, "path": str(saved)}
