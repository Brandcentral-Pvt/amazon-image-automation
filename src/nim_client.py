"""NVIDIA NIM client: dynamic AIIE casting/prompt intelligence per product.

One chat-completions call per ASIN (cached in data/nim/<asin>.json):
  - detects apparel vs hard-goods,
  - classifies audience / age group / fashion segment,
  - picks ONE commercially appropriate model persona ("Automatic Commercial
    Model Casting") - fashion-segment + marketplace aware, e.g. amazon.in ->
    Indian / South Asian model,
  - produces per-slot creative direction so each of the 8 panels gets the
    right treatment (models for clothing, product-only frames for hard goods).

Key lives in .env as NIM_API_KEY. Endpoint is OpenAI-compatible.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

import requests

from .config import Config
from .models import ProductData
from .utils import PROJECT_ROOT, ensure_dir, log

SYSTEM_HINT = (
    "You are the AIIE (Amazon Image Intelligence Engine) casting director. "
    "You analyse one Amazon product listing and return STRICT JSON only. "
    "No markdown, no commentary - a single JSON object."
)


class NIMError(RuntimeError):
    pass


def _parse_json(text: str) -> dict[str, Any]:
    """Best-effort JSON extraction from a model reply."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    # fallback: first {...} block in the reply
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        try:
            data = json.loads(text[start:end + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    raise NIMError(f"NIM reply is not JSON: {text[:200]!r}")


def _chat(cfg: Config, user_prompt: str, max_tokens: int | None = None,
          system: str | None = None) -> str:
    api_key = (cfg.get("nim.api_key") or "").strip() or None
    if api_key == "${NIM_API_KEY}":
        api_key = None
    if not api_key:
        import os
        api_key = os.environ.get("NIM_API_KEY", "")
    if not api_key:
        raise NIMError("NIM not configured: set NIM_API_KEY in .env")

    base = (cfg.get("nim.base_url") or "https://integrate.api.nvidia.com/v1").rstrip("/")
    models = [cfg.get("nim.model") or "nvidia/nemotron-3-ultra-550b-a55b"]
    models += list(cfg.get("nim.fallback_models") or ["openai/gpt-oss-20b"])

    timeout = int(cfg.get("nim.timeout_sec", 90))
    last_exc: Exception | None = None
    for model in models:
        try:
            resp = requests.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system",
                         "content": system or SYSTEM_HINT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": float(cfg.get("nim.temperature", 0.3)),
                    "max_tokens": int(max_tokens or cfg.get("nim.max_tokens", 1600)),
                },
                timeout=timeout,
            )
            if resp.status_code != 200:
                raise NIMError(f"NIM {model} HTTP {resp.status_code}: {resp.text[:200]}")
            content = (resp.json().get("choices") or [{}])[0].get("message", {}).get("content", "")
            if not content:
                raise NIMError(f"NIM {model} returned an empty reply")
            return content
        except (NIMError, requests.RequestException) as exc:
            log.warning("nim: %s failed (%s)", model, str(exc)[:150])
            last_exc = exc
    raise NIMError(f"all NIM models failed: {last_exc}")


SLOT_IDS = ["01_hero_white", "02_back_view", "03_side_view", "04_craft_story",
            "05_lifestyle", "06_styling_lookbook", "07_usp_infographic", "08_product_guide"]

# bump when the NIM prompt template itself changes - old cached castings were
# produced from the previous template and must be regenerated, not reused
# v3: model persona must be brand-new (never copied from the listing humans)
CAST_VERSION = 3


