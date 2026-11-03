"""Data models shared across the pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ProductData:
    asin: str
    domain: str = "amazon.in"
    url: str = ""
    title: str = ""
    brand: str = ""
    category: str = ""
    price: str = ""
    rating: str = ""
    reviews: str = ""
    availability: str = ""
    bullets: list[str] = field(default_factory=list)
    attributes: dict[str, str] = field(default_factory=dict)
    variants: list[str] = field(default_factory=list)
    aplus_text: str = ""
    image_urls: list[str] = field(default_factory=list)      # hi-res candidates
    scraped_at: str = ""
    scrape_status: str = "pending"
    scrape_error: str = ""

    # ---------------------------------------------------------- helpers
    def bullet_block(self, limit: int = 5) -> str:
        if not self.bullets:
            return "- (listing has no bullet points; infer nothing that is not visible in the reference images)"
        return "\n".join(f"- {b}" for b in self.bullets[:limit])

    def attribute_block(self, limit: int = 12) -> str:
        if not self.attributes:
            return "- (no specifications available - OMIT measurement text instead of inventing numbers)"
        rows = list(self.attributes.items())[:limit]
        return "\n".join(f"- {k}: {v}" for k, v in rows)

    def variant_note(self) -> str:
        if len(self.variants) < 2:
            return ""
        sample = ", ".join(self.variants[:6])
        return f"VARIANTS ON THE LISTING (show only the ones visible in the reference images): {sample}"

    def prompt_fields(self) -> dict[str, str]:
        return {
            "title": self.title or "the product in the reference images",
            "brand": self.brand or "",
            "category": self.category or "",
            "bullets": self.bullet_block(),
            "attributes": self.attribute_block(),
            "variant_note": self.variant_note(),
            "extra_notes": "",
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductData":
        allowed = cls.__dataclass_fields__.keys()  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in allowed})


@dataclass
class SlotSpec:
    id: str
    order: int
    title: str
    file: str
    intent: str
    template: str
    allowed_text: bool = True

    @classmethod
    def from_yaml(cls, raw: dict[str, Any]) -> "SlotSpec":
        return cls(
            id=raw["id"],
            order=int(raw.get("order", 0)),
            title=raw.get("title", raw["id"]),
            file=raw.get("file", f"{raw['id']}.png"),
            intent=raw.get("intent", ""),
            template=raw.get("template", raw.get("body", "")),
            allowed_text=bool(raw.get("allowed_text", True)),
        )


@dataclass
class JobResult:
    asin: str
    status: str = "pending"          # pending|scraped|generated|failed|partial
    product_title: str = ""
    brand: str = ""
    base_images_found: int = 0
    slots_done: int = 0
    bundle_path: str = ""
    error: str = ""
    updated_at: str = ""
