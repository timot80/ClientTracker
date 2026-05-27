from __future__ import annotations

import argparse
import sys
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
    visibility = parser.add_mutually_exclusive_group()
    visibility.add_argument(
        "--only-imbalanced",
        action="store_true",
        default=None,
        help="Only show APs currently scored as imbalanced",
    )
    visibility.add_argument(
        "--only-problem",
        action="store_true",
        default=None,
        help="Only show imbalanced, busy-idle, warning, and no-data APs",
    )
    idle = parser.add_mutually_exclusive_group()
    idle.add_argument("--show-idle", action="store_true", default=None, help="Show clean idle APs")
    idle.add_argument("--hide-idle", action="store_true", default=None, help="Hide clean idle APs")
    parser.add_argument("--limit", type=int, help="Maximum AP rows to display")
    parser.add_argument("--columns", type=int, choices=(1, 2), help="AP row groups to display")
    parser.add_argument(
        "--auto-exclude-admin-down-slots",
        action="store_true",
        default=None,
        help="Query AP slot config and ignore admin-disabled/down 0-client slots",
    )
    parser.add_argument(
        "--include-slot",
        type=int,
        action="append",
        default=None,
        help="Radio slot to show and score; may be repeated",
    )
    parser.add_argument(
        "--exclude-slot",
        type=int,
        action="append",
        default=None,
        help="Radio slot to hide and ignore; may be repeated",
    )
    parser.add_argument(
        "--busy-idle-util",
        type=int,
        help="Utilization threshold for zero-client APs to show BUSY-IDLE",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    console = Console(stderr=True)
    try:
        app_config = load_config(args.config)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1
    balance_config = _override_balance_config(
        app_config.ap_balance,
        refresh=args.refresh,
        only_imbalanced=args.only_imbalanced,
        only_problem=args.only_problem,
        show_idle=args.show_idle,
        hide_idle=args.hide_idle,
        limit=args.limit,
        display_columns=args.columns,
        auto_exclude_admin_down_slots=args.auto_exclude_admin_down_slots,
        included_slots=args.include_slot,
        excluded_slots=args.exclude_slot,
        busy_idle_utilization=args.busy_idle_util,
    )

    from ap_radio_monitor.app import run_live, run_once

    console = Console()
    if args.once:
        try:
            run_once(app_config.wlc, balance_config, console)
        except Exception as exc:
            print(f"Failed to start AP radio monitor: {exc}", file=sys.stderr)
            return 1
    else:
        try:
            run_live(app_config.wlc, balance_config, console)
        except Exception as exc:
            print(f"Failed to start AP radio monitor: {exc}", file=sys.stderr)
            return 1
    return 0


def _override_balance_config(
    config: APBalanceConfig,
    refresh: int | None,
    only_imbalanced: bool | None,
    only_problem: bool | None,
    show_idle: bool | None,
    hide_idle: bool | None,
    limit: int | None,
    display_columns: int | None,
    auto_exclude_admin_down_slots: bool | None,
    included_slots: list[int] | None,
    excluded_slots: list[int] | None,
    busy_idle_utilization: int | None,
) -> APBalanceConfig:
    return APBalanceConfig(
        refresh_seconds=refresh if refresh is not None else config.refresh_seconds,
        include=config.include,
        exclude=config.exclude,
        included_slots=tuple(included_slots) if included_slots is not None else config.included_slots,
        excluded_slots=tuple(excluded_slots) if excluded_slots is not None else config.excluded_slots,
        only_imbalanced=config.only_imbalanced if only_imbalanced is None else only_imbalanced,
        only_problem=config.only_problem if only_problem is None else only_problem,
        show_idle=config.show_idle if show_idle is None else show_idle,
        hide_idle=config.hide_idle if hide_idle is None else hide_idle,
        limit=limit if limit is not None else config.limit,
        display_columns=display_columns if display_columns is not None else config.display_columns,
        auto_exclude_admin_down_slots=(
            config.auto_exclude_admin_down_slots
            if auto_exclude_admin_down_slots is None
            else auto_exclude_admin_down_slots
        ),
        min_total_clients=config.min_total_clients,
        busy_idle_utilization=(
            busy_idle_utilization
            if busy_idle_utilization is not None
            else config.busy_idle_utilization
        ),
        ratio_threshold=config.ratio_threshold,
        min_difference=config.min_difference,
        include_zero_client_slots=config.include_zero_client_slots,
    )
