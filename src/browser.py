"""Browser launching: real Chrome profile reuse (beats Google's "Couldn't sign you in").

Why this file exists
--------------------
Google rejects password sign-ins from Playwright's bundled Chromium
("This browser or app may not be secure"). The reliable way in is to never sign
in at all: reuse the Chrome profile you are already logged into.

Two supported modes (config: browser.profile_source):

  "playwright"  Playwright's own Chromium + its own profile (default, isolated)
  "chrome"      REAL Google Chrome + a COPY of your signed-in profile
                -> Gemini/Amazon are already logged in, no sign-in screen ever

Plus an optional escape hatch: `browser.cdp_url` attaches Playwright to a Chrome
you started yourself (most stealthy, and immune to Chrome 136+'s refusal to
enable remote debugging on the default profile).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import platform
import shutil
from pathlib import Path
from typing import Any

from .config import Config
from .utils import ensure_dir, log, write_json

# directories inside a Chrome profile that are huge and useless to us
SKIP_DIRS = {
    "Cache", "Code Cache", "GPUCache", "ShaderCache", "GrShaderCache", "GraphiteDawnCache",
    "DawnCache", "DawnGraphiteCache", "Service Worker", "CacheStorage", "Crashpad",
    "BrowserMetrics", "optimization_guide_model_store", "component_crx_cache",
    "extensions_crx_cache", "Segmentation Platform", "Safe Browsing", "Snapshots",
    "blob_storage", "File System", "GCM Store", "OptimizationHints", "AutofillStrikeDatabase",
}
# files that matter for an authenticated session
KEEP_FILES = [
    "Preferences", "Secure Preferences", "Cookies", "Cookies-journal",
    "Login Data", "Login Data For Account", "Web Data", "History", "Bookmarks",
    "Network/Cookies", "Network/Cookies-journal", "Network/TransportSecurity",
    "Network/Network Persistent State",
]
KEEP_DIRS = ["Local Storage", "Session Storage", "IndexedDB", "Shared Dictionary"]


# --------------------------------------------------------------------- locating chrome
def chrome_user_data_dir() -> Path | None:
    system = platform.system()
    candidates: list[Path] = []
    if system == "Windows":
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            candidates.append(Path(local) / "Google" / "Chrome" / "User Data")
        candidates.append(Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
                          / "Google" / "Chrome" / "User Data")
    elif system == "Darwin":
        candidates.append(Path.home() / "Library" / "Application Support" / "Google" / "Chrome")
    else:
        candidates += [Path.home() / ".config" / "google-chrome",
                       Path.home() / ".config" / "chromium"]
    for cand in candidates:
        if cand.exists() and (cand / "Local State").exists():
            return cand
    return None


def list_profiles(user_data: Path) -> list[str]:
    """Profile folder names that actually hold data: 'Default', 'Profile 1', ..."""
    found = []
    for child in sorted(user_data.iterdir()):
        if child.is_dir() and (child / "Preferences").exists():
            found.append(child.name)
    return found


def profile_display_name(user_data: Path, profile: str) -> str:
    try:
        prefs = json.loads((user_data / profile / "Preferences").read_text(encoding="utf-8"))
        return prefs.get("profile", {}).get("name", "") or profile
    except Exception:  # noqa: BLE001
        return profile


def find_profile_by_name(user_data: Path, display_name: str) -> str | None:
    """Resolve a Chrome profile DISPLAY name ('Chirag') to its folder ('Profile 2').

    Also accepts a raw folder name ('Profile 2', 'Default') directly. Checks the
    per-profile Preferences, then Chrome's Local State cache (which knows the
    signed-in account name too).
    """
    want = (display_name or "").strip().lower()
    if not want:
        return None
    for folder in list_profiles(user_data):
        if folder.lower() == want:
            return folder
        if profile_display_name(user_data, folder).strip().lower() == want:
            return folder
    try:
        state = json.loads((user_data / "Local State").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    cache = ((state.get("profile") or {}).get("info_cache") or {})
    for folder, info in cache.items():
        if info.get("is_ephemeral"):
            continue
        names = (info.get("name"), info.get("gaia_name"), info.get("user_name"))
        if any(n and str(n).strip().lower() == want for n in names):
            return folder
    return None


# --------------------------------------------------------------------- copying
def _copy_file(src: Path, dest: Path) -> bool:
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return True
    except (PermissionError, OSError) as exc:
        log.warning("  skipped locked file %s (%s)", src.name, exc.__class__.__name__)
        return False


def copy_profile(user_data: Path, profile: str = "Default", dest: Path | None = None) -> dict[str, Any]:
    """Copy the authenticated bits of a Chrome profile into a Playwright profile dir.

    Skipped: caches, extensions, GPU blobs. Chrome should ideally be closed, but
    locked files (Windows) are skipped gracefully instead of aborting.
    """
    src = user_data / profile
    if not src.exists():
        raise FileNotFoundError(f"Chrome profile not found: {src}")
    dest = ensure_dir(dest or Path.cwd() / ".browser-profile-chrome")
    copy_dir = dest / profile
    ensure_dir(copy_dir)

    copied, skipped = 0, 0
    # root-level state (required for cookie decryption on Windows)
    for root_file in ("Local State", "First Run"):
        if (user_data / root_file).exists():
            copied += _copy_file(user_data / root_file, dest / root_file)

    for rel in KEEP_FILES:
        f = src / rel
        if f.exists() and f.is_file():
            copied += _copy_file(f, copy_dir / rel)
        elif f.exists():
            skipped += 1

    for rel in KEEP_DIRS:
        d = src / rel
        if not d.exists():
            continue
        for item in d.rglob("*"):
            if item.is_file():
                if any(part in SKIP_DIRS for part in item.parts):
                    continue
                if _copy_file(item, copy_dir / item.relative_to(src)):
                    copied += 1
                else:
                    skipped += 1

    info = {
        "source": str(src),
        "dest": str(dest),
        "profile": profile,
        "profile_name": profile_display_name(user_data, profile),
        "files_copied": copied,
        "files_skipped": skipped,
        "copied_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    write_json(dest / ".profile-copy.json", info)
    log.info("profile copied: %d files (%d skipped) -> %s", copied, skipped, dest)
    return info


def ensure_chrome_profile(cfg: Config) -> Path | None:
    """Make sure the copied Chrome profile exists; returns its dir (or None)."""
    if not cfg.get("browser.use_chrome_profile", False):
        return None

    dest = cfg.resolve(cfg.get("browser.user_data_dir", ".browser-profile"))
    marker = dest / ".profile-copy.json"
    recopy = bool(cfg.get("browser.recopy_chrome_profile", False))
    profile = cfg.get("browser.chrome_profile", "Default") or "Default"

    if marker.exists() and not recopy:
        log.debug("using existing copied Chrome profile: %s", dest)
        return dest

    override = cfg.get("browser.chrome_user_data_dir")
    user_data = Path(override).expanduser() if override else chrome_user_data_dir()
    if not user_data or not Path(user_data).exists():
        raise RuntimeError(
            "Could not find a Chrome 'User Data' folder. Set browser.chrome_user_data_dir "
            "in config.yaml, or switch browser.use_chrome_profile to false."
        )
    user_data = Path(user_data)

    profiles = list_profiles(user_data)
    if profile not in profiles:
        raise RuntimeError(
            f"Chrome profile '{profile}' not found in {user_data}. Available: {profiles}. "
            "Set browser.chrome_profile accordingly."
        )
    log.info("copying Chrome profile '%s' from %s", profile, user_data)
    copy_profile(user_data, profile, dest)
    return dest


# --------------------------------------------------------------- gemini: own Chrome profile
_COOKIE_RELS = ("Cookies", "Network/Cookies")


def _cookie_files_missing(src: Path, dest: Path) -> bool:
    """True when a previous copy grabbed no session cookies (e.g. Chrome was open)."""
    return any((src / rel).exists() and not (dest / rel).exists() for rel in _COOKIE_RELS)


def ensure_gemini_profile(cfg: Config) -> tuple[Path, str] | None:
    """Prepare an isolated copy of the user's OWN signed-in Chrome profile for Gemini.

    Returns (profile_dir, profile_folder), or None when gemini.use_own_chrome_profile
    is disabled. Scraping keeps using browser.user_data_dir - this touches nothing there.
    """
    if not cfg.get("gemini.use_own_chrome_profile", False):
        return None

    dest = cfg.resolve(cfg.get("gemini.user_data_dir", ".browser-profile-gemini"))
    recopy = bool(cfg.get("gemini.recopy_chrome_profile", False))

    override = cfg.get("gemini.chrome_user_data_dir") or cfg.get("browser.chrome_user_data_dir")
    user_data = Path(override).expanduser() if override else chrome_user_data_dir()
    if not user_data or not Path(user_data).exists():
        raise RuntimeError(
            "Could not find a Chrome 'User Data' folder. Set gemini.chrome_user_data_dir "
            "in config.yaml, or set gemini.use_own_chrome_profile to false."
        )
    user_data = Path(user_data)

    want = str(cfg.get("gemini.chrome_profile_name", "") or "Chirag")
    folder = find_profile_by_name(user_data, want)
    if folder is None:
        available = ", ".join(
            f"{p} ({profile_display_name(user_data, p)!r})" for p in list_profiles(user_data)
        )
        raise RuntimeError(
            f"Chrome profile '{want}' not found in {user_data}. Available: {available}. "
            "Set gemini.chrome_profile_name to the name shown in Chrome's profile picker."
        )

    src = user_data / folder
    cookies_missing = _cookie_files_missing(src, dest / folder)
    if dest.exists() and recopy is False and not cookies_missing:
        log.debug("using existing copied Chrome profile for Gemini: %s", dest)
        return dest, folder
    if cookies_missing:
        recopy = True   # self-heal: a previous copy missed the session cookies

    log.info("copying own Chrome profile '%s' (%s) for Gemini from %s", want, folder, user_data)
    copy_profile(user_data, folder, dest)
    if _cookie_files_missing(src, dest / folder):
        log.warning(
            "cookie files could not be copied (Chrome is probably running). Close ALL Chrome "
            "windows and run again, or log in once with: python run.py login --gemini"
        )
    return dest, folder


def ensure_chatgpt_profile(cfg: Config) -> tuple[Path, str] | None:
    """Prepare an isolated copy of the user's OWN signed-in Chrome profile for ChatGPT.

    Returns (profile_dir, profile_folder), or None when chatgpt.use_own_chrome_profile
    is disabled. Scraping keeps using browser.user_data_dir - this touches nothing there.
    """
    if not cfg.get("chatgpt.use_own_chrome_profile", False):
        return None

    dest = cfg.resolve(cfg.get("chatgpt.user_data_dir", ".browser-profile-chatgpt"))
    recopy = bool(cfg.get("chatgpt.recopy_chrome_profile", False))

    override = cfg.get("chatgpt.chrome_user_data_dir") or cfg.get("browser.chrome_user_data_dir")
    user_data = Path(override).expanduser() if override else chrome_user_data_dir()
    if not user_data or not Path(user_data).exists():
        raise RuntimeError(
            "Could not find a Chrome 'User Data' folder. Set chatgpt.chrome_user_data_dir "
            "in config.yaml, or set chatgpt.use_own_chrome_profile to false."
        )
    user_data = Path(user_data)

    want = str(cfg.get("chatgpt.chrome_profile_name", "") or "Default")
    folder = find_profile_by_name(user_data, want)
    if folder is None:
        available = ", ".join(
            f"{p} ({profile_display_name(user_data, p)!r})" for p in list_profiles(user_data)
        )
        raise RuntimeError(
            f"Chrome profile '{want}' not found in {user_data}. Available: {available}. "
            "Set chatgpt.chrome_profile_name to the name shown in Chrome's profile picker."
        )

    src = user_data / folder
    cookies_missing = _cookie_files_missing(src, dest / folder)
    if dest.exists() and recopy is False and not cookies_missing:
        log.debug("using existing copied Chrome profile for ChatGPT: %s", dest)
        return dest, folder
    if cookies_missing:
        recopy = True   # self-heal: a previous copy missed the session cookies

    log.info("copying own Chrome profile '%s' (%s) for ChatGPT from %s", want, folder, user_data)
    copy_profile(user_data, folder, dest)
    if _cookie_files_missing(src, dest / folder):
        log.warning(
            "cookie files could not be copied (Chrome is probably running). Close ALL Chrome "
            "windows and run again, or log in once with: python run.py chatgpt-login"
        )
    return dest, folder


# --------------------------------------------------------------------- launching
def launch_context(pw, cfg: Config, headless: bool = True):
    """Shared persistent context: Amazon scraping + Gemini driving use the same one."""
    cdp_url = (cfg.get("browser.cdp_url") or "").strip()
    if cdp_url:
        log.info("attaching to a running Chrome via CDP: %s", cdp_url)
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        return ctx, browser

    profile_dir = cfg.resolve(cfg.get("browser.user_data_dir", ".browser-profile"))
    ensure_dir(profile_dir)
    if cfg.get("browser.use_chrome_profile", False):
        ensure_chrome_profile(cfg)

    channel = cfg.get("browser.channel") or None
    use_chrome = bool(cfg.get("browser.use_chrome_profile", False))
    if use_chrome and channel in (None, "", "chromium"):
        channel = "chrome"

    args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-features=Translate,OptimizationHints,MediaRouter",
    ]
    args += list(cfg.get("browser.extra_args", []) or [])
    if cfg.get("browser.headless_new", True) and headless and channel == "chrome":
        args.append("--headless=new")

    kwargs: dict[str, Any] = {
        "headless": headless and not (channel == "chrome" and not cfg.get("browser.headless_new", True)),
        "viewport": cfg.get("browser.viewport", {"width": 1440, "height": 900}),
        "locale": cfg.get("browser.locale", "en-US"),
        "args": args,
        "ignore_default_args": ["--enable-automation"],
    }
    if cfg.get("browser.user_agent"):
        kwargs["user_agent"] = cfg.get("browser.user_agent")
    if cfg.get("browser.proxy"):
        kwargs["proxy"] = {"server": cfg.get("browser.proxy")}
    if channel:
        kwargs["channel"] = channel

    log.debug("launching %s profile=%s headless=%s", channel or "chromium", profile_dir.name, kwargs["headless"])
    ctx = pw.chromium.launch_persistent_context(str(profile_dir), **kwargs)
    ctx.add_init_script(
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        "window.chrome = window.chrome || { runtime: {} };"
    )
    return ctx, None


def launch_gemini_context(pw, cfg: Config, headless: bool = True):
    """Playwright context for Gemini that runs on the user's OWN Chrome profile.

    Copies the signed-in profile (gemini.chrome_profile_name, e.g. 'Chirag') into an
    isolated dir (gemini.user_data_dir) so normal Chrome can stay open during
    automation. Real Chrome is used for the copy - bundled Chromium cannot read
    Chrome's encrypted cookies. When the feature is disabled this falls back to the
    shared scraping context, exactly like before.
    """
    prepared = ensure_gemini_profile(cfg)
    if prepared is None:
        from .scraper import launch_context  # legacy shared-context path

        return launch_context(pw, cfg, headless=headless)
    dest, folder = prepared

    args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-features=Translate,OptimizationHints,MediaRouter",
        f"--profile-directory={folder}",
    ]
    args += list(cfg.get("browser.extra_args", []) or [])
    channel = cfg.get("gemini.chrome_channel") or "chrome"
    if cfg.get("browser.headless_new", True) and headless and channel == "chrome":
        args.append("--headless=new")

    kwargs: dict[str, Any] = {
        "headless": headless and not (channel == "chrome" and not cfg.get("browser.headless_new", True)),
        "viewport": cfg.get("browser.viewport", {"width": 1440, "height": 900}),
        "locale": cfg.get("browser.locale", "en-US"),
        "args": args,
        "ignore_default_args": ["--enable-automation"],
    }
    if cfg.get("browser.user_agent"):
        kwargs["user_agent"] = cfg.get("browser.user_agent")
    if cfg.get("browser.proxy"):
        kwargs["proxy"] = {"server": cfg.get("browser.proxy")}
    if channel:
        kwargs["channel"] = channel

    log.debug("launching Gemini on own Chrome profile %s (%s) headless=%s",
              folder, dest.name, kwargs["headless"])
    ctx = pw.chromium.launch_persistent_context(str(dest), **kwargs)
    ctx.add_init_script(
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        "window.chrome = window.chrome || { runtime: {} };"
    )
    return ctx, None


def launch_chatgpt_context(pw, cfg: Config, headless: bool = True):
    """Playwright context for ChatGPT that runs on the user's OWN Chrome profile.

    Copies the signed-in profile (chatgpt.chrome_profile_name, e.g. 'brandcentral') into an
    isolated dir (chatgpt.user_data_dir) so normal Chrome can stay open during
    automation. Real Chrome is used for the copy - bundled Chromium cannot read
    Chrome's encrypted cookies. When the feature is disabled this falls back to the
    shared scraping context, exactly like before.
    """
    prepared = ensure_chatgpt_profile(cfg)
    if prepared is None:
        from .scraper import launch_context  # legacy shared-context path
        return launch_context(pw, cfg, headless=headless)
    dest, folder = prepared

    args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-features=Translate,OptimizationHints,MediaRouter",
        f"--profile-directory={folder}",
    ]
    args += list(cfg.get("browser.extra_args", []) or [])
    channel = cfg.get("chatgpt.chrome_channel") or "chrome"
    if cfg.get("browser.headless_new", True) and headless and channel == "chrome":
        args.append("--headless=new")

    kwargs: dict[str, Any] = {
        "headless": headless and not (channel == "chrome" and not cfg.get("browser.headless_new", True)),
        "viewport": cfg.get("browser.viewport", {"width": 1440, "height": 900}),
        "locale": cfg.get("browser.locale", "en-US"),
        "args": args,
        "ignore_default_args": ["--enable-automation"],
    }
    if cfg.get("browser.user_agent"):
        kwargs["user_agent"] = cfg.get("browser.user_agent")
    if cfg.get("browser.proxy"):
        kwargs["proxy"] = {"server": cfg.get("browser.proxy")}
    if channel:
        kwargs["channel"] = channel

    log.debug("launching ChatGPT on own Chrome profile %s (%s) headless=%s",
              folder, dest.name, kwargs["headless"])
    ctx = pw.chromium.launch_persistent_context(str(dest), **kwargs)
    ctx.add_init_script(
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        "window.chrome = window.chrome || { runtime: {} };"
    )
    return ctx, None


def session_report(ctx) -> dict[str, Any]:
    """Which accounts are actually signed in inside this profile?"""
    report: dict[str, Any] = {"google": False, "amazon": False, "google_accounts": 0}
    try:
        cookies = ctx.cookies()
    except Exception:  # noqa: BLE001
        return report
    names = {(c.get("domain", ""), c.get("name", "")) for c in cookies}
    report["google"] = any("SID" == n or "__Secure-1PSID" == n for _d, n in names)
    report["amazon"] = any(n in ("session-id", "at-main") for _d, n in names)
    report["google_accounts"] = len({c.get("domain") for c in cookies if "google" in c.get("domain", "")})
    return report
