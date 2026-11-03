"""Prompt gallery sourcing: per-slot prompt BODIES from the compiled prompt library.

This version works WITHOUT NVIDIA NIM:
  1. loads the gallery, excludes utility categories (SYSTEM TASK CODE);
  2. selects a model persona from the gallery's model-variation prompts
     (FEMALE MODEL / MALE MODEL categories) based on the product audience;
  3. builds a candidate pool of scene/pose prompts (MEN, WOMEN, GIRL, S-series)
     appropriate for the audience;
  4. picks the best gallery prompt per slot using simple heuristic rules;
  5. locally adapts each chosen body: swaps garment references to this product,
     injects the selected model persona, normalizes aspect ratio, strips
     reference-lock clauses ("same person as reference", "background identical");
  6. caches the whole plan per ASIN in data/nim/<asin>.gallery.json.

Fully offline, no external API calls.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Config
from .models import ProductData
from .utils import PROJECT_ROOT, ensure_dir, log

# bump when pick/adapt/sanitize logic changes - stale plans must be rebuilt
# v3: fully local (no NIM), model selection from gallery model-variation prompts
# v4: craft story forced to AIIE template (never gallery)
GALLERY_VERSION = 4

# utility / non-image categories that must never feed the generator
DEFAULT_EXCLUDED = {"SYSTEM TASK CODE"}

# gallery categories that contain MODEL VARIATION prompts (persona definitions)
MODEL_VARIATION_CATS = {"FEMALE MODEL", "MALE MODEL"}

# scene/pose categories (bodies for slots)
SCENE_CATS = {"MEN", "WOMEN", "GIRL"}

# preferred scene categories per audience (ordered; pool takes ranked shares)
AUDIENCE_SCENE_CATS: dict[str, list[str]] = {
    "men": ["MALE MODEL", "MEN"],
    "women": ["WOMEN", "FEMALE MODEL", "GIRL"],
    "girls": ["GIRL", "WOMEN", "FEMALE MODEL"],
    "boys": ["GIRL", "MALE MODEL", "MEN"],
    "infants": ["GIRL", "WOMEN", "FEMALE MODEL"],
    "toddlers": ["GIRL", "WOMEN", "FEMALE MODEL"],
    "kids": ["GIRL", "WOMEN", "FEMALE MODEL"],
    "unisex": ["MALE MODEL", "WOMEN", "FEMALE MODEL", "MEN", "GIRL"],
    "other": ["MALE MODEL", "WOMEN", "FEMALE MODEL", "GIRL", "MEN"],
}

# hard slot rules for picking
SLOT_RULES: dict[str, str] = {
    "01_hero_white": "Amazon MAIN image. Only prompts on a PLAIN seamless white or "
                     "neutral studio backdrop qualify; otherwise return null.",
    "02_back_view": "Complete BACK view of the product (Product-first framing).",
    "03_side_view": "Profile / three-quarter angle view showing side drape or depth.",
    "04_craft_story": "STRICT: a FULL-SCENE environment prompt (wide crafted-work / "
                      "lifestyle scene). NEVER a close-up, macro or detail-crop prompt.",
    "05_lifestyle": "Believable aspirational real-world environment (cafe, street, "
                    "garden, home interior...) with the product in natural use.",
    "06_styling_lookbook": "ONE premium styled lookbook/editorial scene.",
    "07_usp_infographic": "A visually rich scene that showcases the product's strongest "
                          "feature WITHOUT on-image text or callouts.",
    "08_product_guide": "This is the ONE slot allowed to be a macro / close-up detail "
                        "prompt (fabric/texture/detail, preferably WITHOUT a face).",
}

SLOT_IDS = ["01_hero_white", "02_back_view", "03_side_view", "04_craft_story",
            "05_lifestyle", "06_styling_lookbook", "07_usp_infographic", "08_product_guide"]


@dataclass(frozen=True)
class GalleryPrompt:
    """One flat prompt entry from the compiled library."""

    category: str
    index: int        # 1-based position inside its category
    title: str
    body: str

    @property
    def key(self) -> str:
        return f"{self.category}#{self.index}"

    def preview(self, limit: int = 220) -> str:
        text = " ".join(self.body.split())
        text = "".join(ch if ch.isprintable() else " " for ch in text)
        return text[:limit]

    def is_model_variation(self) -> bool:
        return self.category in MODEL_VARIATION_CATS

    def looks_closeup(self) -> bool:
        blob = f"{self.title} {self.body}".lower()
        return ("close-up" in blob or "closeup" in blob or "macro" in blob
                or "cropping" in blob or "crop" in blob or "neckline" in blob
                or "detail focus" in blob or "detail shot" in blob or "detail view" in blob)


# ------------------------------------------------------------------ loading
def load(path: Any, excluded: set[str] | None = None) -> list[GalleryPrompt]:
    """Flatten the compiled gallery JSON into prompt entries."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    excluded = excluded or DEFAULT_EXCLUDED
    prompts: list[GalleryPrompt] = []
    for cat, block in data.get("categories", {}).items():
        if cat.upper() in excluded:
            continue
        for i, p in enumerate(block.get("prompts", []), 1):
            body = str(p.get("prompt", "")).strip()
            if not body:
                continue
            prompts.append(GalleryPrompt(cat, i, str(p.get("title", "")).strip(), body))
    return prompts


