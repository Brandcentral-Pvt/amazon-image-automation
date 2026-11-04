"""Orchestration: ASIN -> scrape -> base images -> prompts -> 8 images -> manifest."""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from .config import Config
from .downloader import download_base_images
from .models import ProductData
from .prompts import build_bundle
from .tracker import build_tracker
from .utils import ensure_dir, human_delay, log, read_json, rel, write_json
from .wm_clean import clean_generated_image, sweep_generated


class Pipeline:
    def __init__(self, cfg: Config, dry_run: bool = False, force: bool = False):
        self.cfg = cfg
        self.dry_run = dry_run
        self.force = force
        self.tracker = build_tracker(cfg)

    # ------------------------------------------------------------- helpers
    def asin_dir(self, asin: str) -> Path:
        return ensure_dir(self.cfg.asin_dir(asin))

    def manifest_path(self, asin: str) -> Path:
        return self.asin_dir(asin) / "manifest.json"

    def load_manifest(self, asin: str) -> dict[str, Any]:
        return read_json(self.manifest_path(asin), {}) or {
            "asin": asin,
            "created_at": dt.datetime.now().isoformat(timespec="seconds"),
            "stages": {},
            "slots": {},
        }

    def save_manifest(self, asin: str, manifest: dict[str, Any]) -> None:
        manifest["updated_at"] = dt.datetime.now().isoformat(timespec="seconds")
        write_json(self.manifest_path(asin), manifest)

    def report(self, asin: str, product: ProductData | None, manifest: dict[str, Any],
               status: str, error: str = "") -> None:
        slots_done = sum(1 for s in manifest.get("slots", {}).values() if s.get("status") == "ok")
        job = {
            "asin": asin,
            "status": status,
            "product_title": (product.title if product else manifest.get("product", {}).get("title", ""))[:250],
            "brand": (product.brand if product else manifest.get("product", {}).get("brand", "")),
            "base_images_found": len(list((self.asin_dir(asin) / "base_images").glob("*.[jJpP][pnN]*")))
            if (self.asin_dir(asin) / "base_images").exists() else 0,
            "slots_done": f"{slots_done}/8",
            "bundle_path": rel(self.asin_dir(asin)),
            "error": error[:400],
            "updated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        try:
            self.tracker.upsert(job)
        except Exception as exc:  # noqa: BLE001
            log.warning("tracker update failed for %s: %s", asin, exc)

    # ------------------------------------------------------------- stage 1
    def scrape(self, asins: list[str]) -> dict[str, ProductData]:
        from .scraper import scrape_many

        log.info("=== STAGE 1: scraping %d ASIN(s) ===", len(asins))
        products = scrape_many(asins, self.cfg)

        for asin, product in products.items():
            adir = self.asin_dir(asin)
            write_json(adir / "product.json", product.to_dict())
            manifest = self.load_manifest(asin)
            manifest["product"] = product.to_dict()
            manifest["stages"]["scrape"] = {
                "status": product.scrape_status,
                "at": dt.datetime.now().isoformat(timespec="seconds"),
                "error": product.scrape_error,
            }
            if product.scrape_status == "ok":
                bases = download_base_images(product, adir, self.cfg)
                manifest["stages"]["base_images"] = {
                    "status": "ok" if bases else "empty",
                    "count": len(bases),
                    "files": [rel(p, adir) for p in bases],
                }
                self.save_manifest(asin, manifest)
                self.report(asin, product, manifest, "scraped")
            else:
                self.save_manifest(asin, manifest)
                self.report(asin, product, manifest, "failed", product.scrape_error)
        return products

    # ------------------------------------------------------------- stage 2
    def generate(self, asins: list[str], only_slots: list[str] | None = None,
                 extra_notes: str = "") -> dict[str, Any]:
        log.info("=== STAGE 2: generating image bundles for %d ASIN(s) ===", len(asins))

        prepared: dict[str, tuple[ProductData, list[dict], list[Path], str]] = {}
        for asin in asins:
            adir = self.asin_dir(asin)
            pdata = read_json(adir / "product.json")
            if not pdata:
                log.error("%s: no product.json - run scrape first", asin)
                self.report(asin, None, self.load_manifest(asin), "failed", "missing product.json")
                continue
            product = ProductData.from_dict(pdata)
            if product.scrape_status != "ok":
                log.error("%s: scrape was not successful - skipping", asin)
                continue
            bundle, master = build_bundle(product, adir, self.cfg, extra_notes=extra_notes)
            refs = sorted((adir / "base_images").glob("*.*")) if (adir / "base_images").exists() else []
            if not refs:
                log.warning("%s: no base images found; prompts will run text-only", asin)
            prepared[asin] = (product, bundle, refs, master)

        if not prepared:
            return {"ok": 0, "failed": len(asins)}

        if self.dry_run:
            for asin, (_p, bundle, _r, _m) in prepared.items():
                log.info("%s: [dry-run] %d prompts prepared", asin, len(bundle))
            return {"ok": len(prepared), "failed": 0, "dry_run": True}

        provider = str(self.cfg.get("generation.provider", "gemini")).strip().lower()
        if provider == "chatgpt":
            from .chatgpt_web import ChatGPTWeb as Generator
        elif provider == "gemini":
            from .gemini_web import GeminiWeb as Generator
        else:
            raise ValueError(f"unsupported image generation provider: {provider}")

        stats = {"ok": 0, "failed": 0, "slots_ok": 0, "slots_failed": 0}
        headless = self.cfg.get("browser.headless", True)
        with Generator(self.cfg, headless=headless) as client:
            for asin, (product, bundle, refs, master) in prepared.items():
                result = self._generate_one(client, asin, product, bundle, refs, master)
                for key in stats:
                    stats[key] += result.get(key, 0)
                human_delay([5, 10], "between asins")
        return stats

    def _generate_one(self, client, asin: str, product: ProductData,
                      bundle: list[dict], refs: list[Path], master: str = ""
                      ) -> dict[str, int]:
        adir = self.asin_dir(asin)
        gen_dir = ensure_dir(adir / "generated")
        manifest = self.load_manifest(asin)
        manifest.setdefault("slots", {})
        ok = failed = 0

        # slots that still need work (the rest is already cached)
        pending: list[dict] = []
        for item in bundle:
            slot = item["slot_id"]
            dest = gen_dir / item["target_file"]
            prev = manifest["slots"].get(slot, {})
            if prev.get("status") == "ok" and dest.exists() and not self.force:
                log.info("%s %s: already done, skipping", asin, slot)
                ok += 1
                continue
            pending.append(item)

        if not pending:
            # nothing to generate - do not even open a Gemini chat
            return {"ok": 1 if ok else 0, "failed": 0,
                    "slots_ok": ok, "slots_failed": 0}

        # ONE continuous chat for this ASIN batch
        # STRICT SEQUENCE: upload refs -> select Create image -> set 3:4
        client.begin_batch(reference_images=refs)

        provider = str(self.cfg.get("generation.provider", "gemini")).strip().lower()
        retries = int(self.cfg.get(f"{provider}.slot_retries", 2))
        retry_delay = self.cfg.get(f"{provider}.slot_retry_delay_sec", [10, 20])

        for item in pending:
            slot = item["slot_id"]
            dest = gen_dir / item["target_file"]
            log.info("%s | slot %s/%d: %s", asin, item["order"], len(bundle), item["title"])

            last_error: Exception | None = None
            for attempt in range(1, retries + 2):
                if attempt > 1:
                    log.warning("%s %s: retry %d/%d after the previous attempt failed",
                                asin, slot, attempt - 1, retries)
                    human_delay(retry_delay, "slot retry")
                    try:
                        # clean session: the old chat already holds a broken reply
                        # STRICT SEQUENCE: refs -> Create image -> 3:4 -> master
                        client.restart_batch(reference_images=refs)
                    except Exception as exc:  # noqa: BLE001
                        log.error("%s %s: batch restart failed: %s", asin, slot, exc)
                try:
                    result = client.generate_image(
                        prompt=item["prompt"],
                        reference_images=refs,
                        dest=dest,
                        dry_run=False,
                    )
                    saved = Path(result["path"])
                    # the image is only "done" once the sparkle remover has
                    # passed over it - cleaned in place, original kept for provenance
                    wm = clean_generated_image(saved, self.cfg)
                    manifest["slots"][slot] = {
                        "status": "ok",
                        "file": rel(saved, adir),
                        "watermark": wm,
                        "attempts": attempt,
                        "at": dt.datetime.now().isoformat(timespec="seconds"),
                    }
                    ok += 1
                    last_error = None
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    log.error("%s %s attempt %d/%d failed: %s", asin, slot,
                              attempt, retries + 1, exc)
                    continue

            if last_error is None:
                self.save_manifest(asin, manifest)
                continue

            manifest["slots"][slot] = {
                "status": "failed",
                "error": str(last_error)[:400],
                "at": dt.datetime.now().isoformat(timespec="seconds"),
                "attempts": retries + 1,
            }
            failed += 1
            self.save_manifest(asin, manifest)

        status = "generated" if failed == 0 else ("partial" if ok else "failed")
        manifest["stages"]["generate"] = {"status": status, "ok": ok, "failed": failed,
                                          "at": dt.datetime.now().isoformat(timespec="seconds")}

        # FINAL SAFETY SWEEP (stage 3 of image production): after the batch
        # completes, verify EVERY image of this ASIN once more through the
        # sparkle remover - upstream cleans can miss a mark, and this stops
        # a watermarked panel from ever reaching the manifest as done.
        wm_enabled = bool(self.cfg.get("watermark.enabled", False))
        sweep = sweep_generated(adir, self.cfg, manifest) if wm_enabled else {}
        manifest["stages"]["watermark_sweep"] = {
            "status": "done" if wm_enabled else "disabled",
            "removed": sweep.get("removed", 0),
            "no_mark": sweep.get("no-mark", 0),
            "ghosts": sweep.get("ghost", 0),
            "errors": sweep.get("error", 0),
            "at": dt.datetime.now().isoformat(timespec="seconds"),
        }
        self.save_manifest(asin, manifest)
        self._write_index(asin, manifest)
        self.report(asin, product, manifest, status, "" if failed == 0 else f"{failed} slot(s) failed")
        return {"ok": 1 if failed == 0 and ok else 0, "failed": 1 if failed else 0,
                "slots_ok": ok, "slots_failed": failed}

    # ------------------------------------------------------------- extras
    def _write_index(self, asin: str, manifest: dict[str, Any]) -> None:
        """Small human-readable upload checklist for the operator."""
        adir = self.asin_dir(asin)
        product = manifest.get("product", {})
        lines = [
            f"# {asin} - image bundle",
            "",
            f"**{product.get('title', '')}**",
            f"Brand: {product.get('brand', '')} | Source: {product.get('url', '')}",
            "",
            "| # | Slot | File | Attempts | Watermark | Status |",
            "|---|------|------|----------|-----------|--------|",
        ]
        for slot_id, data in sorted(manifest.get("slots", {}).items(), key=lambda kv: kv[0]):
            file_rel = str(data.get("file", "-"))
            if not file_rel.startswith("generated/"):
                file_rel = f"generated/{file_rel}"
            first_pass = (data.get("watermark") or {}).get("status", "-")
            final_pass = (data.get("watermark_final") or {}).get("status", "")
            if final_pass and final_pass != first_pass:
                wm = f"{final_pass} (sweep; first: {first_pass})"
            else:
                wm = final_pass or first_pass
            lines.append(f"| | {slot_id} | `{file_rel}` | {data.get('attempts', 1)} | "
                         f"{wm} | {data.get('status')} |")
        lines += ["", "## Base images used as references", ""]
        for p in sorted((adir / "base_images").glob("*.*")):
            lines.append(f"- `base_images/{p.name}`")
        (adir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ------------------------------------------------------------- entry
    def run(self, asins: list[str], extra_notes: str = "") -> dict[str, Any]:
        self.scrape(asins)
        good = [a for a in asins if (self.asin_dir(a) / "product.json").exists()]
        return self.generate(good, extra_notes=extra_notes)
