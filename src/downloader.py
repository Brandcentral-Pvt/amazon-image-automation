"""Download + validate base images from Amazon's CDN."""
from __future__ import annotations

import re
from pathlib import Path

import requests

from .config import Config
from .scraper import hires_candidates
from .utils import ensure_dir, human_size, log, sha256_file

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def _image_size(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(path) as im:
            return im.size
    except Exception:  # noqa: BLE001
        return (0, 0)


def _fetch(session: requests.Session, url: str, dest: Path, timeout: int = 30) -> bool:
    try:
        r = session.get(url, timeout=timeout, headers={"User-Agent": UA, "Referer": "https://www.amazon.in/"})
        if r.status_code != 200 or len(r.content) < 3000:
            return False
        if not r.headers.get("Content-Type", "").startswith("image"):
            return False
        dest.write_bytes(r.content)
        return True
    except requests.RequestException as exc:
        log.debug("fetch fail %s: %s", url, exc)
        return False


def download_base_images(product, asin_dir: Path, cfg: Config) -> list[Path]:
    """Download the gallery into <asin>/base_images/NN.jpg, deduped by content hash."""
    out_dir = ensure_dir(asin_dir / "base_images")
    if cfg.get("output.keep_base_images", True) is False:
        return []

    min_px = int(cfg.get("amazon.min_image_px", 500))
    saved: list[Path] = []
    hashes: set[str] = set()
    session = requests.Session()

    for url in product.image_urls:
        got = False
        for candidate in hires_candidates(url):
            ext = "png" if candidate.lower().endswith(".png") else "jpg"
            tmp = out_dir / f".tmp_{len(saved) + 1:02d}.{ext}"
            if not _fetch(session, candidate, tmp):
                continue

            w, h = _image_size(tmp)
            if w and (w < min_px or h < min_px):
                log.debug("too small (%dx%d): %s", w, h, candidate)
                tmp.unlink(missing_ok=True)
                continue

            digest = sha256_file(tmp)
            if digest in hashes:            # duplicate rendering of the same photo
                tmp.unlink(missing_ok=True)
                got = True
                break

            hashes.add(digest)
            final = out_dir / f"{len(saved) + 1:02d}.{ext}"
            tmp.replace(final)
            saved.append(final)
            log.info("  base image %s (%dx%d, %s)", final.name, w, h, human_size(final.stat().st_size))
            got = True
            break

        if not got:
            log.warning("  could not download any variant of %s", url)
        if len(saved) >= int(cfg.get("amazon.max_gallery_images", 12)):
            break

    log.info("%s: %d base images saved", product.asin, len(saved))
    return saved


def clean_filename(name: str, max_len: int = 80) -> str:
    name = re.sub(r"[^\w.\- ]", "", name).strip().replace(" ", "_")
    return name[:max_len]
