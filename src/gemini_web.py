"""Drive the Gemini web app (gemini.google.com) with Playwright.

No API key needed: a persisted Chrome profile keeps the Google session alive.

Uploads are the fragile part: Gemini hides the real <input type=file> behind an
"add files" button that opens a NATIVE file chooser. So instead of hunting for
the input, we install a `filechooser` handler and click the button — whatever
Google does to the DOM, the chooser still fires and we hand it the files.

`python run.py probe` dumps every button + file input on the live page, so UI
changes can be fixed from data instead of guesswork.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import time
from pathlib import Path
from typing import Any

from .config import Config
from .utils import PROJECT_ROOT, ensure_dir, human_delay, log, write_json

JS_COUNT_IMAGES = """
() => {
  const imgs = Array.from(document.querySelectorAll('model-response img, message-content img, .model-response-text img'));
  return imgs.filter(i => (i.naturalWidth || 0) >= 200 && (i.naturalHeight || 0) >= 200).length;
}
"""

JS_COUNT_BLOCKS = """
() => document.querySelectorAll('model-response, message-content').length
"""

# images inside the LAST reply only - in a batch chat older panels must be
# ignored, so slot N always captures slot N's image for its related place
JS_COUNT_LAST = """
() => {
  const blocks = Array.from(document.querySelectorAll('model-response, message-content, .model-response-text'));
  if (!blocks.length) return 0;
  const imgs = Array.from(blocks[blocks.length - 1].querySelectorAll('img'));
  return imgs.filter(i => (i.naturalWidth || 0) >= 200 && (i.naturalHeight || 0) >= 200).length;
}
"""

JS_COLLECT_LAST = """
async () => {
  const blocks = Array.from(document.querySelectorAll('model-response, message-content, .model-response-text'));
  if (!blocks.length) return [];
  const imgs = Array.from(blocks[blocks.length - 1].querySelectorAll('img'));
  const out = [];
  for (const img of imgs) {
    const src = img.currentSrc || img.src || '';
    if (!src || src.startsWith('data:image/svg')) continue;
    const w = img.naturalWidth || 0, h = img.naturalHeight || 0;
    if (w < 200 || h < 200) continue;
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

# every clickable thing on the page, for the probe report
JS_BUTTONS = """
() => {
  const nodes = Array.from(document.querySelectorAll('button, [role="button"], [role="menuitem"], [role="option"], a'));
  return nodes.slice(0, 400).map(n => ({
    tag: n.tagName.toLowerCase(),
    role: n.getAttribute('role') || '',
    aria: n.getAttribute('aria-label') || '',
    title: n.getAttribute('title') || '',
    testid: n.getAttribute('data-test-id') || '',
    text: (n.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 60),
    visible: !!(n.offsetWidth || n.offsetHeight || n.getClientRects().length),
  })).filter(b => b.aria || b.text || b.testid || b.title);
}
"""

JS_FILE_INPUTS = """
() => {
  const out = [];
  document.querySelectorAll('input').forEach(i => {
    out.push({
      type: i.type, accept: i.accept || '', multiple: i.multiple,
      hidden: !(i.offsetWidth || i.offsetHeight || i.getClientRects().length),
      cls: (i.className || '').slice(0, 80),
    });
  });
  return out;
}
"""

JS_UPLOAD_PREVIEWS = """
() => {
  const imgs = Array.from(document.querySelectorAll('img'));
  const previews = imgs.filter(i => {
    const s = i.currentSrc || i.src || '';
    return s.startsWith('blob:') || s.startsWith('data:image');
  }).length;
  const chips = document.querySelectorAll('[data-test-id*="attachment"], [data-test-id*="upload"], .attachment-chip').length;
  return previews + chips;
}
"""

JS_LAST_TEXT = """
() => {
  const nodes = Array.from(document.querySelectorAll('model-response, message-content'));
  if (!nodes.length) return '';
  return (nodes[nodes.length - 1].innerText || '').trim().slice(0, 1200);
}
"""


class GeminiError(RuntimeError):
    pass


class GeminiWeb:
    def __init__(self, cfg: Config, headless: bool = False):
        self.cfg = cfg
        self.headless = headless
        self.page = None
        self._ctx = None
        self._pw = None
        self._pending_files: list[Path] = []
        self._chooser_fired = False
        self._files_set = False
        self._upload_error = ""
        # one-chat-per-batch state
        self._baseline_images = 0     # images present before the last prompt was sent
        self._baseline_blocks = 0     # model replies present before it was sent
        self._refs_attached = False   # reference photos already inside the batch chat
        self._active_master = ""      # AIIE master message (kept for retry restarts)
        # download routing: every image Gemini hands us must land at its related place
        self._pending_dest: Path | None = None      # output/<ASIN>/generated/<slot file>
        self._handled_download: Path | None = None

    # ------------------------------------------------------------- lifecycle
    def __enter__(self) -> "GeminiWeb":
        self.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def start(self) -> None:
        from playwright.sync_api import sync_playwright
        from .browser import launch_gemini_context

        self._pw = sync_playwright().start()
        self._ctx, _ = launch_gemini_context(self._pw, self.cfg, headless=self.headless)
        self.page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()

        # KEY FIX: intercept any native file chooser Gemini opens, from any frame
        self.page.on("filechooser", self._on_filechooser)
        # KEY FIX: route every download straight to its related place
        self.page.on("download", self._on_download)

        self.page.goto(self.cfg.get("gemini.url", "https://gemini.google.com/app"),
                       wait_until="domcontentloaded")
        self.page.wait_for_timeout(2500)
        self._cool_down_on_block()
        self._dismiss_overlays()
        self._assert_logged_in()
        # Do NOT select create image/aspect ratio here - will do in begin_batch after upload

    def close(self) -> None:
        try:
            if self._ctx:
                self._ctx.close()
        finally:
            if self._pw:
                self._pw.stop()

    # ------------------------------------------------------------- file chooser
    def _on_filechooser(self, chooser) -> None:
        """Fires whenever any click opens a native file picker."""
        self._chooser_fired = True
        log.debug("file chooser intercepted")
        if not self._pending_files:
            return
        try:
            chooser.set_files([str(p) for p in self._pending_files])
            self._files_set = True
            log.info("file chooser fed %d file(s)", len(self._pending_files))
        except Exception as exc:  # noqa: BLE001
            self._upload_error = str(exc)
            log.warning("could not set files on chooser: %s", exc)

    def _sel(self, key: str, default: str = "") -> str:
        return self.cfg.get(f"gemini.selectors.{key}", default) or default

    def _frames(self):
        try:
            return self.page.frames or [self.page.main_frame]
        except Exception:  # noqa: BLE001
            return [self.page.main_frame]

    def find_file_input(self):
        """Return a locator for a real <input type=file>, across all frames."""
        for frame in self._frames():
            for sel in (self._sel("file_input", 'input[type="file"]'), 'input[type="file"]',
                        'input[accept*="image"]'):
                try:
                    loc = frame.locator(sel)
                    if loc.count() > 0:
                        return loc.first
                except Exception:  # noqa: BLE001
                    continue
        return None

    # ------------------------------------------------------------- downloads -> related place
    def _on_download(self, download) -> None:
        """Route EVERY download Gemini triggers to its related place, immediately.

        While a slot is in flight the related place is  output/<ASIN>/generated/<slot
        file>; stray downloads (operator/manual clicks between slots) are parked in
        output/_downloads/ so nothing is ever lost.
        """
        try:
            name = download.suggested_filename or (
                f"gemini_{dt.datetime.now():%Y%m%d_%H%M%S}.png")
            suffix = Path(name).suffix or ".png"
            if self._pending_dest is not None:
                target = self._pending_dest.with_suffix(suffix)
            else:
                target = ensure_dir(self.cfg.out_root() / "_downloads") / name
            ensure_dir(target.parent)
            download.save_as(str(target))
            self._handled_download = target
            log.info("download captured -> related place: %s", target)
        except Exception as exc:  # noqa: BLE001
            log.debug("download handler issue: %s", exc)

    # ------------------------------------------------------------- traffic blocks
    def _looks_blocked(self) -> bool:
        """True when Google served its /sorry/ traffic-check page instead of Gemini."""
        try:
            return "/sorry/" in (self.page.url or "")
        except Exception:  # noqa: BLE001
            return False

    def _cool_down_on_block(self) -> None:
        """Wait out the /sorry/ block once and retry; give up with a clear error."""
        if not self._looks_blocked():
            return
        wait = int(self.cfg.get("gemini.block_wait_sec", 120))
        log.warning("Google traffic block (/sorry) - cooling down for %ds", wait)
        try:
            out = ensure_dir(PROJECT_ROOT / "logs" / "gemini")
            stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.page.screenshot(path=str(out / f"blocked_{stamp}.png"))
        except Exception:  # noqa: BLE001
            pass
        self.page.wait_for_timeout(wait * 1000)
        try:
            self.page.goto(self.cfg.get("gemini.url", "https://gemini.google.com/app"),
                           wait_until="domcontentloaded")
            self.page.wait_for_timeout(2500)
        except Exception:  # noqa: BLE001
            pass
        if self._looks_blocked():
            raise GeminiError(
                "Google is still blocking automated traffic (/sorry page). "
                "Slow down pacing (gemini.between_slots_sec / between_asins) or try later."
            )

    # ------------------------------------------------------------- overlays/login
    def _dismiss_overlays(self) -> None:
        for sel in self.cfg.get("gemini.selectors.consent_buttons", []) or []:
            try:
                btn = self.page.locator(sel).first
                if btn.is_visible(timeout=1200):
                    btn.click(timeout=2000)
                    self.page.wait_for_timeout(600)
            except Exception:  # noqa: BLE001
                pass

    def _assert_logged_in(self) -> None:
        box = self._sel("prompt_box")
        try:
            if not self.page.locator(box).first.is_visible(timeout=10000):
                raise GeminiError("prompt box not visible")
        except GeminiError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise GeminiError(
                "Gemini is not logged in / page did not load. Run: python run.py login --headed"
            ) from exc

    # ------------------------------------------------------------- health check
    def health_check(self) -> dict[str, object]:
        """Probe the live Gemini page for critical UI selectors.

        Returns {"healthy": bool, "missing": [keys], "checked": [keys]}.
        Call before begin_batch to fail fast on UI drift instead of mid-batch.
        file_input only needs to exist in the DOM (it may be hidden).
        """
        checks = [
            ("prompt_box", True),      # (key, must_be_visible)
            ("send_button", True),
            ("file_input", False),     # hidden inputs OK - just needs to exist
        ]
        missing: list[str] = []
        checked: list[str] = []
        for key, must_be_visible in checks:
            sel = self._sel(key)
            checked.append(key)
            if not sel:
                missing.append(key)
                continue
            try:
                loc = self.page.locator(sel).first
                if loc.count() == 0:
                    missing.append(key)
                    continue
                if must_be_visible and not loc.is_visible(timeout=3000):
                    missing.append(key)
            except Exception:  # noqa: BLE001
                missing.append(key)
        return {"healthy": len(missing) == 0, "missing": missing, "checked": checked}

    # ------------------------------------------------------------- attach buttons
    def _attach_candidates(self) -> list[str]:
        """CSS selectors tried, in order, to open the file picker."""
        configured = self.cfg.get("gemini.selectors.attach_buttons") or []
        defaults = [
            'button[aria-label*="Add files" i]',
            'button[aria-label*="Upload" i]',
            'button[aria-label*="Attach" i]',
            'button[aria-label*="Add" i]',
            'button[aria-label*="Insert" i]',
            '[data-test-id="hidden-file-input"]',
            '[data-test-id*="upload" i]',
            '[data-test-id*="attach" i]',
            'toolbox-drawer button',
            'button.upload-card-button',
            'button[mattooltip*="upload" i]',
            'mat-icon:text-is("add")',
            'button:has(mat-icon:text-is("add"))',
            'button:has(svg) >> nth=0',
        ]
        return [s for s in [*configured, *defaults] if s]

    def _menu_item_candidates(self) -> list[str]:
        """After clicking +, Google often shows a menu: Upload files / Drive / Photos."""
        configured = self.cfg.get("gemini.selectors.upload_menu_items") or []
        defaults = [
            'text="Upload files"',
            'text="Upload file"',
            '[role="menuitem"]:has-text("Upload")',
            'button:has-text("Upload files")',
            'button:has-text("Upload file")',
            'text="Upload images"',
            'text="From this device"',
            '[role="menuitem"]:has-text("Files")',
        ]
        return [s for s in [*configured, *defaults] if s]

    def _click_first(self, selectors: list[str], per_selector_ms: int = 1200) -> str | None:
        for sel in selectors:
            try:
                loc = self.page.locator(sel).first
                if loc.count() == 0:
                    continue
                if not loc.is_visible(timeout=per_selector_ms):
                    continue
                loc.click(timeout=3000)
                log.debug("clicked %s", sel)
                return sel
            except Exception:  # noqa: BLE001
                continue
        return None

    def _preview_count(self) -> int:
        """Upload previews/attachment chips currently visible in the composer."""
        try:
            return int(self.page.evaluate(JS_UPLOAD_PREVIEWS))
        except Exception:  # noqa: BLE001
            return -1

    # ------------------------------------------------------------- upload
    def upload_images(self, paths: list[Path]) -> int:
        """Attach reference images. Returns how many were attached."""
        max_refs = int(self.cfg.get("gemini.max_reference_images", 6))
        paths = [Path(p) for p in paths if Path(p).exists()][:max_refs]
        if not paths:
            return 0

        self._pending_files = paths
        self._chooser_fired = False
        self._files_set = False
        upload_wait = int(self.cfg.get("gemini.upload_wait_sec", 8))
        baseline = self._preview_count()

        # --- strategy 1: a real <input type=file> we can set directly (fastest).
        # MUST verify a preview actually appeared: a stale/hidden input can accept
        # the files silently and attach NOTHING (the per-slot attach bug).
        fi = self.find_file_input()
        if fi is not None:
            try:
                fi.set_input_files([str(p) for p in paths])
                self.page.wait_for_timeout(upload_wait * 1000)
                if self._preview_count() > baseline:
                    log.info("attached %d image(s) via <input type=file>", len(paths))
                    return len(paths)
                log.debug("input accepted files but no upload preview appeared - "
                          "falling back to the chooser")
            except Exception as exc:  # noqa: BLE001
                log.debug("direct input failed (%s) - falling back to chooser interception", exc)

        # --- strategy 2: click the + button; the filechooser handler feeds it
        clicked = self._click_first(self._attach_candidates())
        if clicked and not self._chooser_fired:
            self.page.wait_for_timeout(1200)
            # a menu may have appeared instead of the picker
            if not self._chooser_fired:
                self._click_first(self._menu_item_candidates())

        # --- strategy 3: wait for the chooser / an upload preview to appear
        deadline = time.time() + int(self.cfg.get("gemini.upload_timeout_sec", 25))
        attached = False
        while time.time() < deadline:
            if self._files_set or self._preview_count() > baseline:
                attached = True
                break
            self.page.wait_for_timeout(700)

        if attached:
            self.page.wait_for_timeout(upload_wait * 1000)
            log.info("attached %d reference image(s)", len(paths))
            return len(paths)

        diag = self.dump_diagnostics("upload_failed")
        raise GeminiError(
            "could not attach images to Gemini (no file chooser fired). "
            f"Diagnostics: {diag.get('json')} | {diag.get('screenshot')}. "
            "Run `python run.py probe --interactive` and share that JSON."
        )

    # ------------------------------------------------------------- model picker
    def ensure_image_model(self) -> bool:
        """Select 'Create image' in the model menu + lock the UI aspect ratio (2 passes)."""
        for attempt in (1, 2):
            if self._pick_image_model():
                return True
            if attempt == 1:
                self.page.wait_for_timeout(1500)
        log.warning("no image-capable model matched - using the default model "
                    "(text-only replies may follow; check gemini.image_model_hints)")
        return False

    def _image_hints(self) -> list[str]:
        hints = [h.lower() for h in (self.cfg.get("gemini.image_model_hints") or
                                     ["create images", "nano banana", "imagen", "image"])]
        # the picker menu item the UI provides is literally "Create image"
        return ["create image", "create images", *hints]

    def _click_create_image_label(self) -> bool:
        """Click the 'Create image' menu item by its real label element.

        Gemini's picker renders every menu row with a `div.gem-menu-item-label`;
        clicking the label itself (which bubbles to the row) is the most stable
        route there - the surrounding widget markup changes constantly.
        """
        hints = self._image_hints()
        try:
            labels = self.page.locator("div.gem-menu-item-label")
            count = min(labels.count(), 40)
        except Exception:  # noqa: BLE001
            return False
        for i in range(count):
            try:
                text = (labels.nth(i).inner_text(timeout=700) or "").strip().lower()
            except Exception:  # noqa: BLE001
                continue
            if text and any(h in text for h in hints):
                try:
                    labels.nth(i).click(timeout=3000)
                    log.info("selected image mode: %r", text[:40])
                    return True
                except Exception:  # noqa: BLE001
                    continue
        return False

    def _set_aspect_ratio_ui(self) -> bool:
        """Lock the create-image ASPECT RATIO dropdown (UI-side, per chat).

        Flow: the 'Aspect ratio' row (with its arrow) opens the ratio menu,
        where the value lives in another gem-menu-item-label - e.g. 3:4.
        The final geometry also lives in every prompt; this just makes the
        widget itself agree, because the UI setting can silently override
        prompt text.
        """
        ratio = str(self.cfg.get("gemini.aspect_ratio", "") or "").strip()
        if not ratio:
            return False
        row = self.page.locator('div.row-container:has-text("Aspect ratio")').first
        try:
            if not row.is_visible(timeout=2500):
                log.debug("aspect ratio row not visible - skipping UI lock")
                return False
            row.click(timeout=3000)
        except Exception:  # noqa: BLE001
            log.debug("aspect ratio row not clickable - skipping UI lock")
            return False
        self.page.wait_for_timeout(800)
        clicked = self._click_first([
            f'div.gem-menu-item-label:text-is("{ratio}")',
            f'mat-list-item:has(div.gem-menu-item-label:text-is("{ratio}"))',
            f'[role="menuitem"]:has-text("{ratio}")',
        ], per_selector_ms=1000)
        if clicked:
            log.info("aspect ratio locked in the UI: %s", ratio)
            self.page.wait_for_timeout(600)
        else:
            log.debug("aspect ratio option %r not found - prompt lock still applies", ratio)
            self.page.keyboard.press("Escape")
        return bool(clicked)

    def _pick_image_model(self) -> bool:
        """One pass: open the picker, select Create image (XPath), lock aspect ratio (XPath)."""
        openers = self.cfg.get("gemini.selectors.model_picker") or [
            'button[aria-label*="model" i]', '[data-test-id*="model-selector" i]',
            'button:has-text("Flash")', 'button:has-text("Pro")',
        ]
        if not self._click_first(openers):
            log.debug("model picker not found (skipping)")
            return False
        self.page.wait_for_timeout(1000)

        # Use exact XPath for "Create image" option
        create_img_sel = self._sel("create_image_option", '')
        if create_img_sel:
            try:
                if create_img_sel.startswith('//') or create_img_sel.startswith('xpath='):
                    loc = self.page.locator(f"xpath={create_img_sel}")
                else:
                    loc = self.page.locator(create_img_sel)
                if loc.count() > 0 and loc.is_visible(timeout=2000):
                    loc.first.click(timeout=3000)
                    log.info("selected 'Create image' via XPath")
                else:
                    return False
            except Exception as e:  # noqa: BLE001
                log.debug("create_image XPath failed: %s", e)
                return False
        else:
            log.debug("create_image_option selector not configured")
            return False

        self.page.wait_for_timeout(1200)

        # Set aspect ratio using XPath
        ratio = str(self.cfg.get("gemini.aspect_ratio", "") or "").strip()
        if ratio:
            self._set_aspect_ratio_ui_xpath()
        return True

    def _set_aspect_ratio_ui_xpath(self) -> bool:
        """Lock aspect ratio using XPath selectors from config."""
        ratio = str(self.cfg.get("gemini.aspect_ratio", "") or "").strip()
        if not ratio:
            return False

        # Click aspect ratio button
        ar_btn_sel = self._sel("aspect_ratio_button", '')
        if ar_btn_sel:
            try:
                if ar_btn_sel.startswith('//') or ar_btn_sel.startswith('xpath='):
                    loc = self.page.locator(f"xpath={ar_btn_sel}")
                else:
                    loc = self.page.locator(ar_btn_sel)
                if loc.count() > 0 and loc.is_visible(timeout=2000):
                    loc.first.click(timeout=3000)
                    self.page.wait_for_timeout(800)
            except Exception:  # noqa: BLE001
                pass

        # Click 3:4 option
        ar_opt_sel = self._sel("aspect_ratio_3_4", '')
        if ar_opt_sel:
            try:
                if ar_opt_sel.startswith('//') or ar_opt_sel.startswith('xpath='):
                    loc = self.page.locator(f"xpath={ar_opt_sel}")
                else:
                    loc = self.page.locator(ar_opt_sel)
                if loc.count() > 0 and loc.is_visible(timeout=2000):
                    loc.first.click(timeout=3000)
                    log.info("aspect ratio locked via XPath: %s", ratio)
                    self.page.wait_for_timeout(600)
                    return True
            except Exception:  # noqa: BLE001
                pass

        # Fallback to old method
        return self._set_aspect_ratio_ui()

    # ------------------------------------------------------------- batch session
    def begin_batch(self, master: str = "", reference_images: list = None) -> None:
        """Open ONE chat for the whole ASIN batch and set up image generation mode.

        STRICT SEQUENCE (enforced):
        1. Open new chat
        2. Upload base/reference images FIRST
        3. Open model picker and select "Create image"
        4. Set aspect ratio to 3:4
        (No master prompt - slot prompts carry all instructions)
        """
        self._active_master = (master or "").strip()   # remembered for retry restarts
        self.new_chat()
        self._pending_dest = None       # the master seed is not a slot download
        self._handled_download = None

        # STEP 1: Upload base/reference images FIRST
        if reference_images:
            log.info("uploading %d base/reference images", len(reference_images))
            self.upload_images(reference_images)
            self._refs_attached = True
        else:
            log.warning("no reference images provided to begin_batch")

        # STEP 2: Open model picker and select "Create image" 
        if self.cfg.get("gemini.ensure_image_model", False):
            log.info("selecting 'Create image' mode via model picker")
            if not self._pick_image_model():
                log.warning("failed to select 'Create image' mode - proceeding anyway")

        # STEP 3: Set aspect ratio to 3:4 (done inside _pick_image_model, but ensure)
        ratio = str(self.cfg.get("gemini.aspect_ratio", "") or "").strip()
        if ratio:
            log.info("ensuring aspect ratio is %s", ratio)
            self._set_aspect_ratio_ui()

        # NO master prompt - slot prompts carry all instructions
        log.info("batch chat ready for image generation (strict sequence complete)")

    def restart_batch(self, reference_images: list = None) -> None:
        """Recovery path: open a FRESH chat and re-setup image generation mode.

        Used when a slot fails and pipeline retries it - retrying inside a chat
        that already contains a broken/refused reply drags quality down, so the
        retry gets a clean session with a fresh upload of the references.

        Follows the same STRICT SEQUENCE as begin_batch:
        1. New chat
        2. Upload reference images
        3. Open model picker and select "Create image"
        4. Set aspect ratio 3:4
        (No master prompt)
        """
        log.info("restarting batch chat (fresh session + re-setup image mode)")
        self.begin_batch(self._active_master, reference_images=reference_images)

    def _wait_for_reply(self, text_ok: bool = False) -> bool:
        """Wait until Gemini finished replying to the last submitted message.

        text_ok=True only requires the streaming cycle to end (master message);
        the slot flow always additionally requires an image (wait_for_generation).
        """
        timeout = int(self.cfg.get("gemini.master_ack_timeout_sec", 150))
        stop_sel = self._sel("stop_button")
        deadline = time.time() + timeout
        started = time.time()

        self.page.wait_for_timeout(3000)
        streaming_seen = False
        while time.time() < deadline:
            try:
                running = bool(stop_sel) and self.page.locator(stop_sel).count() > 0
                if running:
                    streaming_seen = True
                elif streaming_seen or (text_ok and self._new_reply_ready()) \
                        or time.time() - started > 15:
                    self.page.wait_for_timeout(1500)
                    return True
            except Exception:  # noqa: BLE001
                return False
            self.page.wait_for_timeout(1200)
        log.warning("reply wait timed out (%.0fs) - continuing anyway", time.time() - started)
        return False

    # ------------------------------------------------------------- chat
    def new_chat(self) -> None:
        try:
            self.page.goto(self.cfg.get("gemini.url", "https://gemini.google.com/app"),
                           wait_until="domcontentloaded")
            self.page.wait_for_timeout(1500)
            self._cool_down_on_block()
            self._dismiss_overlays()
        except GeminiError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("new_chat navigation issue: %s", exc)
        self._refs_attached = False   # a fresh chat needs its reference photos again
        # every fresh chat must land on the image-capable model, never on the
        # default model picker choice (which silently produces text replies)
        if self.cfg.get("gemini.ensure_image_model", False):
            self.ensure_image_model()

    def _should_ensure_mode(self) -> bool:
        """When to enforce the Create image mode for one slot.

        Default: every slot (strict). `gemini.ensure_image_model_every_slot: false`
        relaxes it to fresh chats only.
        """
        every_slot = bool(self.cfg.get("gemini.ensure_image_model_every_slot", True))
        return every_slot or self.cfg.get("gemini.new_chat_per_slot", False)

    def send_prompt(self, prompt: str) -> None:
        # remember what exists NOW; the reply that follows must ADD to this
        try:
            self._baseline_images = int(self.page.evaluate(JS_COUNT_IMAGES))
            self._baseline_blocks = int(self.page.evaluate(JS_COUNT_BLOCKS))
        except Exception:  # noqa: BLE001
            self._baseline_images = self._baseline_blocks = 0

        box = self.page.locator(self._sel("prompt_box", 'div[contenteditable="true"][role="textbox"]')).first
        box.click(timeout=15000)
        self.page.wait_for_timeout(400)
        self.page.keyboard.insert_text(prompt)
        self.page.wait_for_timeout(600)

        sent = False
        try:
            btn = self.page.locator(self._sel("send_button", 'button[aria-label*="Send"]')).first
            if btn.is_visible(timeout=1500):
                btn.click(timeout=4000)
                sent = True
        except Exception:  # noqa: BLE001
            pass
        if not sent:
            self.page.keyboard.press("Enter")
        log.debug("prompt sent (%d chars)", len(prompt))

    def _new_reply_ready(self) -> bool:
        """True once a reply from THIS message exists (beyond the baseline)."""
        try:
            imgs = int(self.page.evaluate(JS_COUNT_IMAGES))
            blocks = int(self.page.evaluate(JS_COUNT_BLOCKS))
            last_imgs = int(self.page.evaluate(JS_COUNT_LAST))
        except Exception:  # noqa: BLE001
            return False
        if imgs > self._baseline_images:
            return True
        return blocks > self._baseline_blocks and last_imgs > 0

    def _dismiss_lightbox(self) -> bool:
        """Dismiss any lightbox/modal that appears after image generation."""
        dismissed = False
        # Try close button
        close_sel = self._sel("lightbox_close", '')
        if close_sel:
            try:
                btn = self.page.locator(close_sel).first
                if btn.count() > 0 and btn.is_visible(timeout=1000):
                    btn.click(timeout=2000)
                    self.page.wait_for_timeout(500)
                    dismissed = True
            except Exception:  # noqa: BLE001
                pass
        # Try clicking backdrop
        if not dismissed:
            backdrop_sel = self._sel("lightbox_backdrop", '')
            if backdrop_sel:
                try:
                    backdrop = self.page.locator(backdrop_sel).first
                    if backdrop.count() > 0 and backdrop.is_visible(timeout=500):
                        backdrop.click(timeout=1000, position={"x": 10, "y": 10})
                        self.page.wait_for_timeout(500)
                        dismissed = True
                except Exception:  # noqa: BLE001
                    pass
        # Press Escape as last resort
        if not dismissed:
            try:
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(500)
                dismissed = True
            except Exception:  # noqa: BLE001
                pass
        if dismissed:
            log.debug("dismissed lightbox/modal after generation")
        return dismissed

    def wait_for_generation(self) -> None:
        timeout = int(self.cfg.get("gemini.generation_timeout_sec", 180))
        stop_sel = self._sel("stop_button")
        deadline = time.time() + timeout
        started = time.time()

        # phase 1: wait for the streaming cycle (stop button appears and clears)
        self.page.wait_for_timeout(3000)
        streaming_seen = False
        while time.time() < deadline:
            try:
                running = bool(stop_sel) and self.page.locator(stop_sel).count() > 0
                if running:
                    streaming_seen = True
                elif streaming_seen or self._new_reply_ready() or time.time() - started > 15:
                    break
            except Exception:  # noqa: BLE001
                break
            self.page.wait_for_timeout(1200)

        # phase 2: wait for the NEW reply to actually contain an image (batch-safe:
        # counts are measured against the baseline from send_prompt, never '> 0')
        while time.time() < deadline:
            try:
                if self._new_reply_ready():
                    self.page.wait_for_timeout(2500)
                    log.info("generation ready in %.0fs", time.time() - started)
                    self._dismiss_lightbox()
                    return
            except Exception:  # noqa: BLE001
                pass
            self.page.wait_for_timeout(2000)

        # no image -> almost always the prompt hit a text-only model / a refusal
        excerpt = ""
        try:
            excerpt = (self.page.evaluate(JS_LAST_TEXT) or "").strip()[:400]
        except Exception:  # noqa: BLE001
            pass
        raise GeminiError(
            "Gemini replied without an image"
            + (f": \"{excerpt}\"" if excerpt else "")
            + " | fix: set gemini.ensure_image_model: true in config.yaml (or pick the "
              "'Create images' / Nano Banana model manually during `run.py probe --interactive`)"
        )

    # ------------------------------------------------------------- download
    def collect_images(self) -> list[dict[str, Any]]:
        """Images of the LATEST reply only (batch-chat safe: THIS slot's panel)."""
        items = self.page.evaluate(JS_COLLECT_LAST) or []
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
            if raw and len(raw) > 20000:
                out.append({"bytes": raw, "w": item.get("w"), "h": item.get("h")})
        return out

    def download_via_button(self, dest: Path) -> Path | None:
        if self._handled_download is not None and self._handled_download.exists():
            return self._handled_download
        try:
            img = self.page.locator(self._sel("generated_image", 'model-response img')).last
            img.hover(timeout=5000)
            self.page.wait_for_timeout(700)
            btn = self.page.locator(
                'button[aria-label*="Download" i], [data-test-id*="download" i]'
            ).last
            with self.page.expect_download(timeout=25000) as dl_info:
                btn.click(timeout=5000)
            download = dl_info.value
            ensure_dir(dest.parent)
            suffix = Path(download.suggested_filename or "").suffix or ".png"
            target = dest.with_suffix(suffix)
            download.save_as(str(target))
            return target
        except Exception as exc:  # noqa: BLE001
            log.warning("button download failed: %s", exc)
            return None

    # ------------------------------------------------------------- diagnostics
    def dump_diagnostics(self, tag: str = "probe") -> dict[str, Any]:
        """Save DOM + screenshot + button inventory. Share these to fix selectors."""
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        out = ensure_dir(PROJECT_ROOT / "logs" / "gemini")
        html_path = out / f"{tag}_{stamp}.html"
        shot_path = out / f"{tag}_{stamp}.png"
        json_path = out / f"{tag}_{stamp}.json"

        report: dict[str, Any] = {"tag": tag, "at": dt.datetime.now().isoformat(timespec="seconds")}
        try:
            report["url"] = self.page.url
            report["title"] = self.page.title()
            report["file_inputs"] = self.page.evaluate(JS_FILE_INPUTS)
            report["buttons"] = self.page.evaluate(JS_BUTTONS)
            report["upload_previews"] = self.page.evaluate(JS_UPLOAD_PREVIEWS)
            report["image_count"] = self.page.evaluate(JS_COUNT_IMAGES)
            report["frames"] = [f.url for f in self._frames()]
        except Exception as exc:  # noqa: BLE001
            report["error"] = str(exc)
        try:
            html_path.write_text(self.page.content(), encoding="utf-8")
            self.page.screenshot(path=str(shot_path), full_page=True)
        except Exception as exc:  # noqa: BLE001
            log.debug("diagnostics capture issue: %s", exc)

        report["json"] = str(json_path)
        report["html"] = str(html_path)
        report["screenshot"] = str(shot_path)
        write_json(json_path, report)
        log.info("diagnostics saved -> %s", json_path)
        return report

    # ------------------------------------------------------------- one slot
    def generate_image(
        self,
        prompt: str,
        reference_images: list[Path],
        dest: Path,
        strategy: str = "auto",
        dry_run: bool = False,
        prompt_record: str | None = None,
    ) -> dict[str, Any]:
        ensure_dir(dest.parent)

        if dry_run:
            p = dest.with_suffix(".txt")
            p.write_text(prompt_record or prompt, encoding="utf-8")
            log.info("[dry-run] prompt saved -> %s", p.name)
            return {"ok": True, "path": str(p), "dry_run": True}

        if self.cfg.get("gemini.new_chat_per_slot", False):
            self.new_chat()
        self._dismiss_overlays()

        # this slot's "related place": output/<ASIN>/generated/<slot file>.png
        self._pending_dest = dest
        self._handled_download = None

        # STRICT RULE: before EVERY image generation the composer must be on the
        # "Create image" mode - a continuous chat can silently fall back to the
        # text model between replies, which produces text instead of a panel.
        if self.cfg.get("gemini.ensure_image_model", False) and self._should_ensure_mode():
            self.ensure_image_model()

        # attach the reference photos on EVERY slot by default (configurable):
        # a fresh upload per panel keeps the product anchored when Gemini's
        # attention drifts in long batch chats
        every_slot = bool(self.cfg.get("gemini.attach_references_every_slot", True))
        fresh_chat = self.cfg.get("gemini.new_chat_per_slot", False)
        need_refs = bool(reference_images) and (fresh_chat or every_slot
                                                or not self._refs_attached)
        if need_refs:
            try:
                self.upload_images(reference_images)
                self._refs_attached = True
            except GeminiError as exc:
                self._refs_attached = False
                if (self.cfg.get("gemini.on_upload_failure", "fail") or "fail").lower() == "continue":
                    log.warning("%s -> continuing TEXT-ONLY (product accuracy will drop)", exc)
                else:
                    raise

        self.send_prompt(prompt)
        self.wait_for_generation()

        saved: Path | None = None
        if strategy in ("auto", "dom_fetch"):
            imgs = self.collect_images()
            if imgs:
                best = max(imgs, key=lambda i: len(i["bytes"]))
                saved = dest
                saved.write_bytes(best["bytes"])
                log.info("saved %s (%.0f KB, %sx%s)", dest.name, len(best["bytes"]) / 1024,
                         best.get("w"), best.get("h"))
        if saved is None and self._handled_download is not None and self._handled_download.exists():
            saved = self._handled_download
            log.info("using captured download for its related place: %s", saved.name)
        if saved is None and strategy in ("auto", "button"):
            saved = self.download_via_button(dest)

        if saved is None:
            raise GeminiError(f"no image could be captured for {dest.name}")

        human_delay(self.cfg.get("gemini.between_slots_sec", [6, 12]), "between slots")
        return {"ok": True, "path": str(saved)}
