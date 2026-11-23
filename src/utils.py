"""Shared helpers: logging, paths, retries, file hashing."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar

T = TypeVar("T")

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------- logging
def setup_logging(level: str = "INFO", log_file: Path | None = None) -> logging.Logger:
    logger = logging.getLogger("amz")
    if logger.handlers:
        return logger
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", "%H:%M:%S")

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger


log = setup_logging()


# --------------------------------------------------------------------- paths
def ensure_dir(path: Path | str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def iter_real_files(dir_path: Path | str, pattern: str = "*.*") -> list[Path]:
    """Sorted files in dir matching pattern, SKIPPING dotfiles.

    pathlib glob matches dotfiles (unlike shell), so a crashed download's
    `.tmp_01.jpg` leftover must never be treated as a real base/generated image.
    """
    d = Path(dir_path)
    if not d.exists():
        return []
    return sorted(p for p in d.glob(pattern)
                  if p.is_file() and not p.name.startswith("."))


# --------------------------------------------------------------------- image QA
def parse_aspect(aspect: str) -> float | None:
    """'3:4' -> 0.75 (width/height). None when unparseable."""
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\s*", str(aspect or ""))
    if not m:
        return None
    w, h = float(m.group(1)), float(m.group(2))
    return (w / h) if h else None


def aspect_targets(cfg) -> list[float]:
    """Accepted width/height ratios for a generated panel: the UI aspect lock
    (gemini.aspect_ratio, e.g. 3:4 -> 0.75) AND the panel spec
    (studio.panel_width x studio.panel_height, e.g. 1600x1920 -> 0.833)."""
    targets: list[float] = []
    r = parse_aspect(str(cfg.get("gemini.aspect_ratio", "3:4") or ""))
    if r:
        targets.append(r)
    try:
        w = float(cfg.get("studio.panel_width", 1600) or 0)
        h = float(cfg.get("studio.panel_height", 1920) or 0)
        if w and h:
            targets.append(w / h)
    except Exception:  # noqa: BLE001
        pass
    return targets or [0.75]


def verify_generated_image(path: Path | str, *, targets: list[float],
                           min_long_side: int = 1000, aspect_tol: float = 0.06,
                           ref_hashes: set[str] | None = None,
                           seen_hashes: set[str] | None = None) -> dict[str, Any]:
    """Accuracy gate for one captured image.

    Returns {"ok", "w", "h", "sha256", "reason"}:
      - decodable by PIL
      - longest side >= min_long_side (Amazon requires >= 1000 px)
      - portrait (h > w)
      - w/h within aspect_tol of one of the accepted target ratios
      - not byte-identical to an uploaded reference (Gemini sometimes echoes
        an upload back unchanged)
      - not a duplicate of an earlier panel of this batch
    """
    path = Path(path)
    result: dict[str, Any] = {"ok": False, "w": 0, "h": 0, "sha256": "", "reason": ""}
    try:
        from PIL import Image

        with Image.open(path) as im:
            w, h = im.size
            im.load()  # force full decode - truncated files fail here
    except Exception as exc:  # noqa: BLE001
        result["reason"] = f"undecodable image ({exc})"
        return result
    digest = sha256_file(path)
    result.update(w=w, h=h, sha256=digest)
    if max(w, h) < min_long_side:
        result["reason"] = (f"too small: {w}x{h} - longest side must be >= "
                            f"{min_long_side}px (Amazon minimum)")
        return result
    if h <= w:
        result["reason"] = f"not a portrait panel: {w}x{h}"
        return result
    ratio = w / h
    if not any(abs(ratio - t) <= aspect_tol for t in targets):
        result["reason"] = (f"aspect {ratio:.3f} outside accepted targets "
                            f"{[round(t, 3) for t in targets]} +/-{aspect_tol}")
        return result
    if ref_hashes and digest in ref_hashes:
        result["reason"] = "Gemini returned an uploaded reference image unchanged"
        return result
    if seen_hashes and digest in seen_hashes:
        result["reason"] = "duplicate of an earlier panel in this chat"
        return result
    result["ok"] = True
    return result


def normalize_image_ext(path: Path | str, dest: Path | str) -> Path:
    """Keep the slot's canonical file name/extension.

    A browser download can land with the server's own suffix (.jpg/.webp); re-encode
    it to the target name (lossless PNG) so every slot file matches its slot spec.
    Falls back to the original file if re-encoding fails.
    """
    path, dest = Path(path), Path(dest)
    if path == dest or path.suffix.lower() == dest.suffix.lower():
        return path
    try:
        from PIL import Image

        with Image.open(path) as im:
            im.save(dest)
        path.unlink(missing_ok=True)
        log.info("re-encoded %s -> %s", path.name, dest.name)
        return dest
    except Exception as exc:  # noqa: BLE001
        log.warning("could not re-encode %s to %s (%s) - keeping original", path, dest, exc)
        return path


def slugify(text: str, max_len: int = 60) -> str:
    text = re.sub(r"[^\w\s-]", "", str(text)).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:max_len].strip("-") or "item"


def rel(path: Path | str, base: Path | str | None = None) -> str:
    path, base = Path(path), Path(base or PROJECT_ROOT)
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path)


# --------------------------------------------------------------------- files
def write_json(path: Path | str, data: Any) -> Path:
    p = Path(path)
    ensure_dir(p.parent)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def read_json(path: Path | str, default: Any = None) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log.warning("corrupt json: %s", p)
        return default


def sha256_file(path: Path | str, chunk: int = 1 << 16) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def human_size(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024 or unit == "GB":
            return f"{num_bytes:.1f}{unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f}GB"


# --------------------------------------------------------------------- timing
def human_delay(rng: Iterable[float] | None = None, label: str = "") -> float:
    lo, hi = (list(rng) + [1, 3])[:2] if rng else (1, 3)
    wait = random.uniform(float(lo), float(hi))
    if label:
        log.debug("sleeping %.1fs (%s)", wait, label)
    time.sleep(wait)
    return wait


def retry(
    times: int = 3,
    backoff: float = 8.0,
    jitter: float = 2.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    fatal: tuple[type[BaseException], ...] = (TypeError, AttributeError, KeyError, FileNotFoundError),
    on_error: Callable[[int, BaseException], None] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry decorator with exponential backoff + jitter."""

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last: BaseException | None = None
            for attempt in range(1, times + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:  # noqa: PERF203
                    if isinstance(exc, fatal):
                        # a code bug, not a transient network/bot failure - do not retry
                        log.error("%s: non-retryable error: %s", getattr(fn, "__name__", "call"), exc)
                        raise
                    last = exc
                    if on_error:
                        on_error(attempt, exc)
                    if attempt == times:
                        break
                    wait = backoff * (2 ** (attempt - 1)) + random.uniform(0, jitter)
                    log.warning(
                        "%s failed (attempt %d/%d): %s -> retry in %.1fs",
                        getattr(fn, "__name__", "call"), attempt, times, exc, wait,
                    )
                    time.sleep(wait)
            assert last is not None
            raise last
        return wrapper
    return decorator


# --------------------------------------------------------------------- misc
def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default) or default


