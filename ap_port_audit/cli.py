from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from rich.console import Console

from ap_port_audit.app import run_multi
from ap_port_audit.config import load_config
from wifiops.wlc_targets import select_wlc_targets


DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit Catalyst 9800 AP Ethernet port speed and duplex."
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to config.yaml")
    parser.add_argument("--include", action="append", default=[], help="AP name wildcard to include")
    parser.add_argument("--exclude", action="append", default=[], help="AP name wildcard to exclude")
    parser.add_argument("--all", action="store_true", help="Show all AP ports, including healthy rows")
    parser.add_argument(
        "--speed-threshold",
        type=int,
        help="Minimum expected negotiated speed in Mbps. Defaults to config or 1000.",
    )
    parser.add_argument("--wlc", action="append", default=[], help="Named WLC to include; repeatable")
    parser.add_argument("--wlc-concurrency", type=int, help="Maximum WLCs to query concurrently")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    console = Console()
    try:
        config = load_config(args.config)
        audit_config = config.ap_ports
        if args.include:
            audit_config = replace(audit_config, include=tuple(args.include))
        if args.exclude:
            audit_config = replace(audit_config, exclude=tuple(args.exclude))
        if args.all:
            audit_config = replace(audit_config, show_all=True)
        if args.speed_threshold is not None:
            audit_config = replace(audit_config, speed_threshold=args.speed_threshold)
        targets = select_wlc_targets(config.wlc_targets, tuple(args.wlc))
        concurrency = args.wlc_concurrency if args.wlc_concurrency is not None else config.wlc_concurrency
        return run_multi(targets, audit_config, concurrency, console)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
