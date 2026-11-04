"""Image-generation backend selection.

The pipeline talks to a *driver* object with this interface (both drivers
implement it):

    with Driver(cfg, headless=...) as drv:
        drv.begin_batch(master, reference_images=refs)
        drv.restart_batch(reference_images=refs)          # on slot retry
        drv.generate_image(prompt=..., reference_images=refs, dest=...) -> {"ok", "path"}

Backends (config: image.backend):
  * "gemini_web" (default) - drives https://gemini.google.com/images (src/gemini_web.py)
  * "arena_web"            - drives https://arena.ai/image  (src/arena_web.py)

Add a backend by implementing the same interface in a new module and registering
it in get_driver() below.
"""
from __future__ import annotations

from .config import Config

DEFAULT_BACKEND = "gemini_web"


def backend_name(cfg: Config) -> str:
    return str(cfg.get("image.backend", DEFAULT_BACKEND) or DEFAULT_BACKEND).lower()


def backend_url(cfg: Config) -> str:
    """The page `run.py login` / `run.py probe` should open for the active backend."""
    if backend_name(cfg) == "arena_web":
        return str(cfg.get("arena.url", "https://arena.ai/image") or "https://arena.ai/image")
    from .gemini_web import DEFAULT_GEMINI_URL

    return str(cfg.get("gemini.url", DEFAULT_GEMINI_URL) or DEFAULT_GEMINI_URL)


def get_driver(cfg: Config):
    """Return the driver CLASS for the configured backend."""
    name = backend_name(cfg)
    if name in ("arena_web", "arena"):
        from .arena_web import ArenaWeb

        return ArenaWeb
    from .gemini_web import GeminiWeb

    return GeminiWeb


def image_check_cfg(cfg: Config) -> dict:
    """The generated-image accuracy gate config.

    Lives under the active backend's section (arena.image_check /
    gemini.image_check) with a top-level image.image_check override.
    """
    top = cfg.get("image.image_check")
    if isinstance(top, dict) and top:
        return top
    section = "arena" if backend_name(cfg) == "arena_web" else "gemini"
    return cfg.get(f"{section}.image_check", {}) or {}