def local_casting(product: ProductData) -> dict[str, Any]:
    """Fallback casting when NIM is disabled/unreachable (never breaks the run)."""
    title = (product.title or "").lower()
    apparel_words = ("kurta", "kurti", "saree", "lehenga", "shirt", "t-shirt", "tshirt",
                     "jeans", "jacket", "hoodie", "dress", "ethnic", "salwar", "palazzo",
                     "top", "blouse", "legging", "jogger", "cargo", "shirt", "sherwani",
                     "nightwear", "bra", "innerwear", "sock", "trouser", "pant")
    is_apparel = any(w in title for w in apparel_words)
    audience = "Unisex"
    if any(w in title for w in ("women", "girl", "saree", "kurti", "lehenga", "blouse")):
        audience = "Women"
    elif any(w in title for w in ("men", "boy", "sherwani")):
        audience = "Men"
    model_card = (
        "professional Indian / South Asian commercial catalogue model, adult, natural "
        "appearance, no dramatic fashion pose; the product is always the hero"
    ) if is_apparel else "no human model: product-only commercial frames"
    return {
        "product_category": "apparel" if is_apparel else "other",
        "product_type": (product.category or "product"),
        "audience": audience,
        "age_group": "Adult" if audience in ("Women", "Men", "Unisex") else "Kids",
        "fashion_segment": "n/a" if not is_apparel else "Western",
        "model_required": is_apparel,
        "model_card": model_card,
        "background_family": ("premium commercial environment matching the product segment"
                              if is_apparel else "clean neutral premium staging"),
        "slot_direction": {sid: "follow the session background and casting rules" for sid in SLOT_IDS},
        "cast_version": CAST_VERSION,
        "source": "local-fallback",
    }


def nim_analyse(product: ProductData, cfg: Config, extra_notes: str = "") -> dict[str, Any]:
    """Return AIIE casting data for ONE product (NIM first, local fallback second)."""
    if not cfg.get("nim.enabled", False):
        return local_casting(product)

    cache_dir = ensure_dir(PROJECT_ROOT / "data" / "nim")
    cache = cache_dir / f"{product.asin}.json"
    if cache.exists():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if data.get("product_category") and "model_required" in data \
                    and data.get("cast_version") == CAST_VERSION:
                log.info("nim: using cached casting for %s", product.asin)
                return data
            if data.get("cast_version") != CAST_VERSION:
                log.info("nim: casting cache for %s is from an older template - refreshing",
                         product.asin)
        except Exception:  # noqa: BLE001
            pass

    summary = {
        "asin": product.asin,
        "title": product.title,
        "brand": product.brand,
        "category": product.category,
        "price": product.price,
        "marketplace": product.domain,
        "key_bullets": product.bullets[:6],
        "top_attributes": dict(list(product.attributes.items())[:10]),
        "seller_notes": extra_notes[:500] if extra_notes else "",
    }

    user_prompt = (
        "Analyse this Amazon product listing for listing-image production.\n"
        f"PRODUCT DATA (JSON):\n{json.dumps(summary, ensure_ascii=False)}\n\n"
        "Return ONLY this JSON object (no markdown):\n"
        "{\n"
        '  "product_category": "apparel" or "other",\n'
        '  "product_type": "<specific garment/product name, e.g. Rayon Kurti>",\n'
        '  "audience": "Women" | "Men" | "Girls" | "Boys" | "Infants" | "Toddlers" | "Kids" | "Unisex",\n'
        '  "age_group": "<e.g. Adult (18-35), Little Kids (5-8)>",\n'
        '  "fashion_segment": "<Western | Formal | Ethnic | Party | Winter | Casual Vacation | n/a>",\n'
        '  "model_required": true/false  (false for hard goods),\n'
        '  "model_card": "<ONE commercially appropriate, BRAND-NEW model persona: appearance, age, '
        'ethnicity suited to the marketplace (amazon.in -> Indian/South Asian; kids apparel -> child '
        'model of correct age and NEVER an adult), hair, natural expression. Must NOT resemble any '
        'person in the listing photos - those are product references only. The product stays the hero.",\n'
        '  "background_family": "<premium commercial environment family for images 2,3,5,6>",\n'
        '  "slot_direction": {\n'
        '    "01_hero_white": "<1-2 lines: angle/framing focus for this IMAGE 1>",\n'
        '    "02_back_view": "<...>",\n'
        '    "03_side_view": "<...>",\n'
        '    "04_craft_story": "<1-2 lines: ONE wide crafted-work scene for IMAGE 4 - product as '
        'the sharp hero in a believable craft environment (workshop/artisan setting, softly '
        'blurred). NO close-ups, NO macro crops, NO detail-crop collage. Name only verifiable '
        'product details the scene should keep accurate>",\n'
        '    "05_lifestyle": "<which believable aspirational environment>",\n'
        '    "06_styling_lookbook": "<ONE styling scenario that suits this garment>",\n'
        '    "07_usp_infographic": "<which verified USP blocks to feature>",\n'
        '    "08_product_guide": "<which single guide (size/fit/care) and its headings>"\n'
        "  }\n"
        "}\n"
        "Rules: for hard goods (electronics, home, food...) use model_required=false and "
        "describe product-only staging. For kids apparel the model MUST be a child of the "
        "matching age group. Fictional brand names may be invented for labels/analysis but every "
        "visible detail must stay truthful to the provided data."
    )

    try:
        reply = _chat(cfg, user_prompt)
        data = _parse_json(reply)
        if "slot_direction" not in data or not isinstance(data.get("slot_direction"), dict):
            data["slot_direction"] = {sid: "" for sid in SLOT_IDS}
        data.setdefault("source", "nim")
        data["cast_version"] = CAST_VERSION
        for sid in SLOT_IDS:
            data["slot_direction"].setdefault(sid, "")
        log.info("nim: casting ready for %s (%s, %s)", product.asin,
                 data.get("product_category"), data.get("audience"))
        cache.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data
    except (NIMError, requests.RequestException) as exc:
        log.warning("nim: dynamic casting failed for %s -> local fallback (%s)",
                    product.asin, str(exc)[:150])
        result = local_casting(product)
        try:
            cache.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        return result


