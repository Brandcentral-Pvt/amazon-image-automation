"""Build the 8 Amazon-compliant Gemini prompts from product data + slot specs.

Two prompt packs (out of the box):
  * prompts/aiie_studio.yaml  - AIIE(TM) Studio 8P master (preferred; apparel-aware,
    uses NVIDIA NIM for dynamic model casting + per-slot direction, one master
    message per ASIN batch)
  * prompts/slots.yaml        - legacy generic 8-slot pack (fallback)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from . import prompt_gallery
from .config import Config
from .models import ProductData, SlotSpec
from .nim_client import local_casting
from .utils import log, write_json

_PLACEHOLDER = re.compile(r"\{(\w+)\}")


# ---------------------------------------------------------------- render
def _render(template: str, fields: dict[str, Any]) -> str:
    """Substitute only known {placeholders} - leaves any other braces untouched."""
    return _PLACEHOLDER.sub(lambda m: str(fields.get(m.group(1), m.group(0))), template)


# ---------------------------------------------------------------- loaders
def load_slots(cfg: Config) -> tuple[list[SlotSpec], str]:
    path = cfg.resolve(cfg.get("prompts.file", "prompts/slots.yaml"))
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    slots = sorted(
        (SlotSpec.from_yaml(s) for s in raw.get("slots", [])),
        key=lambda s: s.order,
    )
    if len(slots) != 8:
        log.warning("expected 8 slots, found %d", len(slots))
    return slots, (raw.get("global_rules") or "").strip()


def load_studio(cfg: Config) -> tuple[list[SlotSpec], str] | None:
    """Load the AIIE Studio pack; returns (slots, master_rules) or None."""
    path = cfg.resolve(cfg.get("studio.templates", "prompts/aiie_studio.yaml"))
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    slots = sorted((SlotSpec.from_yaml(s) for s in raw.get("slots", [])),
                   key=lambda s: s.order)
    if len(slots) != 8:
        log.warning("AIIE studio: expected 8 slots, found %d", len(slots))
    return slots, (raw.get("master_rules") or "").strip()


# ------------------------------------------------------------- casting bridge
def resolve_casting(product: ProductData, cfg: Config, extra_notes: str) -> dict[str, Any]:
    """Local casting only (NIM disabled)."""
    return local_casting(product)


# ------------------------------------------------------------- master message
def _studio_geometry(cfg: Config) -> tuple[str, int, int]:
    """(aspect string, panel width, panel height) from config - always defined."""
    aspect = (str(cfg.get("studio.panel_aspect", "3:4")).strip() or "3:4")
    width = int(cfg.get("studio.panel_width", 1600))
    height = int(cfg.get("studio.panel_height", 1920))
    return aspect, width, height


def build_master_message(rules: str, product: ProductData, casting: dict[str, Any],
                         cfg: Config) -> str:
    """Opening message of the ASIN batch chat: AIIE rules + dynamic casting."""
    aspect, size_w, size_h = _studio_geometry(cfg)
    audience = casting.get("audience", "Unisex")
    age = casting.get("age_group", "")
    segment = casting.get("fashion_segment", "n/a")
    cat = casting.get("product_category", "other")
    audience_block = (
        f"{audience}"
        + (f" / {age}" if age else "")
        + f" | product category: {cat} | segment: {segment}. This classification is "
          "LOCKED for all 8 images - never change it during generation."
    )
    if casting.get("model_required", False):
        model_block = (
            "FRESH CASTING (STRICT): cast a NEW model for this listing - do NOT reuse or "
            "imitate any person, face, pose, hairstyle, makeup, accessories or styling "
            "that appears in the uploaded base images (those are PRODUCT ground truth "
            "only). Cast exactly this NEW persona: "
            f"{casting.get('model_card', 'professional commercial catalogue model')}. "
            "This same NEW model must remain IDENTICAL in every image featuring a person "
            "(face, hair, skin tone, body type, height, makeup, expression, styling, "
            "accessories). "
            f"Background family: {casting.get('background_family', 'premium commercial')}. "
            "The product stays the hero in every frame."
        )
    else:
        model_block = (
            "HARD-GOODS MODE: no human model anywhere. Product-only commercial frames; "
            f"staging family: {casting.get('background_family', 'clean premium neutral')}."
        )
    panel_spec = (
        f"a vertical {aspect} PORTRAIT panel (portrait orientation - never landscape, "
        f"never square), designed for final export at {size_w} x {size_h} pixels"
    )
    fields: dict[str, Any] = {
        "audience_block": audience_block,
        "model_block": model_block,
        "panel_spec": panel_spec,
        **product.prompt_fields(),
    }
    return _render(rules, fields)


# ------------------------------------------------------------- slot prompts
def _ground_truth(product: ProductData) -> str:
    bullets = "\n".join(f"    - {b[:160]}" for b in product.bullets[:5]) or "    - (none beyond the images)"
    attrs = "\n".join(f"    - {k}: {v}" for k, v in list(product.attributes.items())[:8]) or "    - (only what the images show)"
    return (
        f"  PRODUCT (SINGLE SOURCE OF TRUTH): {product.title or 'the product in the references'}\n"
        f"  BRAND: {product.brand or 'as visible on the product'}\n"
        f"  LISTING CATEGORY: {product.category or 'infer only from the images'}\n"
        f"  KEY LISTING POINTS:\n{bullets}\n"
        f"  LISTING SPECIFICATIONS:\n{attrs}"
    )


def build_studio_prompt(slot: SlotSpec, product: ProductData,
                        casting: dict[str, Any], cfg: Config,
                        gallery_item: dict[str, str] | None = None) -> str:
    """One standalone AIIE panel prompt, consistent-safe inside the batch chat.

    When `gallery_item` is present the panel BODY comes from the user's prompt
    gallery (already NIM-adapted + sanitized) and only the compliance wrapper
    (ground truth, references, identity lock, output spec) is AIIE-issued.
    """
    aspect, size_w, size_h = _studio_geometry(cfg)
    direction = (casting.get("slot_direction") or {}).get(slot.id, "")
    model_line = (
        casting.get("model_card", "")
        if casting.get("model_required", False)
        else "No human model: product-only frame."
    )

    body = slot.template.strip()
    if gallery_item:
        body = (
            "DETAILED BRIEF (professional prompt library, adapted for this listing):\n"
            f"{gallery_item['body']}"
        )

    parts = [
        f"[AIIE PANEL {slot.order}/8 OF 8 - {slot.title.upper()}]",
        "Generate ONLY this one image as the next reply in THIS chat. It must be a "
        "standalone premium Amazon listing panel that belongs to the same session as "
        "everything generated so far in this chat.",
        _ground_truth(product),
        body,
        "REFERENCE IMAGES: the product photos already attached in this chat are the "
        "real photos of the live Amazon listing - treat them as ground truth for "
        "shape, colour, fabric, print, construction, label text and proportions. "
        "If a detail is not visible there, do not invent it.",
    ]
    if direction:
        parts.append(f"AIIE CASTING DIRECTION FOR THIS PANEL: {direction}")
    parts.append(
        "IDENTITY & CONSISTENCY LOCK (session-wide):\n"
        f"  MODEL IDENTITY: {model_line}\n"
        "  FRESH CASTING: the attached base images are PRODUCT ground truth only - "
        "NEVER copy, imitate or re-render the face, identity, pose, hairstyle, makeup "
        "or styling of any person visible in them. The person in this panel (if any) "
        "is the freshly cast session model from the master message, identical across "
        "all panels.\n"
        "  The product must be IDENTICAL to the reference images and to every panel "
        "already generated in this chat. Same lighting style, colour grading and "
        "visual identity. 100% product accuracy: do not invent, redesign or exaggerate "
        "any feature; if a detail is not visible in the references, omit it."
    )
    parts.append(
        "OUTPUT (LOCKED): exactly ONE standalone image. ASPECT RATIO: "
        f"{aspect} PORTRAIT (portrait orientation - never landscape, never square), "
        f"final export {size_w}x{size_h}px, PNG-quality, ultra-HD, no borders, "
        "no watermark, ~3% safe margin inside the panel. Text allowed: "
        + ("yes - only the specific text described above." if slot.allowed_text
           else "NO text or lettering anywhere in the image.")
    )
    return "\n\n".join(p for p in parts if p)


def build_prompt(slot: SlotSpec, product: ProductData, global_rules: str, cfg: Config) -> str:
    """Legacy (slots.yaml) single-shot prompt - 1:1 square, self-contained."""
    size = int(cfg.get("image_spec.size", 3000))
    fields: dict[str, Any] = {**product.prompt_fields(), "size": size}

    body = _render(slot.template, fields).strip()
    refs = (
        "REFERENCE IMAGES: the attached images are the real product photos from the live "
        "Amazon listing. Treat them as ground truth for shape, colour, material, label text "
        "and proportions. If a detail is not visible in the references, do not invent it."
    )

    parts = [
        f"[SLOT {slot.order}/8 - {slot.title.upper()}]",
        body,
        refs,
        _render(global_rules, fields),
        f"OUTPUT: one single image, square 1:1, {size}x{size}px, sRGB, no borders, "
        f"no collage of multiple panels unless the brief explicitly asks for a group shot. "
        f"Text allowed: {'yes, only as described above' if slot.allowed_text else 'NO text or lettering anywhere in the image'}.",
    ]
    return "\n\n".join(p for p in parts if p)


# ---------------------------------------------------------------- bundle
def build_bundle(
    product: ProductData,
    asin_dir: Path,
    cfg: Config,
    extra_notes: str = "",
) -> tuple[list[dict[str, Any]], str]:
    """Return (prompt bundle, master message) and persist next to the product.

    The master message is the AIIE session-opener for the shared batch chat
    (empty string for the legacy pack / when the feature is disabled).
    """
    studio = load_studio(cfg)
    master = ""
    gallery_used = False
    if studio is not None:
        slots, rules = studio
        casting = resolve_casting(product, cfg, extra_notes)
        master = build_master_message(rules, product, casting, cfg)
        gallery_items: dict[str, dict[str, str]] = {}
        if cfg.get("gallery.enabled", True):
            gallery_items = prompt_gallery.gallery_bodies(product, casting, cfg)
            if gallery_items:
                log.info("%s: %d of 8 panel bodies sourced from the prompt gallery",
                         product.asin, len(gallery_items))

        def prompt_fn(slot: SlotSpec, _casting: dict[str, Any],
                      _gi: dict[str, dict[str, str]]) -> str:
            return build_studio_prompt(slot, product, _casting, cfg,
                                       gallery_item=_gi.get(slot.id))
    else:
        slots, global_rules = load_slots(cfg)
        casting = {}

    bundle: list[dict[str, Any]] = []
    for slot in slots:
        if studio is not None:
            gi = gallery_items.get(slot.id)
            prompt = prompt_fn(slot, casting, gallery_items)
            item = {
                "slot_id": slot.id,
                "order": slot.order,
                "title": slot.title,
                "intent": slot.intent,
                "allowed_text": slot.allowed_text,
                "target_file": slot.file,
                "prompt": prompt,
                "source": "gallery" if gi else "aiie",
                "gallery_ref": (gi or {}).get("ref", ""),
            }
            if gi:
                item["gallery_title"] = gi.get("title", "")
                gallery_used = True
        else:
            prompt = build_prompt(slot, product, global_rules, cfg)
            item = {
                "slot_id": slot.id,
                "order": slot.order,
                "title": slot.title,
                "intent": slot.intent,
                "allowed_text": slot.allowed_text,
                "target_file": slot.file,
                "prompt": prompt,
                "source": "slots",
                "gallery_ref": "",
            }
        prompt = item["prompt"]
        if extra_notes:
            prompt += f"\n\nADDITIONAL BRIEF FROM THE SELLER:\n{extra_notes.strip()}"
            item["prompt"] = prompt
        bundle.append(item)

    prompts_dir = asin_dir / "prompts"
    pack = ("aiie_studio+gallery" if (studio and gallery_used)
            else ("aiie_studio" if studio else "slots"))
    write_json(prompts_dir / "prompts.json",
               {"asin": product.asin, "pack": pack,
                "master": master, "slots": bundle})
    (prompts_dir / "prompts.md").write_text(
        _render_markdown(product, bundle, master), encoding="utf-8")
    log.info("%s: %d prompts written to %s (pack: %s)", product.asin, len(bundle),
             prompts_dir, pack)
    return bundle, master


def _render_markdown(product: ProductData, bundle: list[dict[str, Any]],
                     master: str = "") -> str:
    lines = [
        f"# Image bundle prompts - {product.asin}",
        "",
        f"**{product.title}**",
        f"Brand: {product.brand}  |  Category: {product.category}  |  Price: {product.price}",
        f"Source: {product.url}",
        "",
        "---",
    ]
    if master:
        lines += ["", "## SESSION MASTER MESSAGE (sent once per batch chat)", "",
                  "```text", master, "```"]
    lines += ["", "---"]
    for item in bundle:
        lines += [
            f"## {item['order']}. {item['title']}",
            f"*Target file:* `{item['target_file']}`  |  *Text:* {'allowed' if item['allowed_text'] else 'none'}",
            "",
            f"_{item['intent']}_",
            "",
            "```text",
            item["prompt"],
            "```",
            "",
        ]
    return "\n".join(lines)
