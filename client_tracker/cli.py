from __future__ import annotations

import argparse
import pathlib
import sys

from .app import ClientTrackerApp
from .config import load_config
from .infra import is_valid_mac
from wifiops.config_paths import default_config_path

CONFIG_PATH = default_config_path(__file__)
DEFAULT_INTERVALS = {
    "infra": 5.0,
    "local": 1.0,
    "combined": 2.0,
}


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
    parser.add_argument("--config", default=str(CONFIG_PATH), help="Path to config.yaml")
    parser.add_argument("--wlc", action="append", default=[], help="Named WLC to include; repeatable")
    parser.add_argument(
        "--interval",
        type=float,
        default=None,
        help="Polling interval in seconds. Defaults: local=1, combined=2, infra=5.",
    )
    parser.add_argument("--check", action="store_true", help="Validate local setup and exit")
    args = parser.parse_args(argv)
    if args.mode is None:
        args.mode = "infra" if args.mac else "local"
    if args.interval is None:
        args.interval = DEFAULT_INTERVALS[args.mode]
    if args.interval <= 0:
        parser.error("--interval must be greater than 0")
    if args.mode in ("infra", "combined") and not args.mac and not args.check:
        parser.error(f"--mode {args.mode} requires a MAC address")
    if args.mac and not is_valid_mac(args.mac):
        parser.error(f"Invalid MAC address format: {args.mac}")
    return args


def main(argv: list[str] | None = None):
    args = parse_args(argv)
    require_infra = args.mode in ("infra", "combined") and not args.check
    config_path = pathlib.Path(args.config)
    config = load_config(config_path, require_infra=require_infra, wlc_names=tuple(args.wlc))
    if args.check:
        print("Python dependencies import successfully.")
        if config_path.exists():
            print(f"Config found: {config_path}")
        else:
            print(f"Config not found: {config_path}")
        return
    app = ClientTrackerApp(
        args.mode,
        config,
        mac=args.mac,
        log_path=args.log,
        poll_interval=args.interval,
    )
    app.run()


if __name__ == "__main__":
    main(sys.argv[1:])