def wait_respect(cfg: Config) -> None:
    """Polite pause between NIM calls if the user configures one."""
    seconds = float(cfg.get("nim.between_calls_sec", 1.0))
    if seconds > 0:
        time.sleep(seconds)


# ------------------------------------------------------------ prompt gallery
def nim_gallery_pick(product: ProductData, cfg: Config, candidates: list[dict[str, str]],
                     slot_rules: dict[str, str]) -> dict[str, str | None]:
    """NIM call 1: choose one gallery prompt key (or None) per slot.

    `candidates`: [{"key", "title", "preview"}]. Returns {slot_id: key | None}.
    """
    cand_lines = "\n".join(f"{c['key']} | {c.get('title', '')} | {c.get('preview', '')}"
                           for c in candidates)
    rules_txt = "\n".join(f'  {sid}: {msg}' for sid, msg in slot_rules.items())
    summary = _product_summary(product)

    user_prompt = (
        "TASK: for ONE Amazon listing, pick the best source prompt for each of 8 "
        "listing images from a professional prompt library.\n\n"
        f"PRODUCT (JSON):\n{summary}\n\n"
        f"SLOT BRIEFS (hard rules):\n{rules_txt}\n\n"
        "CANDIDATE PROMPTS (format: key | title | preview):\n"
        f"{cand_lines}\n\n"
        "Return ONLY this JSON (no markdown):\n"
        '{"picks": {'
        '"01_hero_white": "<candidate key or null>", '
        '"02_back_view": "<key or null>", '
        '"03_side_view": "<key or null>", '
        '"04_craft_story": "<key or null>", '
        '"05_lifestyle": "<key or null>", '
        '"06_styling_lookbook": "<key or null>", '
        '"07_usp_infographic": "<key or null>", '
        '"08_product_guide": "<key or null>"}}\n\n'
        "Selection rules:\n"
        "- Each slot gets ONE candidate key from the list above, or null when no "
        "candidate truly fits its brief (null is fine and triggers a safe default).\n"
        "- Match candidate pose/scene/framing to the slot brief, NOT just the garment.\n"
        "- Prefer using a DIFFERENT candidate for every slot; reuse is only allowed "
        "when no alternative exists.\n"
        "- Never pick a close-up/crop/macro candidate for 04_craft_story.\n"
        "- At most ONE picked prompt overall may be a close-up/macro candidate, "
        "and it should go to 08_product_guide.\n"
        "- Ignore any candidate that describes non-photo utility work (resizing, "
        "renaming, splitting files, face swapping tools)."
    )
    wait_respect(cfg)
    reply = _chat(cfg, user_prompt, max_tokens=int(cfg.get("gallery.nim_pick_tokens", 1400)))
    data = _parse_json(reply)
    picks = data.get("picks")
    if not isinstance(picks, dict):
        raise NIMError("gallery pick: reply has no 'picks' object")
    return {sid: (picks.get(sid) or None) for sid in SLOT_IDS}


