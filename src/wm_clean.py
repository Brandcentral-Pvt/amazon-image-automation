"""Pass every generated image through the Veo/Gemini watermark remover.

Every image the pipeline finalises is handed to the removal engine
(`wm_core.py` inside the user's local remover app) BEFORE it counts as done:

  output/<ASIN>/generated/01_hero_white.png   <- cleaned IN PLACE (related place)
  output/<ASIN>/generated/_with_watermark/    <- pre-clean pixels (provenance)

Statuses reported for the manifest:
  removed  - sparkle found + inpainted, file replaced with the clean image
  no-mark  - detector found nothing -> file left untouched (safe default)
  error    - engine problem -> file kept as generated (never breaks the run)
  skipped  - model/file/python missing
  disabled - watermark.enabled: false
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .config import Config
from .utils import log

WORKER = Path(__file__).resolve().parent / "wm_worker.py"

# only real images belong in the remover - reports/manifests live beside them
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def iter_generated_images(gen_dir: Path) -> list[Path]:
    """Every IMAGE file in the generated/ dir (skips clean_report.json etc.)."""
    gen_dir = Path(gen_dir)
    if not gen_dir.exists():
        return []
    return sorted(p for p in gen_dir.iterdir()
                  if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def _engine_dir(cfg: Config) -> str:
    return str(Path(str(cfg.get("watermark.engine_dir", ""))).expanduser())


def _resolve_python(cfg: Config, engine_dir: str) -> str:
    """Prefer the remover app's own venv (wm_core + onnxruntime live there)."""
    configured = (str(cfg.get("watermark.python") or "") or "").strip()
    if configured:
        return configured
    candidates = [
        Path(engine_dir) / ".venv" / "Scripts" / "python.exe",   # Windows venv
        Path(engine_dir) / ".venv" / "bin" / "python",           # POSIX venv
    ]
    for cand in candidates:
        if cand.exists():
            return str(cand)
    return sys.executable   # last resort: current interpreter


def _resolve_model(cfg: Config, engine_dir: str) -> Path:
    configured = (str(cfg.get("watermark.model") or "") or "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path(engine_dir) / "models" / "lama_fp32.onnx"


def clean_generated_image(path: Path, cfg: Config) -> dict[str, Any]:
    """Run ONE generated image through the sparkle remover, in place."""
    if not bool(cfg.get("watermark.enabled", False)):
        return {"status": "disabled"}

    path = Path(path)
    if not path.exists():
        return {"status": "skipped", "detail": "file missing"}

    engine_dir = _engine_dir(cfg)
    python = _resolve_python(cfg, engine_dir)
    model = _resolve_model(cfg, engine_dir)
    orig_dir = path.parent / "_with_watermark"
    timeout = int(cfg.get("watermark.timeout_sec", 180))
    device = str(cfg.get("watermark.device", "cpu") or "cpu")
    threads = int(cfg.get("watermark.threads", 0))

    if not model.exists():
        log.warning("wm: model not found (%s) - image kept as generated", model)
        return {"status": "skipped", "detail": f"model missing: {model}"}

    cmd = [python, str(WORKER), str(path), engine_dir, str(model),
           str(orig_dir), device, str(threads)]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout,
                              cwd=str(WORKER.parent.parent))
    except subprocess.TimeoutExpired:
        log.warning("wm: cleaner timed out after %ds - image kept as generated", timeout)
        return {"status": "error", "detail": f"timeout after {timeout}s"}
    except OSError as exc:
        log.warning("wm: cleaner could not start (%s) - image kept as generated", exc)
        return {"status": "error", "detail": f"start failed: {exc}"}

    out = (proc.stdout or "").strip()
    try:
        result = json.loads(out.splitlines()[-1]) if out else {}
    except (ValueError, IndexError):
        result = {}
    if not isinstance(result, dict) or not result:
        log.warning("wm: cleaner produced no result (rc=%s) - image kept as generated",
                    proc.returncode)
        return {"status": "error",
                "detail": ((proc.stderr or out or f"exit {proc.returncode}").strip()[:300])}

    result.setdefault("seconds", round(time.time() - t0, 2))
    status = result.get("status")
    if status == "removed":
        log.info("wm: sparkle removed from %s (%s, verdict: %s, %.1fs)", path.name,
                 result.get("method", "?"), result.get("verdict", "?"),
                 float(result.get("seconds", 0)))
    elif status == "no-mark":
        log.info("wm: no sparkle in %s (probe %.2f) - left untouched", path.name,
                 float(result.get("probe", 0)))
    else:
        log.warning("wm: cleaner error for %s: %s - image kept as generated",
                    path.name, result.get("detail", "?"))
    return result


def clean_existing(asin_dir: Path, cfg: Config) -> dict[str, int]:
    """Retro-clean an already-generated bundle (run.py clean --asins ...)."""
    stats: dict[str, int] = {}
    for f in iter_generated_images(Path(asin_dir) / "generated"):
        status = clean_generated_image(f, cfg).get("status", "error")
        stats[status] = stats.get(status, 0) + 1
    return stats


def sweep_generated(asin_dir: Path, cfg: Config, manifest: dict | None = None) -> dict[str, int]:
    """Final verifying pass over EVERY image of a finished batch (per ASIN).

    The per-slot clean runs right after each image; this second pass re-checks
    all of them once the batch completes, because a retry/side-channel render
    can still carry a sparkle the first detection missed. Any mark found in the
    sweep is removed in place, and the outcome is recorded as `watermark_final`
    on the slot (the original `watermark` record of the first pass is kept).

    Returns counters (removed / no-mark / error / skipped / ghost / disabled).
    """
    stats = {"removed": 0, "no-mark": 0, "error": 0, "skipped": 0, "disabled": 0, "ghost": 0}
    if not bool(cfg.get("watermark.enabled", False)):
        return stats
    asin_dir = Path(asin_dir)
    files = iter_generated_images(asin_dir / "generated")
    if not files:
        return stats
    log.info("wm: final sweep over %d image(s) of the finished batch", len(files))
    by_file: dict[str, str] = {}
    if manifest:
        by_file = {str(d.get("file") or ""): sid
                   for sid, d in manifest.get("slots", {}).items() if d.get("file")}
    for f in files:
        res = clean_generated_image(f, cfg)
        status = res.get("status", "error")
        stats[status] = stats.get(status, 0) + 1
        if res.get("ghost"):
            stats["ghost"] += 1
        sid = by_file.get(f"generated/{f.name}") or by_file.get(f.name)
        if sid is not None and manifest is not None:
            manifest.setdefault("slots", {}).setdefault(sid, {})["watermark_final"] = res
        if status == "removed":
            log.info("wm (sweep): sparkle found + removed in %s", f.name)
        elif status == "no-mark":
            log.debug("wm (sweep): %s clean", f.name)
        elif status != "disabled":
            log.warning("wm (sweep): %s status %s - inspect %s", f.name, status, f.name)
    return stats
