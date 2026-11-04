"""Interactive, non-invasive selector discovery for the ChatGPT web UI.

Operator performs browser actions manually; this module NEVER uploads files,
sends prompts, triggers downloads or generates images.
Only short element metadata is saved. No cookies, page HTML, user messages,
file paths from attachment chips, or screenshots are collected.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from .utils import PROJECT_ROOT, ensure_dir, log

# DOM metadata only, bounded to likely controls. No message body text/HTML.
JS_INSPECT = r"""
() => {
  const query = [
    'form', 'textarea', '[contenteditable="true"]', 'input[type="file"]',
    'button', '[role="button"]', '[role="menuitem"]', '[role="dialog"]',
    '[data-testid]', '[aria-label]', 'img'
  ].join(',');
  const nodes = Array.from(document.querySelectorAll(query)).slice(0, 1500);
  const safe = (s, limit = 90) => String(s || '').slice(0, limit);
  const cssEscape = s => CSS.escape(String(s));
  function selector(el) {
    const tag = el.tagName.toLowerCase();
    if (el.id && !/^_r_/.test(el.id)) return '#' + cssEscape(el.id);
    const testid = el.getAttribute('data-testid');
    if (testid) return tag + '[data-testid="' + cssEscape(testid) + '"]';
    const aria = el.getAttribute('aria-label');
    if (aria) return tag + '[aria-label="' + cssEscape(aria) + '"]';
    if (el.getAttribute('contenteditable') === 'true')
      return tag + '[contenteditable="true"]';
    if (el.matches('input[type="file"]')) return 'input[type="file"]';
    return tag;
  }
  function visible(el) {
    const style = getComputedStyle(el), rect = el.getBoundingClientRect();
    return style.visibility !== 'hidden' && style.display !== 'none'
      && rect.width > 0 && rect.height > 0;
  }
  return nodes.filter(el => {
    if (el.matches('img')) {
      return visible(el) && el.naturalWidth >= 200 && el.naturalHeight >= 200
        && el.closest('[data-message-author-role="assistant"]');
    }
    return visible(el) || el.matches('input[type="file"]');
  }).slice(0, 280).map(el => {
    const tag = el.tagName.toLowerCase();
    const isImage = tag === 'img';
    const input = tag === 'input';
    const relevant = (el.getAttribute('aria-label') || el.getAttribute('data-testid') || '').toLowerCase();
    return {
      tag, selector: selector(el), visible: visible(el),
      role: safe(el.getAttribute('role'), 50),
      testid: safe(el.getAttribute('data-testid')),
      aria: safe(el.getAttribute('aria-label')),
      type: safe(el.getAttribute('type'), 40),
      accept: input ? safe(el.getAttribute('accept')) : '',
      multiple: input ? Boolean(el.multiple) : false,
      contenteditable: el.getAttribute('contenteditable') === 'true',
      disabled: Boolean(el.disabled),
      inForm: Boolean(el.closest('form')),
      inAssistantReply: Boolean(el.closest('[data-message-author-role="assistant"]')),
      textHint: (!isImage && /upload|attach|add|send|download|image|file|photo|new chat/i.test(relevant))
        ? safe((el.innerText || '').replace(/\\s+/g, ' '), 48) : '',
      imageSize: isImage ? [el.naturalWidth, el.naturalHeight] : null
    };
  });
}
"""

STAGES = [
    ("composer", "Leave the ChatGPT project open. Do not type anything yet."),
    ("attachment_menu", "Manually click the plus/attachment button and leave its menu open."),
    ("upload_dialog", "Manually select Upload files. Cancel the OS file picker if it opens, then leave ChatGPT visible."),
    ("prompt_ready", "Optionally attach a safe test image and enter a harmless draft prompt. Do NOT send it for this stage."),
    ("response_controls", "Optionally send a harmless test request yourself, then open any image you already have. No action is performed by the probe."),
]

def _candidate_score(element: dict, role: str) -> int:
    s = " ".join(str(element.get(k, "")) for k in ("selector", "role", "testid", "aria", "textHint")).lower()
    if role == "composer":
        return 100 if element.get("contenteditable") and element.get("inForm") else (70 if element.get("contenteditable") else (60 if element.get("tag") == "textarea" else 0))
    if role == "file_input":
        return 100 if element.get("tag") == "input" and element.get("type") == "file" else 0
    words = {
        "attach_button": ("composer-plus", "attach", "add files", "add photos"),
        "upload_menu": ("upload", "photos and files", "from computer"),
        "send_button": ("send-button", "send prompt", "send message"),
        "download_button": ("download", "save image"),
        "new_chat_button": ("new chat",),
    }.get(role, ())
    score = 0
    for w in words:
        if w in s:
            score += 30
    if role.endswith("button") and element.get("tag") != "button":
        score -= 10
    return score


def _recommend(elements: list[dict]) -> dict:
    result = {}
    for role in ("composer", "attach_button", "upload_menu", "file_input", "send_button", "download_button", "new_chat_button"):
        choices = [
            {**el, "score": _candidate_score(el, role)}
            for el in elements
            if _candidate_score(el, role) > 0
        ]
        choices.sort(key=lambda x: (x["score"], x.get("visible", False), bool(x.get("testid"))), reverse=True)
        result[role] = choices[:6]
    return result


def _snapshot(page, stage: str) -> dict:
    try:
        elements = page.evaluate(JS_INSPECT)
        return {
            "stage": stage,
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "host": "chatgpt.com" if "chatgpt.com" in (page.url or "") else "other",
            "elements": elements,
            "candidates": _recommend(elements),
        }
    except Exception as exc:
        return {"stage": stage, "error": f"{type(exc).__name__}: {str(exc)[:180]}"}


def run_chatgpt_probe(cfg, interactive: bool = False) -> int:
    """Inspect the real project UI using the configured Chrome profile."""
    from playwright.sync_api import sync_playwright
    from .browser import launch_chatgpt_context

    if not interactive:
        log.error("ChatGPT probe requires --interactive so you can control each UI step.")
        return 2
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = ensure_dir(PROJECT_ROOT / "logs" / "chatgpt" / ("probe_" + stamp))
    report = {"created_at": dt.datetime.now(dt.timezone.utc).isoformat(), "stages": []}
    log.info("Probe is observational. No automatic upload, prompt submission or download.")
    log.info("Do not share screenshots, cookies, session data or private message contents.")
    with sync_playwright() as pw:
        ctx, browser = launch_chatgpt_context(pw, cfg, headless=False)
        try:
            page = next((p for p in ctx.pages if "chatgpt.com" in (p.url or "")), None)
            if page is None:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
            target = cfg.get("chatgpt.url", "https://chatgpt.com/")
            if "chatgpt.com" not in (page.url or ""):
                page.goto(target, wait_until="domcontentloaded", timeout=60000)
            for stage, instruction in STAGES:
                print("\nPROBE STAGE: " + stage)
                print(instruction)
                print("Press Enter to capture, or type s then Enter to skip this stage.")
                try:
                    response = input("Capture? [Enter/s]: ").strip().lower()
                except EOFError:
                    response = "s"
                if response == "s":
                    report["stages"].append({"stage": stage, "skipped": True})
                    continue
                snap = _snapshot(page, stage)
                report["stages"].append(snap)
                path = out / f"{stage}.json"
                path.write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")
                summary = {k: [e["selector"] for e in v[:3]] for k, v in snap.get("candidates", {}).items() if v}
                print(json.dumps(summary, indent=2))
        finally:
            if browser is None:
                ctx.close()
            else:
                # Attached through CDP: disconnect when Playwright exits, do not close Chrome.
                pass
    report_path = out / "report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("ChatGPT probe saved selector metadata to %s", report_path)
    log.info("Review the JSON locally before sharing. It can contain UI labels and selectors.")
    return 0