def nim_gallery_adapt(product: ProductData, casting: dict[str, Any], cfg: Config,
                      chosen: list[dict[str, str]], slot_rules: dict[str, Any]) -> dict[str, str | None]:
    """NIM call 2: rewrite each chosen gallery body for THIS product and persona.

    Returns {slot_id: adapted text or None}.
    """
    items = "\n\n".join(
        f"=== SLOT {it['slot']} (source {it['key']}: {it['title']}) ===\n{it['body']}"
        for it in chosen
    )
    rules_txt = "\n".join(f"  {sid}: {rule}" for sid, rule in slot_rules.items())
    model_line = casting.get("model_card", "") if casting.get("model_required", False) else ""
    persona_block = (
        f"REPLACE every model/person description in the source with EXACTLY this "
        f"persona: {model_line}"
        if model_line
        else "REMOVE every human from the shot - rewrite each prompt as a product-only "
             "commercial frame (no person)."
    )
    casting_json = json.dumps({
        "model_required": casting.get("model_required", False),
        "model_card": model_line,
        "audience": casting.get("audience", ""),
        "age_group": casting.get("age_group", ""),
    }, ensure_ascii=False)

    user_prompt = (
        "TASK: adapt 8 source image prompts to ONE exact Amazon listing. Keep the "
        "creative bones (pose, framing, lighting, scene idea), rewrite the details.\n\n"
        f"PRODUCT (JSON):\n{_product_summary(product)}\n\n"
        f"CASTING (JSON): {casting_json}\n\n"
        f"SLOT CONTEXT:\n{rules_txt}\n\n"
        f"SOURCE PROMPTS:\n{items}\n\n"
        "Adaptation rules:\n"
        f"- Persona: {persona_block}.\n"
        "- Product naming: wherever the source names a different garment/product "
        "(apparel, shirt, pants...), rename it to THIS product's exact item "
        "(e.g. 'cotton kurta with palazzo and dupatta'); colour/texture claims must "
        f"stay generic since the exact look comes from the attached listing photos.\n"
        "- Remove any sentence that ties the person's face, identity or the background "
        "height/props to a 'reference' (the wrapper controls identity).\n"
        "- Remove aspect-ratio / pixel-size statements (locked elsewhere).\n"
        "- No on-image text instructions unless the slot brief requires it.\n"
        "- Keep each adapted body 3-10 sentences of plain prose, no headings, no JSON, "
        "no bullet lists; keep the language premium and photographic.\n"
        "- If a source prompt is fundamentally unusable for this product, return null "
        "for that slot.\n\n"
        "Return ONLY this JSON (no markdown):\n"
        '{"adapted": {"<slot_id>": "<adapted prompt text or null>", ...}} '
        "with every slot id listed above."
    )
    wait_respect(cfg)
    reply = _chat(cfg, user_prompt, max_tokens=int(cfg.get("gallery.nim_adapt_tokens", 6000)))
    data = _parse_json(reply)
    adapted = data.get("adapted")
    if not isinstance(adapted, dict):
        raise NIMError("gallery adapt: reply has no 'adapted' object")
    return {it["slot"]: (adapted.get(it["slot"]) or None) for it in chosen}


def _product_summary(product: ProductData) -> str:
    return json.dumps({
        "asin": product.asin,
        "title": product.title,
        "brand": product.brand,
        "category": product.category,
        "marketplace": product.domain,
        "key_bullets": product.bullets[:5],
    }, ensure_ascii=False)
