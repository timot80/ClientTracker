from __future__ import annotations

import argparse
import pathlib
import sys

from .app import ClientTrackerApp
from .config import load_config
from .infra import is_valid_mac

CONFIG_PATH = pathlib.Path(__file__).resolve().parent.parent / "config.yaml"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Track a wireless client from Cisco infrastructure and/or local OS telemetry."
    )
    parser.add_argument("mac", nargs="?", help="Wireless client MAC address")
    parser.add_argument(
        "--mode",
        choices=("infra", "local", "combined"),
        default=None,
        help="Tracking mode. Defaults to infra when MAC is supplied, local otherwise.",
    )
    parser.add_argument("--log", help="Optional CSV log path")
    parser.add_argument("--check", action="store_true", help="Validate local setup and exit")
    args = parser.parse_args(argv)
    if args.mode is None:
        args.mode = "infra" if args.mac else "local"
    if args.mode in ("infra", "combined") and not args.mac and not args.check:
        parser.error(f"--mode {args.mode} requires a MAC address")
    if args.mac and not is_valid_mac(args.mac):
        parser.error(f"Invalid MAC address format: {args.mac}")
    return args


def main(argv: list[str] | None = None):
    args = parse_args(argv)
    require_infra = args.mode in ("infra", "combined") and not args.check
    config = load_config(CONFIG_PATH, require_infra=require_infra)
    if args.check:
        print("Python dependencies import successfully.")
        if CONFIG_PATH.exists():
            print(f"Config found: {CONFIG_PATH}")
        else:
            print(f"Config not found: {CONFIG_PATH}")
        return
    app = ClientTrackerApp(args.mode, config, mac=args.mac, log_path=args.log)
    app.run()


if __name__ == "__main__":
    main(sys.argv[1:])