def chunked(items: list[Any], size: int) -> Iterable[list[Any]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def parse_asin_list(text: str) -> list[str]:
    """Accept bare ASINs, amazon URLs, or URLs with /dp/ or /gp/product/."""
    found: list[str] = []
    for token in re.split(r"[\s,;]+", text or ""):
        token = token.strip().strip('"').strip("'")
        if not token:
            continue
        m = re.search(r"(?:/dp/|/gp/product/|/product/|asin=)([A-Z0-9]{10})", token, re.I)
        if m:
            found.append(m.group(1).upper())
            continue
        if re.fullmatch(r"[A-Z0-9]{10}", token, re.I):
            found.append(token.upper())
    seen, out = set(), []
    for a in found:
        if a not in seen:
            seen.add(a)
            out.append(a)
    return out


def read_asins(source: str) -> list[str]:
    """File path or a literal comma/newline separated string."""
    p = Path(source)
    if p.exists() and p.is_file():
        return parse_asin_list(p.read_text(encoding="utf-8"))

    looks_like_path = any(ch in source for ch in ("/", "\\")) or p.suffix.lower() in (
        ".txt", ".csv", ".list", ".md")
    if looks_like_path:
        hint = ""
        sample = PROJECT_ROOT / "data" / "asins.sample.txt"
        if sample.exists():
            hint = f" (a template exists at {sample})"
        raise FileNotFoundError(
            f"ASIN file not found: {p.resolve()}{hint} - create it with one ASIN per line, "
            f'or pass ASINs directly: --asins "B0CP9MK37V,B0CLRPLR4D"'
        )

    asins = parse_asin_list(source)
    if not asins:
        raise ValueError(f"no valid 10-character ASINs found in: {source[:80]!r}")
    return asins