def _spread(items: list[GalleryPrompt], n: int) -> list[GalleryPrompt]:
    """Evenly sample n items across a (possibly huge) category."""
    if len(items) <= n:
        return list(items)
    idx = sorted({(i * len(items)) // n for i in range(n)})
    return [items[i] for i in idx]


def candidate_pool(prompts: list[GalleryPrompt], preferred: list[str],
                   pool_size: int = 40) -> tuple[list[GalleryPrompt], set[str]]:
    """Return (pool, valid_keys). Ranked categories get descending shares (half,
    quarter, eighth...) before anything else fills the rest ("force everywhere")."""
    by_cat: dict[str, list[GalleryPrompt]] = {}
    for p in prompts:
        by_cat.setdefault(p.category, []).append(p)

    pool: list[GalleryPrompt] = []
    seen: set[int] = set()
    ranked = [c for c in preferred if by_cat.get(c)]
    for i, cat in enumerate(ranked):
        budget = pool_size - len(pool)
        if budget <= 0:
            break
        share = budget if i == len(ranked) - 1 else max(3, budget // 2)
        take = min(share, len(by_cat[cat]), budget)
        for p in _spread(by_cat[cat], take):
            if id(p) not in seen:
                seen.add(id(p))
                pool.append(p)
    for p in prompts:                     # fill leftovers with everything else
        if len(pool) >= pool_size:
            break
        if id(p) not in seen:
            seen.add(id(p))
            pool.append(p)
    return pool[:pool_size], {p.key for p in pool}


# ------------------------------------------------------------------ model selection
def select_model_persona(prompts: list[GalleryPrompt], audience: str) -> str:
    """Pick one model-variation prompt from the gallery matching the audience.

    Returns the model description text to use as the consistent persona.
    """
    audience_l = audience.lower()
    # map audience -> which model-variation category + keywords to match
    if audience_l in ("women", "girls", "infants", "toddlers", "kids"):
        cat = "FEMALE MODEL"
        keywords = {
            "women": ["indian", "south asian", "ethnic", "modern wear", "saree"],
            "girls": ["indian", "child", "girl", "young"],
            "infants": ["infant", "baby", "child"],
            "toddlers": ["toddler", "child", "young"],
            "kids": ["child", "girl", "young"],
        }.get(audience_l, ["indian", "female"])
    elif audience_l in ("men", "boys"):
        cat = "MALE MODEL"
        keywords = ["indian", "south asian", "male", "men"]
    else:
        cat = "FEMALE MODEL"
        keywords = ["indian", "female", "south asian"]

    model_prompts = [p for p in prompts if p.category == cat]
    if not model_prompts:
        # fallback generic
        return ("professional Indian / South Asian commercial catalogue model, adult, "
                "natural appearance, no dramatic fashion pose; the product is always the hero")

    # score each model variation by keyword matches
    best = None
    best_score = -1
    for mp in model_prompts:
        text = f"{mp.title} {mp.body}".lower()
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best = mp

    if best is None:
        best = model_prompts[0]

    # extract a clean persona line from the model variation prompt
    body = best.body
    # take first 2-3 sentences that describe the model
    sentences = re.split(r"(?<=[.!?])\s+", body)
    persona_parts = []
    for s in sentences:
        low = s.lower()
        if any(w in low for w in ["model", "man", "woman", "girl", "boy", "person",
                                   "hair", "skin", "face", "eyes", "expression",
                                   "age", "build", "physique", "stature"]):
            persona_parts.append(s.strip())
        if len(persona_parts) >= 3:
            break
    if not persona_parts:
        persona_parts = [body[:300]]

    persona = " ".join(persona_parts)
    # clean up
    persona = re.sub(r"^\s*[\w\s]+\s*:", "", persona)  # "Model Variation:" prefix
    persona = re.sub(r"[\u200b\u200c\u200d\u200e\u200f\u202a-\u202e\u2060\u2061\ufeff\u00ad]", "", persona)
    persona = re.sub(r"\s+", " ", persona).strip(" .,;:")
    return persona


# ------------------------------------------------------------------ sanitizer
_REWRITE_PATTERNS: list[tuple[str, str]] = [
    (r"(ensure|maintain)\s+strict\s+facial\s+consistency\s+with\s+"
     r"(a\s+|the\s+)?(prior|previous|the)\s*(reference|photo|image)\s*,?\s*", ""),
    (r"facial\s+consistency\s+with\s+(a\s+|the\s+)?(prior|previous)[^,.;)]*,?\s*", ""),
    (r"(ensure|maintain)\s+strict\s+facial\s+consistency\s*", ""),
    (r"\bthe\s+same\s+(young\s+|old\s+|elderly\s+|attractive\s+|beautiful\s+|"
     r"handsome\s+|stunning\s+|gen-z\s+)?(man|woman|male\s+model|female\s+model)\b",
     "the freshly cast session model"),
    (r"\bsame\s+(young\s+|attractive\s+)?(man|woman)\b", "freshly cast session model"),
    (r"\bsame\s+male\s+model\b", "the freshly cast session model"),
    (r"\bsame\s+female\s+model\b", "the freshly cast session model"),
]

_KILL_PATTERNS = [
    r"facial consistency",
    r"\bbase (her|his)\b",
    r"\bbased (closely\s+)?on (the\s+)?(attached\s+)?reference (photo|image)",
    r"maintain 100\s*% integrity of the background",
    r"\bintegrity of the background\b",
    r"background (must|should|has to)\s+(remain|stay|be)\s+(identical|same|unchanged)",
    r"do not (change|modify)[^.]{0,90}background",
    r"\bbackground\s*:\s*identical",
    r"\bidentical environment\b",
    r"\bsame background\b",
    r"change the background to be the same",
    r"\bbackground[^.]{0,80}\bidentical\b",
    r"\bkeep(ing)? the background\b",
    r"\bmodel identity\s*:",
    r"(?:model|man|woman)[^.]{0,140}\bage\s+\d+",
    r"(?:model|man|woman)[^.]{0,140}\b(?:years|yrs)\s+old\b",
    r"(?:model|man|woman)[^.]{0,140}\by/o\b",
    r"\b(?:stunningly\s+)?(?:beautiful|handsome|attractive|gorgeous)\s+"
    r"(?:indian|brazilian|scandinavian|east\s+asian|latina?|hispanic|russian|"
    r"european|middle\s+eastern|african\s+american|italian|arab|korean|"
    r"japanese|chinese|filipino)\s+(?:female|male)\s+(?:model|girl|boy)\b",
]

_SIZE_FIX = re.compile(r"1600\s*[xX×]\s*2100", re.IGNORECASE)


def sanitize(text: str, model_line: str = "") -> str:
    """Normalize sizes, de-personalize in place, drop shoot-lock sentences."""
    txt = _SIZE_FIX.sub("1600x1920", text or "")

    # 1) de-personalize INSIDE sentences (keep the scene composition)
    for pattern, repl in _REWRITE_PATTERNS:
        txt = re.sub(pattern, repl, txt, flags=re.IGNORECASE)

    # 2) mojibake repair (best effort, never aborts)
    txt = txt.replace("Ã©", "é")
    if "Ã" in txt or "â€" in txt:
        try:
            repaired = txt.encode("cp1252", errors="ignore").decode("utf-8", errors="ignore")
            if repaired.strip() and ("Ã" not in repaired):
                txt = repaired
        except Exception:  # noqa: BLE001
            pass

    # 3) drop sentences that are pure identity / background locks
    kills = [re.compile(p, re.IGNORECASE) for p in _KILL_PATTERNS]
    kept: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", txt):
        low = sentence.lower()
        if any(k.search(low) for k in kills):
            continue
        kept.append(sentence.strip())
    out = " ".join(kept)
    out = re.sub(r"\(\s*\)\s*,", ", ", out)
    out = re.sub(r"\(\s*\)", "", out)
    out = re.sub(r"\s+,\s*", ", ", out).strip()
    out = re.sub(r"\s+", " ", out).strip()
    out = out.strip("`\"' ").strip()
    # strip invisible marks
    out = re.sub(r"[\u200b\u200c\u200d\u200e\u200f\u202a-\u202e\u2060\u2061\ufeff\u00ad]", "", out)
    if model_line:
        out = (f"MODEL DIRECTION (session persona, LOCKED): {model_line} "
               f"The product stays the hero. {out}").strip()
    return out


# ------------------------------------------------------------------ local adapter
_GARMENT_WORDS = [
    "apparel", "garment", "shirt", "t-shirt", "tshirt", "kurta", "kurti", "saree",
    "lehenga", "jeans", "jacket", "hoodie", "dress", "ethnic", "salwar", "palazzo",
    "top", "blouse", "legging", "jogger", "cargo", "sherwani", "nightwear", "bra",
    "innerwear", "sock", "trouser", "pant", "anarkali", "chikankari", "co-ord",
    "co ord", "coordinated", "set", "suit", "ensemble", "outfit", "wear", "clothing",
    "fashion", "attire", "robe", "gown", "frock", "skirt", "shorts", "pants",
]

def _product_garment_name(product: ProductData) -> str:
    """Extract a concise garment description from the product title."""
    title = (product.title or "the product").lower()
    # keep first ~8 words, strip brand/ASIN noise
    words = title.split()
    # remove common noise words
    noise = {"with", "and", "or", "for", "the", "a", "an", "in", "of", "by", "|"}
    clean = [w for w in words if w not in noise and not w.startswith("b0")]
    return " ".join(clean[:10])


def adapt_body(body: str, product: ProductData, model_line: str, slot_id: str) -> str:
    """Local adaptation: replace garment refs, inject model, strip locks."""
    garment = _product_garment_name(product)

    # replace generic garment words with this product's garment
    txt = body
    for gw in _GARMENT_WORDS:
        txt = re.sub(rf"\b{gw}\b", garment, txt, flags=re.IGNORECASE)

    # sanitize (strips reference locks, fixes size, injects model line)
    txt = sanitize(txt, model_line)

    # slot-specific tweaks
    if slot_id == "01_hero_white":
        # ensure pure white background language
        if "white" not in txt.lower() and "seamless" not in txt.lower():
            txt = txt.replace("studio backdrop", "pure white seamless studio backdrop")
            txt = txt.replace("neutral background", "pure white seamless background")
    elif slot_id == "04_craft_story":
        # reinforce no-close-up
        if "close-up" in txt.lower() or "macro" in txt.lower():
            txt = re.sub(r"(?i)(close-up|macro|crop|detail shot)[^.]*\.", "", txt)

    return txt


# ------------------------------------------------------------------ slot picker (heuristic, no NIM)
def pick_slot_prompts(product: ProductData, casting: dict[str, Any],
                      scene_pool: list[GalleryPrompt], valid_keys: set[str]) -> dict[str, GalleryPrompt | None]:
    """Heuristic slot picking from the scene pool (no NIM call)."""
    audience = casting.get("audience", "Unisex").lower()
    model_required = casting.get("model_required", False)

    # score each scene prompt against each slot rule
    picks: dict[str, GalleryPrompt | None] = {sid: None for sid in SLOT_IDS}
    used_keys: set[str] = set()

    # priority order: slots with strictest requirements first
    slot_priority = [
        "01_hero_white",
        "04_craft_story",
        "08_product_guide",
        "02_back_view",
        "03_side_view",
        "05_lifestyle",
        "06_styling_lookbook",
        "07_usp_infographic",
    ]

    for sid in slot_priority:
        rule = SLOT_RULES[sid]
        best = None
        best_score = -1

        for gp in scene_pool:
            if gp.key in used_keys:
                continue
            if gp.key not in valid_keys:
                continue

            score = 0
            blob = f"{gp.title} {gp.body}".lower()

            # rule-based scoring
            if sid == "01_hero_white":
                if any(w in blob for w in ["white", "seamless", "plain background", "studio backdrop", "clean background"]):
                    score += 10
            elif sid == "02_back_view":
                if any(w in blob for w in ["back view", "rear", "back angle", "from behind", "back pose"]):
                    score += 10
            elif sid == "03_side_view":
                if any(w in blob for w in ["side", "profile", "three-quarter", "45", "angle"]):
                    score += 10
            elif sid == "04_craft_story":
                if gp.looks_closeup():
                    score -= 50  # hard penalty
                if any(w in blob for w in ["workshop", "artisan", "craft", "loom", "weaving", "studio", "seated", "sofa", "environment", "scene", "background"]):
                    score += 8
            elif sid == "05_lifestyle":
                if any(w in blob for w in ["cafe", "street", "garden", "home", "interior", "outdoor", "walking", "lifestyle", "urban", "park", "seated", "sofa", "relaxed"]):
                    score += 8
            elif sid == "06_styling_lookbook":
                if any(w in blob for w in ["styling", "lookbook", "editorial", "fashion", "premium", "styled", "elegant"]):
                    score += 8
            elif sid == "07_usp_infographic":
                if any(w in blob for w in ["detail", "feature", "texture", "fabric", "embroidery", "quality", "close", "macro"]):
                    score += 5
            elif sid == "08_product_guide":
                if gp.looks_closeup():
                    score += 10  # this is the ONE allowed macro slot
                if any(w in blob for w in ["detail", "fabric", "texture", "neckline", "macro", "close-up", "closeup"]):
                    score += 5

            # prefer model-appropriate prompts
            if model_required:
                if "model" in blob or "woman" in blob or "man" in blob or "girl" in blob:
                    score += 3
            else:
                if "model" not in blob and "person" not in blob and "woman" not in blob and "man" not in blob:
                    score += 3

            # small tie-break: earlier in pool (more preferred category)
            score += (len(scene_pool) - scene_pool.index(gp)) * 0.01

            if score > best_score:
                best_score = score
                best = gp

        if best is not None and best_score > -10:
            picks[sid] = best
            used_keys.add(best.key)

    return picks


# ------------------------------------------------------------------ planning
def _cache_path(product: ProductData) -> Path:
    return ensure_dir(PROJECT_ROOT / "data" / "nim") / f"{product.asin}.gallery.json"


def _cache_valid(cache: dict[str, Any], source_md5: str) -> bool:
    return (cache.get("gallery_version") == GALLERY_VERSION
            and cache.get("source_md5") == source_md5
            and isinstance(cache.get("bodies"), dict))


def gallery_bodies(product: ProductData, casting: dict[str, Any], cfg: Config) -> dict[str, dict[str, str]]:
    """Return {slot_id: {body, title, category, ref}} or {} -> keep AIIE templates."""
    if not cfg.get("gallery.enabled", True):
        return {}

    path = cfg.resolve(cfg.get("gallery.path", "DOCUMENTATION/all_prompts_compilation.json"))
    if not path.exists():
        log.warning("gallery: file %s not found - keeping AIIE templates", path)
        return {}

    excluded = {str(c).upper() for c in cfg.get("gallery.exclude_categories", [])} or DEFAULT_EXCLUDED
    all_prompts = load(path, excluded)
    if not all_prompts:
        log.warning("gallery: no usable prompts in %s", path)
        return {}

    cache_path = _cache_path(product)
    source_md5 = hashlib.md5(path.read_bytes()).hexdigest()
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            if _cache_valid(cache, source_md5):
                log.info("gallery: using cached plan for %s (%d slots)", product.asin, len(cache["bodies"]))
                return _validated(cache["bodies"])
        except Exception:  # noqa: BLE001
            pass

    # 1) select model persona from gallery's model-variation prompts
    audience = str(casting.get("audience", "Unisex")).lower()
    model_line = select_model_persona(all_prompts, audience)
    log.info("gallery: selected model persona for %s: %s...", product.asin, model_line[:80])

    # 2) build scene candidate pool (excludes model-variation cats)
    scene_prompts = [p for p in all_prompts if p.category not in MODEL_VARIATION_CATS]
    preferred = AUDIENCE_SCENE_CATS.get(audience, AUDIENCE_SCENE_CATS["other"])
    pool, valid_keys = candidate_pool(scene_prompts, preferred,
                                      int(cfg.get("gallery.pool_size", 40)))

    # 3) heuristic slot picking
    picks = pick_slot_prompts(product, casting, pool, valid_keys)

    # 4) adapt each chosen body
    bodies: dict[str, dict[str, str]] = {}
    detail_slot = str(cfg.get("gallery.detail_closeup_slot", "08_product_guide"))

    # craft story MUST always use the AIIE template (never gallery) to preserve
    # the "NO close-up / wide crafted-work scene" constraint
    if "04_craft_story" in picks:
        log.info("gallery: 04_craft_story forced to AIIE template (no gallery body)")
        picks["04_craft_story"] = None

    # enforce: at most one close-up overall, must be detail_slot if present
    closeup_slots = [sid for sid, gp in picks.items() if gp and gp.looks_closeup()]
    if len(closeup_slots) > 1:
        keep = detail_slot if detail_slot in closeup_slots else closeup_slots[0]
        for sid in closeup_slots:
            if sid != keep:
                log.info("gallery: dropping extra macro pick %s for %s", picks[sid].key, sid)
                picks[sid] = None

    for sid, gp in picks.items():
        if gp is None:
            continue
        adapted = adapt_body(gp.body, product, model_line, sid)
        if len(adapted) < 80 or len(adapted) > 6000:
            continue
        bodies[sid] = {
            "body": adapted,
            "title": gp.title,
            "category": gp.category,
            "ref": gp.key,
        }

    if bodies:
        cache_path.write_text(json.dumps({
            "gallery_version": GALLERY_VERSION,
            "source_md5": source_md5,
            "model_line": model_line,
            "bodies": bodies,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("gallery: %d/%d slots re-sourced for %s", len(bodies), len(SLOT_IDS), product.asin)
    return _validated(bodies)


def _validated(bodies: dict[str, Any]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for sid, item in (bodies or {}).items():
        if sid not in SLOT_IDS or not isinstance(item, dict):
            continue
        text = str(item.get("body", "")).strip()
        if len(text) < 80 or len(text) > 6000:
            continue
        out[sid] = {
            "body": text,
            "title": str(item.get("title", "")),
            "category": str(item.get("category", "")),
            "ref": str(item.get("ref", "")),
        }
    return out