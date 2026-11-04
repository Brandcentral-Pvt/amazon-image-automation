"""Drive the ChatGPT web app (chatgpt.com) with Playwright.

No API key needed: a persisted Chrome profile keeps the ChatGPT session alive.

Follows the same 6-step workflow as Gemini:
1. Open ChatGPT web page (custom GPT URL)
2. Upload ref images
3. Select/Create mode (GPT-4o auto-triggers DALL-E 3)
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
from pathlib import Path
from typing import Any

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
        self._refs_attached = False
        # download routing
        self._pending_dest: Path | None = None
        self._handled_download: Path | None = None

    # ------------------------------------------------------------- lifecycle
    def __enter__(self) -> "ChatGPTWeb":
        self.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def start(self) -> None:
        from playwright.sync_api import sync_playwright
        from .browser import launch_gemini_context  # reuse Chrome launcher

        self._pw = sync_playwright().start()
        self._ctx, _ = launch_gemini_context(self._pw, self.cfg, headless=self.headless)
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
                target = self._pending_dest.with_suffix(suffix)
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
        max_refs = int(self.cfg.get("chatgpt.max_reference_images", 10))
        paths = [Path(p) for p in paths if Path(p).exists()][:max_refs]
        if not paths:
            return 0

        self._pending_files = paths
        self._chooser_fired = False
        self._files_set = False
        upload_wait = int(self.cfg.get("chatgpt.upload_wait_sec", 10))
        baseline = self._preview_count()

        # Strategy 1: direct input
        fi = self.find_file_input()
        if fi is not None:
            try:
                fi.set_input_files([str(p) for p in paths])
                self.page.wait_for_timeout(upload_wait * 1000)
                if self._preview_count() > baseline:
                    log.info("attached %d image(s) via <input type=file>", len(paths))
                    return len(paths)
                log.debug("input accepted files but no upload preview appeared - falling back")
            except Exception as exc:
                log.debug("direct input failed (%s) - falling back to chooser", exc)

        # Strategy 2: click attach button
        clicked = self._click_first(self._attach_candidates())
        if clicked and not self._chooser_fired:
            self.page.wait_for_timeout(1200)
            if not self._chooser_fired:
                self._click_first(self._menu_item_candidates())

        # Strategy 3: wait for chooser/preview
        deadline = time.time() + int(self.cfg.get("chatgpt.upload_timeout_sec", 30))
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
        raise ChatGPTError(
            "could not attach images to ChatGPT. "
            f"Diagnostics: {diag.get('json')} | {diag.get('screenshot')}. "
            "Run `python run.py chatgpt-probe --interactive`."
        )

    # ------------------------------------------------------------- send prompt
    def send_prompt(self, prompt: str) -> None:
        try:
            self._baseline_images = int(self.page.evaluate(JS_COUNT_IMAGES))
            self._baseline_blocks = int(self.page.evaluate(JS_COUNT_BLOCKS))
        except Exception:
            self._baseline_images = self._baseline_blocks = 0

        box = self.page.locator(self._sel("prompt_box")).first
        box.click(timeout=15000)
        self.page.wait_for_timeout(400)
        self.page.keyboard.insert_text(prompt)
        self.page.wait_for_timeout(600)

        sent = False
        try:
            btn = self.page.locator(self._sel("send_button", 'button[data-testid="send-button"]')).first
            if btn.is_visible(timeout=1500):
                btn.click(timeout=4000)
                sent = True
        except Exception:
            pass
        if not sent:
            self.page.keyboard.press("Enter")
        log.debug("prompt sent (%d chars)", len(prompt))

    def _new_reply_ready(self) -> bool:
        try:
            imgs = int(self.page.evaluate(JS_COUNT_IMAGES))
            blocks = int(self.page.evaluate(JS_COUNT_BLOCKS))
            last_imgs = int(self.page.evaluate(JS_COUNT_LAST))
        except Exception:
            return False
        if imgs > self._baseline_images:
            return True
        return blocks > self._baseline_blocks and last_imgs > 0

    # ------------------------------------------------------------- wait for generation
    def wait_for_generation(self) -> None:
        timeout = int(self.cfg.get("chatgpt.generation_timeout_sec", 300))
        deadline = time.time() + timeout
        started = time.time()

        self.page.wait_for_timeout(3000)
        while time.time() < deadline:
            try:
                if self._new_reply_ready():
                    self.page.wait_for_timeout(3000)
                    log.info("generation ready in %.0fs", time.time() - started)
                    self._dismiss_lightbox()
                    return
            except Exception:
                pass
            self.page.wait_for_timeout(2000)

        excerpt = ""
        try:
            excerpt = (self.page.evaluate(JS_LAST_TEXT) or "").strip()[:400]
        except Exception:
            pass
        raise ChatGPTError(
            "ChatGPT replied without an image"
            + (f": \"{excerpt}\"" if excerpt else "")
            + " | Check if GPT-4o triggered DALL-E 3"
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
    def collect_images(self) -> list[dict[str, Any]]:
        items = self.page.evaluate(JS_COLLECT_LAST) or []
        out: list[dict[str, Any]] = []
        for item in items:
            raw: bytes | None = None
            if item.get("b64"):
                try:
                    raw = base64.b64decode(item["b64"])
                except Exception:
                    raw = None
            if raw is None and str(item.get("src", "")).startswith("http"):
                try:
                    resp = self.page.request.get(item["src"], timeout=30000)
                    if resp.ok:
                        raw = resp.body()
                except Exception:
                    raw = None
            if raw and len(raw) > 20000:
                out.append({"bytes": raw, "w": item.get("w"), "h": item.get("h")})
        return out

    def download_via_button(self, dest: Path) -> Path | None:
        if self._handled_download is not None and self._handled_download.exists():
            return self._handled_download

        try:
            items = self.page.evaluate(JS_COLLECT_LAST) or []
            if not items:
                return None
            best_item = max(items, key=lambda i: (i.get("w", 0) * i.get("h", 0)))
            src = best_item.get("src", "")
            if not src:
                return None

            if src.startswith("blob:") or src.startswith("http"):
                try:
                    resp = self.page.request.get(best_item["src"], timeout=30000)
                    if resp.ok:
                        ensure_dir(dest.parent)
                        dest.write_bytes(resp.body())
                        log.info("downloaded generated image via fetch: %s", dest.name)
                        return dest
                except Exception:
                    pass
        except Exception:
            pass
        return None

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
            p = dest.with_suffix(".txt")
            p.write_text(prompt_record or prompt, encoding="utf-8")
            log.info("[dry-run] prompt saved -> %s", p.name)
            return {"ok": True, "path": str(p), "dry_run": True}

        self._handled_download = None
        self._pending_dest = dest

        # Step 4: Send prompt
        self.send_prompt(prompt)

        # Step 5: Wait + Download
        self.wait_for_generation()

        saved: Path | None = None
        imgs = self.collect_images()
        if imgs:
            best = max(imgs, key=lambda i: len(i["bytes"]))
            dest.write_bytes(best["bytes"])
            log.info("saved %s (%.0f KB, %sx%s)", dest.name, len(best["bytes"]) / 1024, best.get("w"), best.get("h"))
            saved = dest

        if saved is None:
            saved = self.download_via_button(dest)

        if saved is None:
            raise ChatGPTError(f"no image could be captured for {dest.name}")

        return {"ok": True, "path": str(saved)}

    # ------------------------------------------------------------- batch session
    def begin_batch(self, reference_images: list = None) -> None:
        """6-step setup:
        1. Open ChatGPT page
        2. Upload ref images
        3. (No model picker - GPT-4o auto-triggers DALL-E 3)
        """
        self.new_chat()
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
        self._refs_attached = False


def chatgpt_login(cfg: Config) -> int:
    """One-time ChatGPT login - saves session to Chrome profile."""
    from playwright.sync_api import sync_playwright
    from .browser import launch_gemini_context

    log.info("Opening browser - sign in to ChatGPT, then press Enter.")
    with sync_playwright() as pw:
        ctx, _ = launch_gemini_context(pw, cfg, headless=False)
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