from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from ap_radio_monitor.config import load_config
from ap_radio_monitor.models import APBalanceConfig


DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitor AP radio client distribution from a Catalyst 9800 WLC."
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to config.yaml")
    parser.add_argument("--refresh", type=int, help="Live refresh interval in seconds")
    parser.add_argument("--once", action="store_true", help="Print one snapshot and exit")
    parser.add_argument(
        "--only-imbalanced",
        action="store_true",
        help="Only show APs currently scored as imbalanced",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    app_config = load_config(args.config)
    balance_config = _override_balance_config(
        app_config.ap_balance,
        refresh=args.refresh,
        only_imbalanced=args.only_imbalanced,
    )

    from ap_radio_monitor.app import run_live, run_once

    console = Console()
    if args.once:
        run_once(app_config.wlc, balance_config, console)
    else:
        run_live(app_config.wlc, balance_config, console)
    return 0


def _override_balance_config(
    config: APBalanceConfig, refresh: int | None, only_imbalanced: bool
) -> APBalanceConfig:
    return APBalanceConfig(
        refresh_seconds=refresh if refresh is not None else config.refresh_seconds,
        include=config.include,
        exclude=config.exclude,
        included_slots=config.included_slots,
        excluded_slots=config.excluded_slots,
        only_imbalanced=only_imbalanced or config.only_imbalanced,
        min_total_clients=config.min_total_clients,
        ratio_threshold=config.ratio_threshold,
        min_difference=config.min_difference,
        include_zero_client_slots=config.include_zero_client_slots,
    )
