from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import replace

from rich.console import Console

from ap_filesystem_audit.app import run_audit
from ap_filesystem_audit.config import load_config
from wifiops.wlc_targets import select_wlc_targets
from wifiops.config_paths import default_config_path


DEFAULT_CONFIG = default_config_path(__file__)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit AP filesystem usage.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to config.yaml")
    parser.add_argument("--wlc", action="append", default=[], help="Named WLC to include; repeatable")
    parser.add_argument("--include", action="append", default=[], help="AP name wildcard to include")
    parser.add_argument("--exclude", action="append", default=[], help="AP name wildcard to exclude")
    parser.add_argument("--ap-name", action="append", default=[], help="Exact AP name to include; repeatable")
    parser.add_argument("--ap-host", action="append", default=[], help="Exact AP IP/host to include; repeatable")
    parser.add_argument("--min-used-percent", type=int, help="Use%% threshold for HIGH status")
    parser.add_argument("--all", action="store_true", help="Show all filesystems, including OK rows")
    parser.add_argument("--wlc-concurrency", type=int, help="Maximum WLCs to query concurrently")
    parser.add_argument("--ap-concurrency", type=int, help="Maximum APs to query concurrently")
    parser.add_argument("--output", help="Optional CSV output path")
    parser.add_argument(
        "--reload-full-tmp",
        action="store_true",
        help="Reload APs only when the /tmp filesystem is exactly 100%% used",
    )
    parser.add_argument(
        "--confirm-reload-full-tmp",
        action="store_true",
        help="Confirm AP reloads for --reload-full-tmp",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    console = Console()
    try:
        if args.reload_full_tmp and not args.confirm_reload_full_tmp:
            raise ValueError("--reload-full-tmp requires --confirm-reload-full-tmp")
        config = load_config(args.config)
        audit_config = config.audit
        if args.include:
            audit_config = replace(audit_config, include=tuple(args.include))
        if args.exclude:
            audit_config = replace(audit_config, exclude=tuple(args.exclude))
        if args.ap_name:
            audit_config = replace(audit_config, ap_names=tuple(args.ap_name))
        if args.ap_host:
            audit_config = replace(audit_config, ap_hosts=tuple(args.ap_host))
        if args.min_used_percent is not None:
            audit_config = replace(audit_config, min_used_percent=args.min_used_percent)
        if args.all:
            audit_config = replace(audit_config, show_all=True)
        if args.ap_concurrency is not None:
            audit_config = replace(audit_config, ap_concurrency=args.ap_concurrency)
        if args.output:
            audit_config = replace(audit_config, output=args.output)
        if args.reload_full_tmp:
            audit_config = replace(
                audit_config,
                reload_full_tmp=True,
                confirm_reload_full_tmp=args.confirm_reload_full_tmp,
            )

        targets = select_wlc_targets(config.wlc_targets, tuple(args.wlc))
        concurrency = args.wlc_concurrency if args.wlc_concurrency is not None else config.wlc_concurrency
        return run_audit(targets, config.ap_credentials, audit_config, concurrency, console)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
