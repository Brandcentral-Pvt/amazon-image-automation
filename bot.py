#!/usr/bin/env python3
"""OpenMaus bot entry point for the ASIN -> 8-image pipeline.

Usage:
  python bot.py status <ASIN>          # status summary for one ASIN
  python bot.py generate <ASINs...>    # generate images for ASINs
  python bot.py clean <ASIN>           # re-run watermark cleanup
  python bot.py login                  # one-time Google sign-in (delegates to run.py)

Results are printed as JSON for the bot framework to consume.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import Config, ConfigError, load_config  # noqa: E402
from src.bot_commands import cmd_status, cmd_generate, cmd_clean  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 1

    cmd = argv[0]
    args = argv[1:]

    try:
        cfg = load_config()
    except (ConfigError, FileNotFoundError) as exc:
        print(json.dumps({"error": f"config: {exc}"}))
        return 2

    try:
        if cmd == "status":
            if len(args) != 1:
                print(json.dumps({"error": "usage: bot.py status <ASIN>"}))
                return 2
            result = cmd_status(args[0], cfg)

        elif cmd == "generate":
            if not args:
                print(json.dumps({"error": "usage: bot.py generate <ASIN> [ASIN...]"}))
                return 2
            force = "--force" in args
            asins = [a for a in args if a != "--force"]
            result = cmd_generate(asins, cfg, force=force)

        elif cmd == "clean":
            if len(args) != 1:
                print(json.dumps({"error": "usage: bot.py clean <ASIN>"}))
                return 2
            result = cmd_clean(args[0], cfg)

        else:
            print(json.dumps({"error": f"unknown command: {cmd}"}))
            print(__doc__)
            return 2

    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"command {cmd} failed: {exc}"}))
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
