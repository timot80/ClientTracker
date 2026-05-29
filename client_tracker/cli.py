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
    parser.add_argument(
        "--local-source",
        choices=("os", "android"),
        default="os",
        help="Local telemetry source. Defaults to os.",
    )
    parser.add_argument(
        "--android-latest-url",
        default="",
        help="URL for latest Android telemetry JSON when --local-source android is used.",
    )
    parser.add_argument(
        "--android-receiver-url",
        default="",
        help="Receiver URL printed by wifiops probe receive.",
    )
    parser.add_argument(
        "--android-session",
        default="",
        help="Android probe receiver session ID.",
    )
    args = parser.parse_args(argv)
    if args.mode is None:
        args.mode = "infra" if args.mac else "local"
    if args.interval is None:
        args.interval = DEFAULT_INTERVALS[args.mode]
    if args.interval <= 0:
        parser.error("--interval must be greater than 0")
    if args.mode in ("infra", "combined") and not args.mac and not args.check:
        parser.error(f"--mode {args.mode} requires a MAC address")
    if args.local_source == "android" and not args.android_latest_url:
        if bool(args.android_receiver_url) != bool(args.android_session):
            parser.error("--android-receiver-url and --android-session must be supplied together")
        if args.android_receiver_url and args.android_session:
            args.android_latest_url = build_android_latest_url(args.android_receiver_url, args.android_session)
    if args.mode in ("local", "combined") and args.local_source == "android" and not args.android_latest_url and not args.check:
        parser.error(
            "--android-latest-url or --android-receiver-url with --android-session is required "
            "when --local-source android"
        )
    if args.mac and not is_valid_mac(args.mac):
        parser.error(f"Invalid MAC address format: {args.mac}")
    return args


def build_android_latest_url(receiver_url: str, session_id: str) -> str:
    return f"{receiver_url.rstrip('/')}/api/v1/sessions/{session_id}/latest"


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
        local_source=args.local_source,
        android_latest_url=args.android_latest_url,
    )
    app.run()


if __name__ == "__main__":
    main(sys.argv[1:])
