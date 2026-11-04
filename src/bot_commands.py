"""OpenMaus bot command handlers for the ASIN -> 8-image pipeline.

Each function takes a Config and returns a plain dict result suitable for
sending back as a bot message. No network/Playwright here except where the
underlying pipeline needs it (cmd_generate delegates to Pipeline).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import Config
from .pipeline import Pipeline
from .utils import read_json
from .wm_clean import clean_existing


def cmd_status(asin: str, cfg: Config) -> dict[str, Any]:
    """Return a human-readable status summary for one ASIN bundle."""
    adir = Path(cfg.asin_dir(asin))
    manifest = read_json(adir / "manifest.json", {})
    if not manifest:
        return {"asin": asin, "status": "not_found", "error": "no manifest for this ASIN"}

    slots = manifest.get("slots", {})
    ok = sum(1 for s in slots.values() if s.get("status") == "ok")
    failed = sum(1 for s in slots.values() if s.get("status") == "failed")
    total = len(slots)

    stage = manifest.get("stages", {}).get("generate", {})
    bundle_status = stage.get("status", "unknown")

    if total == 0:
        status = "not_started"
    elif failed == total:
        status = "failed"
    elif ok == total:
        status = "complete"
    elif failed > 0:
        status = "partial"
    else:
        status = "in_progress"

    product = manifest.get("product", {})
    return {
        "asin": asin,
        "status": status,
        "bundle_status": bundle_status,
        "slots_done": f"{ok}/{total}" if total else "0/0",
        "slots_ok": ok,
        "slots_failed": failed,
        "title": product.get("title", ""),
        "brand": product.get("brand", ""),
        "bundle_path": str(adir),
        "slots": {k: {"status": v.get("status"), "attempts": v.get("attempts", 1)}
                  for k, v in slots.items()},
    }


def cmd_generate(asins: list[str], cfg: Config, force: bool = False,
                 notes: str = "") -> dict[str, Any]:
    """Run the generate stage for a list of ASINs."""
    pipe = Pipeline(cfg, dry_run=False, force=force)
    return pipe.generate(asins, extra_notes=notes)


def cmd_clean(asin: str, cfg: Config) -> dict[str, int]:
    """Re-run watermark cleanup on an already-generated bundle."""
    adir = Path(cfg.asin_dir(asin))
    gen_dir = adir / "generated"
    if not gen_dir.exists():
        return {}
    return clean_existing(adir, cfg)
