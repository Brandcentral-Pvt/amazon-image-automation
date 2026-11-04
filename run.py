#!/usr/bin/env python3
"""CLI entry point.

  python run.py login                       # one-time: sign in to Google (persistent profile)
  python run.py scrape  --asins asins.txt   # crawl + download base images
  python run.py generate --asins asins.txt  # build prompts + generate the 8 images
  python run.py clean   --asins asins.txt   # watermark-clean already-generated images
  python run.py all     --asins asins.txt   # full pipeline
  python run.py one     --asin B0XXXXXXXX   # single ASIN, full pipeline
  python run.py probe [--interactive]       # dump Gemini page diagnostics (fix selectors from data)

Handy flags: --dry-run (prompts only, no Gemini calls) --headed (watch the browser)
             --force (regenerate finished slots) --limit 5 --config other.yaml
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import load_config            # noqa: E402
from src.utils import log, read_asins, setup_logging  # noqa: E402


def _asins(args) -> list[str]:
    items: list[str] = []
    if getattr(args, "asin", None):
        items.append(args.asin.upper())
    if getattr(args, "asins", None):
        try:
            items += read_asins(args.asins)
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
    if not items:
        raise SystemExit("Provide --asin or --asins <file|list>")
    seen, out = set(), []
    for a in items:
        if a not in seen:
            seen.add(a)
            out.append(a)
    if getattr(args, "limit", 0):
        out = out[: args.limit]
    return out


def cmd_login(args) -> int:
    cfg = load_config(args.config)
    from playwright.sync_api import sync_playwright

    use_gemini_profile = bool(getattr(args, "gemini", False))
    log.info("Opening a browser - sign in to Google (and Amazon if you want), then press Enter here.")
    with sync_playwright() as pw:
        if use_gemini_profile:
            from src.browser import launch_gemini_context

            ctx, _ = launch_gemini_context(pw, cfg, headless=False)
        else:
            from src.scraper import launch_context

            ctx, _ = launch_context(pw, cfg, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        from src.gemini_web import DEFAULT_GEMINI_URL

        page.goto(cfg.get("gemini.url", DEFAULT_GEMINI_URL))
        try:
            input("Press Enter once you are logged in... ")
        except EOFError:
            page.wait_for_timeout(120000)
        ctx.close()
    profile_dir = cfg.get("gemini.user_data_dir") if use_gemini_profile \
        else cfg.get("browser.user_data_dir")
    log.info("Session stored in %s", profile_dir)
    return 0


def cmd_scrape(args) -> int:
    from src.pipeline import Pipeline

    cfg = load_config(args.config)
    products = Pipeline(cfg, args.dry_run, args.force).scrape(_asins(args))
    failed = sorted(a for a, p in products.items() if p.scrape_status != "ok")
    if failed:
        log.error("scrape failed for %d ASIN(s): %s", len(failed), ", ".join(failed))
        return 1
    return 0


def cmd_generate(args) -> int:
    from src.pipeline import Pipeline

    cfg = load_config(args.config)
    stats = Pipeline(cfg, args.dry_run, args.force).generate(_asins(args), extra_notes=args.notes or "")
    log.info("done: %s", stats)
    return 0 if not stats.get("failed") else 1


def cmd_clean(args) -> int:
    """Retro-clean already-generated bundles through the watermark remover."""
    import datetime as dt

    from src.utils import read_json, write_json
    from src.wm_clean import clean_generated_image

    cfg = load_config(args.config)
    totals: dict[str, int] = {}
    for asin in _asins(args):
        adir = Path(cfg.asin_dir(asin))
        gen_dir = adir / "generated"
        from src.utils import iter_real_files
        from src.wm_clean import IMAGE_EXTS

        files = [f for f in iter_real_files(gen_dir) if f.suffix.lower() in IMAGE_EXTS]
        if not files:
            log.info("%s: no generated images (run generate first)", asin)
            continue
        log.info("%s: watermark-cleaning %d generated image(s)", asin, len(files))
        manifest = read_json(adir / "manifest.json", {}) or {}
        changed = False
        rel_files = {d.get("file"): sid for sid, d in manifest.get("slots", {}).items()}
        rows: list[dict] = []
        for f in files:
            res = clean_generated_image(f, cfg)
            status = res.get("status", "error")
            totals[status] = totals.get(status, 0) + 1
            rows.append({"file": f.name, **res})
            sid = rel_files.get(f.relative_to(adir).as_posix())
            if sid is not None:
                manifest["slots"][sid]["watermark"] = res
                changed = True
        write_json(gen_dir / "clean_report.json",
                   {"asin": asin, "updated": dt.datetime.now().isoformat(timespec="seconds"),
                    "rows": rows})
        if changed:
            manifest.setdefault("stages", {})["watermark"] = {
                "status": "done",
                "at": dt.datetime.now().isoformat(timespec="seconds"),
                "totals": dict(totals),
            }
            write_json(adir / "manifest.json", manifest)
    log.info("clean done: %s", totals)
    return 0 if not totals.get("error") else 1


def cmd_all(args) -> int:
    from src.pipeline import Pipeline

    cfg = load_config(args.config)
    stats = Pipeline(cfg, args.dry_run, args.force).run(_asins(args), extra_notes=args.notes or "")
    log.info("done: %s", stats)
    return 0 if not stats.get("failed") else 1


def cmd_probe(args) -> int:
    """Open a Gemini page in the persistent profile and dump page diagnostics.

    Writes logs/gemini/probe_*.{json,html,png}: every button/file input/
    contenteditable on the live page + screenshot (buttons include a truncated
    outerHTML so exact XPaths can be derived). With --steps, one tagged dump per
    UI action is captured (step_1_home, step_2_attach, step_3_model_picker,
    step_4_aspect, step_5_image) - use --interactive (headed) and click the
    element named in each step so its menu is open when the dump is taken.
    All dumps are merged into logs/gemini/selectors.suggested.yaml, a ready-to-
    review mapping of gemini.selectors.* keys to concrete selectors for THIS page.
    Use --url to probe a specific page, e.g. --url https://gemini.google.com/images
    """
    import yaml

    from src.gemini_web import GeminiWeb, suggest_selectors

    cfg = load_config(args.config)
    if getattr(args, "url", None):
        cfg.data.setdefault("gemini", {})["url"] = args.url
    headless = bool(cfg.get("browser.headless", True)) and not args.headed
    with GeminiWeb(cfg, headless=headless) as gem:
        reports = [gem.dump_diagnostics("probe")]
        log.info("probe: url=%s image_count=%s buttons=%d -> %s",
                 reports[0].get("url"), reports[0].get("image_count"),
                 len(reports[0].get("buttons") or []), reports[0].get("json"))
        if getattr(args, "steps", False):
            reports += gem.capture_steps(interactive=args.interactive)
        elif args.interactive:
            log.info("interactive: click around in the browser window, then press Enter here")
            try:
                input("Press Enter to dump the final report... ")
            except EOFError:
                pass
            reports.append(gem.dump_diagnostics("probe_final"))

    # merge all step dumps -> suggested selectors for this page
    merged: dict[str, list] = {"buttons": [], "file_inputs": [], "contenteditables": []}
    for r in reports:
        for k in merged:
            merged[k] += r.get(k) or []
    ratio = str(cfg.get("gemini.aspect_ratio", "3:4") or "3:4")
    sugg = suggest_selectors(merged, ratio=ratio)
    out_dir = Path("logs") / "gemini"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "selectors.suggested.yaml"
    header = ("# Auto-generated by `run.py probe --steps` - candidates for gemini.selectors.*,\n"
              "# derived from the live DOM of the probed page. Review each entry against the\n"
              "# step_*.json/html dumps (or derive exact XPaths from each button's 'html' field),\n"
              "# then paste the winners into config.yaml under gemini.selectors.\n")
    body = yaml.safe_dump({"gemini": {"selectors": sugg}}, sort_keys=True, allow_unicode=True)
    out_path.write_text(header + body, encoding="utf-8")
    log.info("suggested selectors for %s -> %s (%d action keys)",
             cfg.get("gemini.url"), out_path, len(sugg))
    return 0


def _common(sp: argparse.ArgumentParser) -> None:
    """Flags usable before OR after the subcommand (SUPPRESS keeps the global value)."""
    sp.add_argument("--config", default=argparse.SUPPRESS)
    sp.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS)
    sp.add_argument("--headed", action="store_true", default=argparse.SUPPRESS)
    sp.add_argument("--force", action="store_true", default=argparse.SUPPRESS)
    sp.add_argument("--limit", type=int, default=argparse.SUPPRESS)
    sp.add_argument("--notes", default=argparse.SUPPRESS)
    sp.add_argument("--asins", default=argparse.SUPPRESS)
    sp.add_argument("--asin", default=argparse.SUPPRESS)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Amazon ASIN -> 8-image compliant bundle (Gemini web)")
    _common(p)
    p.set_defaults(config=None, dry_run=False, headed=False, force=False, limit=0,
                   notes="", asins=None, asin=None)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("login", help="one-time Google login into the persistent profile")
    _common(sp)
    sp.add_argument("--gemini", action="store_true",
                    help="log into the GEMINI own-Chrome profile copy instead of the shared one")

    for name, helptext in (("scrape", "crawl products + download base images"),
                           ("generate", "build prompts + generate 8 images"),
                           ("all", "scrape + generate")):
        _common(sub.add_parser(name, help=helptext))

    _common(sub.add_parser("one", help="single ASIN, full pipeline"))
    _common(sub.add_parser("clean", help="pass generated images through the watermark remover"))

    sp = sub.add_parser("probe", help="dump Gemini page diagnostics + suggested selectors (for /images etc.)")
    _common(sp)
    sp.add_argument("--interactive", action="store_true",
                    help="headed: click around in the browser, press Enter between dumps")
    sp.add_argument("--url", default=None,
                    help="page to probe (default: gemini.url from config, e.g. https://gemini.google.com/images)")
    sp.add_argument("--steps", action="store_true",
                    help="capture one tagged dump per UI action (home/attach/model picker/aspect/image)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(log_file=Path("logs/run.log"))

    if args.headed:
        import os

        os.environ["HEADED"] = "1"
    try:
        if args.cmd == "login":
            return cmd_login(args)
        if args.cmd == "scrape":
            return cmd_scrape(args)
        if args.cmd == "generate":
            return cmd_generate(args)
        if args.cmd in ("all", "one"):
            return cmd_all(args)
        if args.cmd == "clean":
            return cmd_clean(args)
        if args.cmd == "probe":
            return cmd_probe(args)
    except KeyboardInterrupt:
        log.warning("interrupted")
        return 130
    except ModuleNotFoundError as exc:
        if "playwright" in str(exc):
            log.error("Playwright is not installed. Run:\n"
                      "  pip install -r requirements.txt\n"
                      "  python -m playwright install chromium")
            return 2
        log.error("missing dependency: %s", exc)
        return 2
    except Exception:  # noqa: BLE001
        log.error("fatal:\n%s", traceback.format_exc())
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
