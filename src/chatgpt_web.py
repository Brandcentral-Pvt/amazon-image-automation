"""Drive the ChatGPT web app (chatgpt.com) with Playwright.

No API key needed: a persisted Chrome profile keeps the ChatGPT session alive.

Follows the same 6-step workflow as Gemini:
1. Open ChatGPT web page (custom GPT URL)
2. Upload ref images
3. Select/Create mode (image generation depends on the selected ChatGPT experience)
4. Click generation button (send prompt)
5. Download Generation
6. Next Generation (caller loops)

Login session persisted in Chrome profile (like Gemini).
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import time
import io
import hashlib
import os
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from .config import Config
from .utils import PROJECT_ROOT, ensure_dir, human_delay, log, write_json

# JavaScript snippets for ChatGPT
JS_COUNT_IMAGES = """
() => {
  const imgs = Array.from(document.querySelectorAll('img'));
  return imgs.filter(i => {
    const src = i.currentSrc || i.src || '';
    return (i.naturalWidth || 0) >= 200 && (i.naturalHeight || 0) >= 200 && 
           !src.startsWith('data:image/svg') &&
           !src.includes('avatar') &&
           !src.includes('icon');
  }).length;
}
"""

JS_COUNT_BLOCKS = """
() => document.querySelectorAll('[data-message-author-role="assistant"]').length
"""

# Images inside the LAST assistant reply only
JS_COUNT_LAST = """
() => {
  const blocks = Array.from(document.querySelectorAll('[data-message-author-role="assistant"]'));
  if (!blocks.length) return 0;
  const imgs = Array.from(blocks[blocks.length - 1].querySelectorAll('img'));
  return imgs.filter(i => {
    const src = i.currentSrc || i.src || '';
    return (i.naturalWidth || 0) >= 200 && (i.naturalHeight || 0) >= 200 &&
           !src.startsWith('data:image/svg') &&
           !src.includes('avatar') &&
           !src.includes('icon');
  }).length;
}
"""

JS_COLLECT_LAST = """
async () => {
  const blocks = Array.from(document.querySelectorAll('[data-message-author-role="assistant"]'));
  if (!blocks.length) return [];
  const imgs = Array.from(blocks[blocks.length - 1].querySelectorAll('img'));
  const out = [];
  for (const img of imgs) {
    const src = img.currentSrc || img.src || '';
    if (!src) continue;
    if (src.startsWith('data:image/svg')) continue;
    if (src.includes('avatar') || src.includes('icon')) continue;
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
  const chips = document.querySelectorAll('[data-testid*="attachment"], [data-testid*="upload"], .attachment-chip').length;
  return previews + chips;
}
"""

JS_LAST_TEXT = """
() => {
  const nodes = Array.from(document.querySelectorAll('[data-message-author-role="assistant"]'));
  if (!nodes.length) return '';
  return (nodes[nodes.length - 1].innerText || '').trim().slice(0, 1200);
}
"""

class ChatGPTError(RuntimeError):
    pass


class ChatGPTWeb:
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
        self._baseline_images = 0
        self._baseline_blocks = 0
        self._baseline_users = 0
        self._response_block_index = -1
        self._refs_attached = False
        # download routing
        self._pending_dest: Path | None = None
        self._handled_download: Path | None = None
        self._seen_image_hashes: set[str] = set()
        self._reference_hashes: set[str] = set()

    # ------------------------------------------------------------- lifecycle
    def __enter__(self) -> "ChatGPTWeb":
        self.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def start(self) -> None:
        from playwright.sync_api import sync_playwright
        from .browser import launch_chatgpt_context  # use ChatGPT-specific launcher

        self._pw = sync_playwright().start()
        self._ctx, _ = launch_chatgpt_context(self._pw, self.cfg, headless=self.headless)
        self.page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()

        # Intercept file chooser
        self.page.on("filechooser", self._on_filechooser)
        self.page.on("download", self._on_download)

        # Go to ChatGPT custom GPT URL
        url = self.cfg.get("chatgpt.url", "https://chatgpt.com/g/g-p-6aeafd8cf6148191b9034dbaaf247ba1")
        self.page.goto(url, wait_until="domcontentloaded")
        self.page.wait_for_timeout(3000)
        self._cool_down_on_block()
        self._dismiss_overlays()
        self._assert_logged_in()

    def close(self) -> None:
        try:
            if self._ctx:
                self._ctx.close()
        finally:
            if self._pw:
                self._pw.stop()

    # ------------------------------------------------------------- file chooser
    def _on_filechooser(self, chooser) -> None:
        self._chooser_fired = True
        log.debug("file chooser intercepted")
        if not self._pending_files:
            return
        try:
            chooser.set_files([str(p) for p in self._pending_files])
            self._files_set = True
            log.info("file chooser fed %d file(s)", len(self._pending_files))
        except Exception as exc:
            self._upload_error = str(exc)
            log.warning("could not set files on chooser: %s", exc)

    def _sel(self, key: str, default: str = "") -> str:
        return self.cfg.get(f"chatgpt.selectors.{key}", default) or default

    def _frames(self):
        try:
            return self.page.frames or [self.page.main_frame]
        except Exception:
            return [self.page.main_frame]

    def find_file_input(self):
        for frame in self._frames():
            for sel in (self._sel("file_input", 'input[type="file"]'), 'input[type="file"]', 'input[accept*="image"]'):
                try:
                    loc = frame.locator(sel)
                    if loc.count() > 0:
                        return loc.first
                except Exception:
                    continue
        return None

    # ------------------------------------------------------------- downloads
    def _on_download(self, download) -> None:
        try:
            name = download.suggested_filename or f"chatgpt_{dt.datetime.now():%Y%m%d_%H%M%S}.png"
            suffix = Path(name).suffix or ".png"
            if self._pending_dest is not None:
                target = self._pending_dest.with_name(self._pending_dest.name + ".download" + suffix)
            else:
                target = ensure_dir(self.cfg.out_root() / "_downloads") / name
            ensure_dir(target.parent)
            download.save_as(str(target))
            self._handled_download = target
            log.info("download captured -> related place: %s", target)
        except Exception as exc:
            log.debug("download handler issue: %s", exc)

    # ------------------------------------------------------------- traffic blocks
    def _looks_blocked(self) -> bool:
        try:
            return "/sorry/" in (self.page.url or "") or "challenge" in (self.page.url or "")
        except Exception:
            return False

    def _cool_down_on_block(self) -> None:
        if not self._looks_blocked():
            return
        wait = int(self.cfg.get("chatgpt.block_wait_sec", 120))
        log.warning("ChatGPT traffic block - cooling down for %ds", wait)
        try:
            out = ensure_dir(PROJECT_ROOT / "logs" / "chatgpt")
            stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.page.screenshot(path=str(out / f"blocked_{stamp}.png"))
        except Exception:
            pass
        self.page.wait_for_timeout(wait * 1000)
        try:
            self.page.goto(self.cfg.get("chatgpt.url", "https://chatgpt.com/g/g-p-6aeafd8cf6148191b9034dbaaf247ba1"),
                           wait_until="domcontentloaded")
            self.page.wait_for_timeout(3000)
        except Exception:
            pass
        if self._looks_blocked():
            raise ChatGPTError("ChatGPT still blocking. Slow down or try later.")

    def _dismiss_overlays(self) -> None:
        for sel in self.cfg.get("chatgpt.selectors.consent_buttons", []) or []:
            try:
                btn = self.page.locator(sel).first
                if btn.is_visible(timeout=1200):
                    btn.click(timeout=2000)
                    self.page.wait_for_timeout(600)
            except Exception:
                pass

    def _assert_logged_in(self) -> None:
        box = self._sel("prompt_box")
        try:
            if not self.page.locator(box).first.is_visible(timeout=15000):
                raise ChatGPTError("prompt box not visible - not logged in")
        except ChatGPTError:
            raise
        except Exception as exc:
            raise ChatGPTError(
                "ChatGPT not logged in. Run: python run.py chatgpt-login --headed"
            ) from exc

    # ------------------------------------------------------------- upload
    def _attach_candidates(self) -> list[str]:
        configured = self.cfg.get("chatgpt.selectors.attach_buttons") or []
        defaults = [
            'button[aria-label*="Attach" i]',
            'button[aria-label*="Upload" i]',
            'button[aria-label*="Add" i]',
            '[data-testid*="attachment" i]',
            '[data-testid*="upload" i]',
            'button:has-text("Attach")',
            'button:has-text("Upload")',
        ]
        return [s for s in [*configured, *defaults] if s]

    def _menu_item_candidates(self) -> list[str]:
        configured = self.cfg.get("chatgpt.selectors.upload_menu_items") or []
        defaults = [
            'text="Upload from computer"',
            'text="Upload file"',
            '[role="menuitem"]:has-text("Upload")',
            'button:has-text("Upload from computer")',
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
            except Exception:
                continue
        return None

    def _preview_count(self) -> int:
        try:
            return int(self.page.evaluate(JS_UPLOAD_PREVIEWS))
        except Exception:
            return -1

    def upload_images(self, paths: list[Path]) -> int:
        requested = [Path(p) for p in paths]
        max_refs = int(self.cfg.get("chatgpt.max_reference_images", 10))
        if not requested:
            return 0
        if len(requested) > max_refs:
            raise ChatGPTError(f"{len(requested)} reference files exceed the configured limit {max_refs}")
        if any(not p.is_file() for p in requested):
            raise ChatGPTError("one or more reference images are missing")
        self._pending_files = requested
        self._chooser_fired = False
        self._files_set = False
        baseline = self._preview_count()
        if baseline < 0:
            raise ChatGPTError("could not inspect upload attachments")

        try:
            fi = self.find_file_input()
            if fi is not None:
                try:
                    fi.set_input_files([str(p) for p in requested])
                except Exception as exc:
                    log.debug("direct file input failed: %s", exc)
            else:
                clicked = self._click_first(self._attach_candidates())
                if not clicked:
                    raise ChatGPTError("no attachment control available")
                if not self._chooser_fired:
                    self._click_first(self._menu_item_candidates())

            deadline = time.monotonic() + int(self.cfg.get("chatgpt.upload_timeout_sec", 30))
            while time.monotonic() < deadline:
                current = self._preview_count()
                if current >= baseline + len(requested):
                    self._refs_attached = True
                    return len(requested)
                self.page.wait_for_timeout(500)
            raise ChatGPTError(
                f"attachment verification timed out: expected {len(requested)} new previews, "
                f"observed {max(0, self._preview_count() - baseline)}"
            )
        finally:
            self._pending_files = []

    # ------------------------------------------------------------- send prompt
    def send_prompt(self, prompt: str) -> None:
        if not prompt.strip():
            raise ChatGPTError("empty generation prompt")
        self._baseline_blocks = int(self.page.evaluate(JS_COUNT_BLOCKS))
        self._baseline_users = int(self.page.locator('[data-message-author-role="user"]').count())
        self._response_block_index = self._baseline_blocks
        box = self.page.locator(self._sel("prompt_box")).first
        box.click(timeout=15000)
        box.fill(prompt, timeout=15000)
        actual = (box.inner_text(timeout=5000) or "").strip()
        if actual != prompt.strip():
            raise ChatGPTError("prompt composer contents did not match requested prompt")
        btn = self.page.locator(self._sel("send_button", 'button[data-testid="send-button"]')).first
        if not btn.is_visible(timeout=5000) or not btn.is_enabled(timeout=5000):
            raise ChatGPTError("send button is not ready")
        btn.click(timeout=5000)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self.page.locator('[data-message-author-role="user"]').count() > self._baseline_users:
                log.info("ChatGPT accepted prompt (%d chars)", len(prompt))
                return
            self.page.wait_for_timeout(300)
        raise ChatGPTError("prompt submission was not confirmed; do not retry blindly")

    def _new_reply_ready(self) -> bool:
        try:
            blocks = self.page.locator('[data-message-author-role="assistant"]')
            if blocks.count() <= self._baseline_blocks:
                return False
            for index in range(self._baseline_blocks, blocks.count()):
                images = blocks.nth(index).locator("img")
                for j in range(images.count()):
                    image = images.nth(j)
                    if image.evaluate("(el) => el.complete && el.naturalWidth >= 200 && el.naturalHeight >= 200"):
                        return True
            return False
        except Exception:
            return False

    # ------------------------------------------------------------- wait for generation
    def wait_for_generation(self) -> None:
        timeout = int(self.cfg.get("chatgpt.generation_timeout_sec", 300))
        deadline = time.monotonic() + timeout
        started = time.monotonic()

        self.page.wait_for_timeout(3000)
        stable = 0
        while time.monotonic() < deadline:
            try:
                # A visible stop control indicates that the response is still streaming.
                stop = self.page.locator('button[data-testid="stop-button"], button[aria-label*="Stop generating" i]')
                running = any(stop.nth(i).is_visible() for i in range(stop.count()))
                if self._new_reply_ready() and not running:
                    stable += 1
                    if stable >= 3:
                        log.info("generation ready in %.0fs", time.monotonic() - started)
                        self._dismiss_lightbox()
                        return
                else:
                    stable = 0
            except Exception:
                stable = 0
            self.page.wait_for_timeout(2000)

        excerpt = ""
        try:
            excerpt = (self.page.evaluate(JS_LAST_TEXT) or "").strip()[:400]
        except Exception:
            pass
        raise ChatGPTError(
            "ChatGPT replied without an image"
            + (f": \"{excerpt}\"" if excerpt else "")
            + " | Verify that ChatGPT produced an image in this conversation"
        )

    # ------------------------------------------------------------- lightbox dismiss
    def _dismiss_lightbox(self) -> bool:
        dismissed = False
        # Try close button
        close_sel = self._sel("lightbox_close", '')
        if close_sel:
            try:
                btn = self.page.locator(close_sel).first
                if btn.count() > 0 and btn.is_visible(timeout=1000):
                    btn.click(timeout=2000)
                    self.page.wait_for_timeout(500)
                    return True
            except Exception:
                pass
        # Press Escape (safest)
        try:
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(500)
            return True
        except Exception:
            pass
        return False

    # ------------------------------------------------------------- download
    def _validated_image(self, raw: bytes, expected: Path) -> bytes:
        try:
            with Image.open(io.BytesIO(raw)) as img:
                img.verify()
            with Image.open(io.BytesIO(raw)) as img:
                width, height = img.size
                if max(width, height) < int(self.cfg.get("chatgpt.image_check.min_long_side_px", 1000)):
                    raise ChatGPTError(f"generated image is too small: {width}x{height}")
                ratio = min(width, height) / max(width, height)
                tolerance = float(self.cfg.get("chatgpt.image_check.aspect_tolerance", 0.07))
                if not any(abs(ratio - target) <= tolerance for target in (0.75, 5.0 / 6.0)):
                    raise ChatGPTError(f"invalid image aspect ratio: {width}x{height}")
                if expected.suffix.lower() == ".png":
                    converted = io.BytesIO()
                    img.convert("RGB").save(converted, format="PNG")
                    return converted.getvalue()
                if expected.suffix.lower() in (".jpg", ".jpeg"):
                    converted = io.BytesIO()
                    img.convert("RGB").save(converted, format="JPEG", quality=95)
                    return converted.getvalue()
                raise ChatGPTError(f"unsupported output extension: {expected.suffix}")
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ChatGPTError("downloaded bytes are not a valid image") from exc

    @staticmethod
    def _content_fingerprint(raw: bytes) -> str:
        with Image.open(io.BytesIO(raw)) as img:
            return hashlib.sha256(img.convert("RGB").resize((128, 128)).tobytes()).hexdigest()

    def _save_candidate(self, raw: bytes, dest: Path) -> str:
        valid = self._validated_image(raw, dest)
        fingerprint = self._content_fingerprint(valid)
        if fingerprint in self._reference_hashes:
            raise ChatGPTError("image duplicates an uploaded reference")
        if fingerprint in self._seen_image_hashes:
            raise ChatGPTError("image duplicates an earlier generated slot")
        tmp = dest.with_name(dest.name + ".tmp")
        try:
            tmp.write_bytes(valid)
            os.replace(tmp, dest)
        finally:
            tmp.unlink(missing_ok=True)
        self._seen_image_hashes.add(fingerprint)
        return hashlib.sha256(valid).hexdigest()

    def collect_images(self) -> list[dict[str, Any]]:
        if self.page.locator('[data-message-author-role="assistant"]').count() <= self._baseline_blocks:
            return []
        # Only inspect responses created after this prompt, never earlier history.
        out: list[dict[str, Any]] = []
        blocks = self.page.locator('[data-message-author-role="assistant"]')
        for index in range(self._baseline_blocks, blocks.count()):
            block = blocks.nth(index)
            for img in block.locator("img").all():
                try:
                    info = img.evaluate("(el) => ({src: el.currentSrc || el.src, w: el.naturalWidth, h: el.naturalHeight})")
                    src = info.get("src", "")
                    if info.get("w", 0) < 200 or info.get("h", 0) < 200 or not src:
                        continue
                    if src.startswith("blob:") or src.startswith("data:"):
                        b64 = img.evaluate("""async el => {
                            const r = await fetch(el.currentSrc || el.src);
                            const bytes = new Uint8Array(await r.arrayBuffer());
                            let binary = '';
                            for (let i=0; i<bytes.length; i+=8192) {
                              binary += String.fromCharCode(...bytes.slice(i,i+8192));
                            }
                            return btoa(binary);
                        }""")
                        raw = base64.b64decode(b64)
                    elif src.startswith("https://"):
                        response = self.page.request.get(src, timeout=30000)
                        raw = response.body() if response.ok else b""
                    else:
                        continue
                    if len(raw) > 20000:
                        out.append({"bytes": raw, "w": info["w"], "h": info["h"]})
                except Exception as exc:
                    log.debug("image collection candidate failed: %s", exc)
        return out

    def download_via_button(self, dest: Path) -> Path | None:
        # A browser download event is only accepted when it is routed to this slot.
        candidate = self._handled_download
        if candidate is None or not candidate.exists():
            return None
        raw = candidate.read_bytes()
        self._save_candidate(raw, dest)
        if candidate != dest:
            candidate.unlink(missing_ok=True)
        return dest

    # ------------------------------------------------------------- diagnostics
    def dump_diagnostics(self, tag: str = "probe") -> dict[str, Any]:
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        out = ensure_dir(PROJECT_ROOT / "logs" / "chatgpt")
        html_path = out / f"{tag}_{stamp}.html"
        shot_path = out / f"{tag}_{stamp}.png"
        json_path = out / f"{tag}_{stamp}.json"

        report: dict[str, Any] = {"tag": tag, "at": dt.datetime.now().isoformat(timespec="seconds")}
        try:
            report["url"] = self.page.url
            report["title"] = self.page.title()
            report["file_inputs"] = self.page.evaluate(JS_FILE_INPUTS)
            report["upload_previews"] = self.page.evaluate(JS_UPLOAD_PREVIEWS)
            report["image_count"] = self.page.evaluate(JS_COUNT_IMAGES)
            report["frames"] = [f.url for f in self._frames()]
        except Exception as exc:
            report["error"] = str(exc)
        try:
            html_path.write_text(self.page.content(), encoding="utf-8")
            self.page.screenshot(path=str(shot_path), full_page=True)
        except Exception as exc:
            log.debug("diagnostics capture issue: %s", exc)

        report["json"] = str(json_path)
        report["html"] = str(html_path)
        report["screenshot"] = str(shot_path)
        write_json(json_path, report)
        log.info("diagnostics saved -> %s", json_path)
        return report

    # ------------------------------------------------------------- one slot (6-step)
    def generate_image(
        self,
        prompt: str,
        reference_images: list[Path],
        dest: Path,
        dry_run: bool = False,
        prompt_record: str | None = None,
    ) -> dict[str, Any]:
        ensure_dir(dest.parent)
        if dry_run:
            record = dest.with_suffix(".txt")
            record.write_text(prompt_record or prompt, encoding="utf-8")
            return {"ok": True, "path": str(record), "dry_run": True}

        self._handled_download = None
        self._pending_dest = dest
        try:
            self.send_prompt(prompt)
            self.wait_for_generation()
            images = self.collect_images()
            for item in sorted(images, key=lambda x: len(x["bytes"]), reverse=True):
                try:
                    digest = self._save_candidate(item["bytes"], dest)
                    return {"ok": True, "path": str(dest), "sha256": digest}
                except ChatGPTError as exc:
                    log.warning("image candidate rejected: %s", exc)
            saved = self.download_via_button(dest)
            if saved is not None:
                return {"ok": True, "path": str(saved)}
            raise ChatGPTError(f"no validated image captured for {dest.name}")
        finally:
            self._pending_dest = None
            self._handled_download = None

    # ------------------------------------------------------------- batch session
    def begin_batch(self, reference_images: list = None) -> None:
        """Start a fresh ASIN conversation and verify the reference attachments."""
        self.new_chat()
        self._seen_image_hashes = set()
        self._reference_hashes = set()
        for item in reference_images or []:
            try:
                self._reference_hashes.add(self._content_fingerprint(Path(item).read_bytes()))
            except (OSError, UnidentifiedImageError, ValueError) as exc:
                raise ChatGPTError(f"invalid reference image: {item}") from exc
        if reference_images:
            log.info("uploading %d reference images", len(reference_images))
            self.upload_images(reference_images)
        else:
            log.warning("no reference images provided")

    def restart_batch(self, reference_images: list = None) -> None:
        log.info("restarting: fresh session")
        self.begin_batch(reference_images=reference_images)

    def new_chat(self) -> None:
        try:
            url = self.cfg.get("chatgpt.url", "https://chatgpt.com/g/g-p-6aeafd8cf6148191b9034dbaaf247ba1")
            self.page.goto(url, wait_until="domcontentloaded")
            self.page.wait_for_timeout(3000)
            self._cool_down_on_block()
            self._dismiss_overlays()
        except ChatGPTError:
            raise
        except Exception as exc:
            log.warning("new_chat navigation issue: %s", exc)
        # A new batch must begin at a clean composer rather than an old reply.
        previous = self.page.locator('[data-message-author-role="assistant"]').count()
        if previous:
            selector = self._sel("new_chat_button", 'button[aria-label*="New chat" i], a[aria-label*="New chat" i]')
            button = self.page.locator(selector).first
            if button.count() == 0 or not button.is_visible(timeout=2000):
                raise ChatGPTError("could not create a fresh ChatGPT conversation")
            button.click(timeout=5000)
            self.page.wait_for_timeout(1500)
            if self.page.locator('[data-message-author-role="assistant"]').count():
                raise ChatGPTError("ChatGPT still displays previous conversation after new chat")
        self._assert_logged_in()
        self._refs_attached = False


def chatgpt_login(cfg: Config) -> int:
    """One-time ChatGPT login - saves session to Chrome profile."""
    from playwright.sync_api import sync_playwright
    from .browser import launch_chatgpt_context

    log.info("Opening browser - sign in to ChatGPT, then press Enter.")
    with sync_playwright() as pw:
        ctx, _ = launch_chatgpt_context(pw, cfg, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        url = cfg.get("chatgpt.url", "https://chatgpt.com/g/g-p-6aeafd8cf6148191b9034dbaaf247ba1")
        page.goto(url, wait_until="domcontentloaded")
        try:
            input("Press Enter after you've signed in to ChatGPT...")
        except EOFError:
            page.wait_for_timeout(120000)
        ctx.close()
    log.info("ChatGPT session saved to profile")
    return 0