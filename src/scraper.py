"""Amazon product scraper (Playwright).

Pulls product data + the full hi-res image gallery for one ASIN.
Everything is defensive: one missing selector must not fail the whole job.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any

from .config import Config
from .models import ProductData
from .utils import human_delay, log, retry

HIRES_SIZE = 2000          # try _SL2000_ first, then standard ladder
HIRES_LADDER = [2000, 1500, 1200, 1000]


class BlockedError(RuntimeError):
    """Amazon served a captcha / robot page."""


# --------------------------------------------------------------------- urls
_IMG_RE = re.compile(
    r"^(https://m\.media-amazon\.com/images/I/[A-Za-z0-9+\-_.]+?)(?:\._[A-Za-z0-9_,\-]+_)?\.(jpg|jpeg|png)$",
    re.I,
)

_ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")


def validate_asin(asin: str) -> str:
    """Normalise and validate a 10-character ASIN. Raises ValueError if invalid."""
    if not asin or not asin.strip():
        raise ValueError("ASIN must not be empty")
    cleaned = asin.strip().upper()
    if not _ASIN_RE.match(cleaned):
        raise ValueError(
            f"invalid ASIN: {asin!r} (must be 10 alphanumeric characters, e.g. B0DEMO1234)"
        )
    return cleaned


def hires_candidates(url: str) -> list[str]:
    """Turn a thumbnail URL into an ordered list of hi-res candidates."""
    if not url:
        return []
    url = url.split(" ")[0].strip()
    m = _IMG_RE.match(url)
    if not m:
        return [url]
    base, ext = m.group(1), m.group(2).lower()
    out = [f"{base}._AC_SL{size}_.{ext}" for size in HIRES_LADDER]
    out.append(f"{base}.{ext}")
    seen, uniq = set(), []
    for u in out:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


# --------------------------------------------------------------------- js extractors
_JS_EXTRACT = r"""
() => {
  const txt = (sel) => {
    const el = document.querySelector(sel);
    return el ? (el.innerText || el.textContent || '').trim() : '';
  };
  const all = (sel) => Array.from(document.querySelectorAll(sel));

  // ---- title / brand / misc
  const out = {
    title: txt('#productTitle'),
    brand: txt('#bylineInfo') || txt('#brand'),
    price: txt('.a-price .a-offscreen') || txt('#priceblock_ourprice') || txt('#corePrice_feature_div .a-offscreen'),
    rating: txt('#acrPopover') ? (document.querySelector('#acrPopover').getAttribute('title') || '') : '',
    reviews: txt('#acrCustomerReviewText'),
    availability: txt('#availability'),
    category: all('#wayfinding-breadcrumbs_feature_div li a').map(a => a.innerText.trim()).join(' > '),
    bullets: all('#feature-bullets li span.a-list-item').map(e => e.innerText.trim()).filter(Boolean),
    aplus: txt('#aplus'),
  };
  if (!out.brand) {
    const byline = all('#bylineInfo').map(e => e.innerText.trim()).join(' ');
    out.brand = byline;
  }

  // ---- attributes (tech spec tables + detail bullets)
  const attrs = {};
  all('#productDetails_techSpec_section_1 tr, #productDetails_detailBullets_sections1 tr, #productOverview_feature_div tr')
    .forEach(tr => {
      const th = tr.querySelector('th, td.a-span3, td.label');
      const td = tr.querySelector('td.a-span9, td.value, td:last-child');
      if (th && td) {
        const k = (th.innerText || '').trim().replace(/\s+/g, ' ');
        const v = (td.innerText || '').trim().replace(/\s+/g, ' ');
        if (k && v && k.length < 60) attrs[k] = v;
      }
    });
  all('#detailBullets_feature_div li').forEach(li => {
    const t = (li.innerText || '').trim();
    const m = t.split(/[:\u200f\u202a-\u202e]+/);
    if (m.length >= 2) {
      const k = m[0].trim(), v = m.slice(1).join(':').trim();
      if (k && v && k.length < 60) attrs[k] = v;
    }
  });
  out.attributes = attrs;

  // ---- variants
  out.variants = all('#twister .selection, #twister_feature_div li')
    .map(e => (e.innerText || '').trim().replace(/\s+/g, ' '))
    .filter(t => t && t.length < 60).slice(0, 12);

  // ---- gallery images: dynamic JSON (best source) + thumbnails
  const urls = [];
  const push = (u) => { if (u && typeof u === 'string' && u.includes('media-amazon.com')) urls.push(u); };

  const landing = document.querySelector('#landingImage');
  if (landing) {
    const dyn = landing.getAttribute('data-a-dynamic-image');
    if (dyn) { try { Object.keys(JSON.parse(dyn)).forEach(push); } catch (e) {} }
    push(landing.getAttribute('data-old-hires') || '');
    push(landing.getAttribute('src') || '');
  }
  all('#altImages li img, #imageBlock img, #main-image-container img').forEach(img => {
    push(img.getAttribute('src'));
    const dyn = img.getAttribute('data-a-dynamic-image');
    if (dyn) { try { Object.keys(JSON.parse(dyn)).forEach(push); } catch (e) {} }
  });
  // colour variations sometimes expose their own gallery in scripts
  const m = document.documentElement.innerHTML.match(/"hiRes":"(https:[^"]+)"/g) || [];
  m.slice(0, 20).forEach(s => push(s.replace(/"hiRes":"/, '').replace(/"$/, '')));

  out.images = Array.from(new Set(urls));
  out.canonical = document.querySelector('link[rel="canonical"]')?.href || location.href;
  return out;
}
"""


# --------------------------------------------------------------------- scraping
def _check_blocked(page, cfg: Config) -> None:
    markers = cfg.get("scrape.captcha_markers", []) or []
    try:
        body = page.content()[:400000]
    except Exception:  # noqa: BLE001
        return
    low = body.lower()
    for marker in markers:
        if marker.lower() in low:
            raise BlockedError(f"Amazon served an interstitial: '{marker}'")


def _url_for(cfg: Config, asin: str) -> str:
    domain = cfg.get("amazon.domain", "amazon.in")
    locale = cfg.get("amazon.locale", "en-IN")
    return f"https://www.{domain}/dp/{asin}?language={locale}"


@retry(times=3, backoff=10, exceptions=(Exception,), on_error=lambda a, e: log.warning("scrape retry %d: %s", a, e))
def scrape_asin(page, asin: str, cfg: Config) -> ProductData:
    """Scrape a single ASIN using an already-open Playwright page."""
    url = _url_for(cfg, asin)
    timeout = int(cfg.get("amazon.page_timeout_ms", 45000))
    log.info("scraping %s -> %s", asin, url)

    page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    page.wait_for_timeout(1200)

    # dismiss cookie banners if present
    for label in ("Accept", "Accept All", "Got it", "Dismiss"):
        try:
            btn = page.get_by_role("button", name=re.compile(label, re.I)).first
            if btn.is_visible(timeout=800):
                btn.click(timeout=1500)
                page.wait_for_timeout(500)
                break
        except Exception:  # noqa: BLE001
            pass

    _check_blocked(page, cfg)

    # lazy-load the gallery
    for _ in range(int(cfg.get("amazon.scroll_passes", 4))):
        page.mouse.wheel(0, 1400)
        page.wait_for_timeout(600)

    raw: dict[str, Any] = page.evaluate(_JS_EXTRACT)

    if not raw.get("title"):
        _check_blocked(page, cfg)
        raise RuntimeError(f"{asin}: product title not found (page layout / bot wall)")

    product = product_from_raw(raw, asin, cfg, fallback_url=url)

    product.scrape_status = "ok"
    log.info("%s | %s | %d bullets | %d images", asin, product.title[:60], len(product.bullets), len(product.image_urls))
    return product


def product_from_raw(raw: dict[str, Any], asin: str, cfg: Config, fallback_url: str = "") -> ProductData:
    """Build ProductData from the JS extractor output (pure function -> unit testable)."""
    seen_ids, candidates = set(), []
    for u in raw.get("images") or []:
        m = re.search(r"/images/I/([A-Za-z0-9+\-_]+)", u)
        img_id = m.group(1) if m else u
        if img_id in seen_ids:
            continue
        seen_ids.add(img_id)
        candidates.append(u)
    limit = int(cfg.get("amazon.max_gallery_images", 12))

    return ProductData(
        asin=asin,
        domain=cfg.get("amazon.domain", "amazon.in"),
        url=raw.get("canonical") or fallback_url,
        title=re.sub(r"\s+", " ", raw.get("title") or "").strip(),
        brand=re.sub(r"\s+", " ", raw.get("brand") or "").strip(),
        category=raw.get("category") or "",
        price=(raw.get("price") or "").strip(),
        rating=(raw.get("rating") or "").strip(),
        reviews=(raw.get("reviews") or "").strip(),
        availability=(raw.get("availability") or "").strip(),
        bullets=[b for b in (raw.get("bullets") or []) if b][:10],
        attributes={k: v for k, v in (raw.get("attributes") or {}).items() if k and v},
        variants=raw.get("variants") or [],
        aplus_text=(raw.get("aplus") or "")[:4000],   # <- field name matches models.ProductData
        image_urls=candidates[:limit],
        scraped_at=dt.datetime.now().isoformat(timespec="seconds"),
        scrape_status="ok",
    )


def scrape_many(asins: list[str], cfg: Config) -> dict[str, ProductData]:
    """Open one browser, scrape every ASIN, honour pacing between pages."""
    from playwright.sync_api import sync_playwright  # local import: heavy dep

    results: dict[str, ProductData] = {}
    with sync_playwright() as pw:
        ctx, _browser = launch_context(pw, cfg, headless=cfg.get("browser.headless", True))
        page = ctx.new_page()
        for idx, raw_asin in enumerate(asins, 1):
            try:
                asin = validate_asin(raw_asin)
            except ValueError as exc:
                log.error("invalid ASIN %r: %s", raw_asin, exc)
                results[raw_asin] = ProductData(
                    asin=raw_asin, scrape_status="failed", scrape_error=str(exc)
                )
                if idx < len(asins):
                    human_delay(cfg.get("amazon.delay_between_asins", [4, 9]), "between asins")
                continue
            log.info("[%d/%d] %s", idx, len(asins), asin)
            try:
                results[asin] = scrape_asin(page, asin, cfg)
            except Exception as exc:  # noqa: BLE001
                log.error("%s failed: %s", asin, exc)
                results[asin] = ProductData(asin=asin, scrape_status="failed", scrape_error=str(exc)[:500])
            if idx < len(asins):
                human_delay(cfg.get("amazon.delay_between_asins", [4, 9]), "between asins")
        ctx.close()
    return results


def launch_context(pw, cfg: Config, headless: bool = True):
    """Persistent context shared by the scraper and the Gemini driver (keeps logins)."""
    profile = cfg.resolve(cfg.get("browser.user_data_dir", ".browser-profile"))
    profile.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, Any] = {
        "headless": headless,
        "viewport": cfg.get("browser.viewport", {"width": 1440, "height": 900}),
        "locale": "en-US",
        "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        "ignore_default_args": ["--enable-automation"],
    }
    if cfg.get("browser.user_agent"):
        kwargs["user_agent"] = cfg.get("browser.user_agent")
    if cfg.get("browser.proxy"):
        kwargs["proxy"] = {"server": cfg.get("browser.proxy")}
    ctx = pw.chromium.launch_persistent_context(str(profile), **kwargs)
    ctx.add_init_script(
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        "window.chrome = { runtime: {} };"
    )
    return ctx, None
