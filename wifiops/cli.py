from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import subprocess
import sys
from collections.abc import Sequence


DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wifiops",
        description="Wireless operations tools for Catalyst 9800 and local client telemetry.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    credentials = subcommands.add_parser("credentials", help="Manage OS keyring credential profiles")
    credential_subcommands = credentials.add_subparsers(dest="credentials_command", required=True)
    set_profile = credential_subcommands.add_parser(
        "set-profile",
        help="Store or update a credential profile",
        description="Store or update a credential profile in config.yaml and the OS keyring.",
    )
    set_profile.add_argument("profile", help="Credential profile name")
    set_profile.add_argument("--username", required=True, help="Profile username")
    set_profile.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to config.yaml")

    show_profiles = credential_subcommands.add_parser(
        "show-profiles",
        help="List credential profiles from config.yaml",
    )
    show_profiles.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to config.yaml")

    delete_profile = credential_subcommands.add_parser(
        "delete-profile",
        help="Delete a credential profile",
    )
    delete_profile.add_argument("profile", help="Credential profile name")
    delete_profile.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to config.yaml")

    c9800 = subcommands.add_parser("c9800", help="Cisco Catalyst 9800 tools")
    c9800_subcommands = c9800.add_subparsers(dest="c9800_command", required=True)

    radio = c9800_subcommands.add_parser(
        "radio",
        help="Monitor AP radio client distribution",
        description="Monitor AP radio client distribution from a Catalyst 9800 WLC.",
    )
    radio.add_argument("--config", help="Path to config.yaml")
    radio.add_argument("--refresh", type=int, help="Live refresh interval in seconds")
    radio.add_argument("--once", action="store_true", help="Print one snapshot and exit")
    visibility = radio.add_mutually_exclusive_group()
    visibility.add_argument(
        "--only-imbalanced",
        action="store_true",
        help="Only show APs currently scored as imbalanced",
    )
    visibility.add_argument(
        "--only-problem",
        action="store_true",
        help="Only show imbalanced, busy-idle, warning, and no-data APs",
    )
    idle = radio.add_mutually_exclusive_group()
    idle.add_argument("--show-idle", action="store_true", help="Show clean idle APs")
    idle.add_argument("--hide-idle", action="store_true", help="Hide clean idle APs")
    radio.add_argument("--limit", type=int, help="Maximum AP rows to display")
    radio.add_argument("--columns", type=int, choices=(1, 2), help="AP row groups to display")
    radio.add_argument(
        "--auto-exclude-admin-down-slots",
        action="store_true",
        help="Query AP slot config and ignore admin-disabled/down 0-client slots",
    )
    radio.add_argument(
        "--busy-idle-util",
        type=int,
        help="Utilization threshold for zero-client APs to show BUSY-IDLE",
    )

    ap_ports = c9800_subcommands.add_parser(
        "ap-ports",
        help="Audit AP Ethernet port speed and duplex",
        description="Audit AP Ethernet port speed and duplex from a Catalyst 9800 WLC.",
    )
    ap_ports.add_argument("--config", help="Path to config.yaml")
    ap_ports.add_argument("--include", action="append", default=[], help="AP name wildcard to include")
    ap_ports.add_argument("--exclude", action="append", default=[], help="AP name wildcard to exclude")
    ap_ports.add_argument("--all", action="store_true", help="Show all AP ports, including healthy rows")
    ap_ports.add_argument("--speed-threshold", type=int, help="Minimum expected negotiated speed in Mbps")

    c9800_client = c9800_subcommands.add_parser(
        "client",
        help="Track a wireless client from Catalyst 9800 infrastructure",
        description="Track a wireless client from Catalyst 9800 infrastructure.",
    )
    c9800_client.add_argument("mac", help="Wireless client MAC address")
    c9800_client.add_argument(
        "--mode",
        choices=("infra", "combined"),
        default="infra",
        help="Tracking mode. Defaults to infra.",
    )
    c9800_client.add_argument("--log", help="Optional CSV log path")
    c9800_client.add_argument("--interval", type=float, help="Polling interval in seconds")

    client = subcommands.add_parser("client", help="Local client telemetry tools")
    client_subcommands = client.add_subparsers(dest="client_command", required=True)

    local = client_subcommands.add_parser(
        "local",
        help="Show local Wi-Fi telemetry",
        description="Show local Wi-Fi telemetry from the machine running wifiops.",
    )
    local.add_argument("--log", help="Optional CSV log path")
    local.add_argument("--interval", type=float, help="Polling interval in seconds")

    subcommands.add_parser("check", help="Validate local client tracker setup and exit")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "credentials":
        return _credentials_command(args, parser)

    if args.command == "c9800" and args.c9800_command == "radio":
        from ap_radio_monitor.cli import main as radio_main

        return _exit_code(radio_main(_delegated_args(argv, "radio")))

    if args.command == "c9800" and args.c9800_command == "ap-ports":
        from ap_port_audit.cli import main as ap_ports_main

        return _exit_code(ap_ports_main(_delegated_args(argv, "ap-ports")))

    if args.command == "c9800" and args.c9800_command == "client":
        from client_tracker.cli import main as client_main

        if args.mode == "combined" and not _macos_sudo_ready():
            return _macos_sudo_error()
        translated = [args.mac, "--mode", args.mode]
        if args.interval is not None:
            translated.extend(["--interval", _format_number(args.interval)])
        if args.log is not None:
            translated.extend(["--log", args.log])
        return _exit_code(client_main(translated))

    if args.command == "client" and args.client_command == "local":
        from client_tracker.cli import main as client_main

        if not _macos_sudo_ready():
            return _macos_sudo_error()
        translated = ["--mode", "local"]
        if args.interval is not None:
            translated.extend(["--interval", _format_number(args.interval)])
        if args.log is not None:
            translated.extend(["--log", args.log])
        return _exit_code(client_main(translated))

    if args.command == "check":
        from client_tracker.cli import main as client_main

        return _exit_code(client_main(["--check"]))

    parser.error("unknown command")


def _credentials_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    from wifiops.credentials import CredentialConfigError, delete_profile, list_profiles, set_profile, validate_profile_name

    try:
        if args.credentials_command == "set-profile":
            validate_profile_name(args.profile)
            password = getpass.getpass("Password: ")
            enable = getpass.getpass("Enable secret (optional): ")
            set_profile(args.config, args.profile, args.username, password, enable)
            print(f"Stored credential profile '{args.profile}' in {args.config}")
            return 0

        if args.credentials_command == "show-profiles":
            profiles = list_profiles(args.config)
            if not profiles:
                print("No credential profiles configured.")
                return 0
            for profile, username in profiles:
                print(f"{profile}\t{username}")
            return 0

        if args.credentials_command == "delete-profile":
            deleted = delete_profile(args.config, args.profile)
            if deleted:
                print(
                    f"Deleted credential profile '{args.profile}'. "
                    "Existing device credential_profile references may now be invalid."
                )
            else:
                print(f"Credential profile '{args.profile}' was not found.")
            return 0
    except CredentialConfigError as exc:
        parser.error(str(exc))

    parser.error("unknown credentials command")


def _delegated_args(argv: list[str], command: str) -> list[str]:
    index = argv.index(command)
    return argv[index + 1 :]


def _exit_code(value: object) -> int:
    if value is None:
        return 0
    return int(value)


def _format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return str(value)


def _macos_sudo_ready() -> bool:
    if sys.platform != "darwin":
        return True
    if os.geteuid() == 0:
        return True
    result = subprocess.run(
        ["sudo", "-n", "-v"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _macos_sudo_error() -> int:
    print(
        "macOS local telemetry requires sudo for 'wdutil info'. "
        "Run 'sudo -v' first, then retry the wifiops command.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
