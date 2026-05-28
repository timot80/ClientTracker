#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import fnmatch
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from netmiko import ConnectHandler
except ImportError:  # pragma: no cover - operator guidance path
    ConnectHandler = None

try:
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.table import Table
except ImportError:  # pragma: no cover - operator guidance path
    Console = None
    Group = None
    Panel = None
    Table = None

try:
    import yaml
except ImportError:  # pragma: no cover - operator guidance path
    yaml = None


@dataclass(frozen=True)
class WLCConfig:
    host: str
    username: str
    password: str
    enable: str = ""
    read_timeout: int = 90


@dataclass(frozen=True)
class WlcTarget:
    name: str
    config: WLCConfig


@dataclass(frozen=True)
class APCredentials:
    username: str
    password: str
    enable: str = ""


@dataclass(frozen=True)
class APFilesystemAuditConfig:
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    ap_names: tuple[str, ...] = ()
    ap_hosts: tuple[str, ...] = ()
    min_used_percent: int = 95
    show_all: bool = False
    ap_concurrency: int = 20
    output: str = ""
    reload_full_tmp: bool = False
    confirm_reload_full_tmp: bool = False


@dataclass(frozen=True)
class APFilesystemConfig:
    wlc_targets: list[WlcTarget]
    ap_credentials: APCredentials
    audit: APFilesystemAuditConfig = field(default_factory=APFilesystemAuditConfig)
    wlc_concurrency: int = 3


@dataclass(frozen=True)
class APTarget:
    wlc_name: str
    wlc_host: str
    name: str
    host: str


@dataclass(frozen=True)
class APFilesystemRow:
    wlc_name: str = ""
    wlc_host: str = ""
    ap_name: str = ""
    ap_host: str = ""
    filesystem: str = ""
    mount: str = ""
    size: str = ""
    used: str = ""
    available: str = ""
    used_percent: int | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class APFilesystemFailure:
    wlc_name: str = ""
    wlc_host: str = ""
    ap_name: str = ""
    ap_host: str = ""
    message: str = ""


@dataclass(frozen=True)
class APReloadResult:
    wlc_name: str = ""
    wlc_host: str = ""
    ap_name: str = ""
    ap_host: str = ""
    action: str = ""
    output: str = ""


@dataclass(frozen=True)
class APFilesystemSnapshot:
    rows: list[APFilesystemRow] = field(default_factory=list)
    failures: list[APFilesystemFailure] = field(default_factory=list)
    parser_warnings: list[str] = field(default_factory=list)
    reload_results: list[APReloadResult] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


HEADER_RE = re.compile(r"^Filesystem\s+Size\s+Used\s+Available\s+Use%\s+Mounted\s+on$")
PROMPT_RE = re.compile(r"^[A-Za-z0-9_.:-]+[>#]\s*$")
IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
FS_ROW_RE = re.compile(
    r"^(?P<filesystem>\S+)\s+"
    r"(?P<size>\S+)\s+"
    r"(?P<used>\S+)\s+"
    r"(?P<available>\S+)\s+"
    r"(?P<used_percent>\d+)%\s+"
    r"(?P<mount>\S+)$"
)

CSV_FIELDS = [
    "record_type",
    "wlc_name",
    "wlc_host",
    "ap_name",
    "ap_host",
    "filesystem",
    "mount",
    "size",
    "used",
    "available",
    "used_percent",
    "status",
    "notes",
    "reload_action",
    "reload_output",
    "error",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Standalone AP filesystem audit.")
    parser.add_argument("--config", default="ap_filesystem_audit_standalone.yaml", help="Path to YAML config")
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


def load_config(path: str | Path) -> APFilesystemConfig:
    if yaml is None:
        raise RuntimeError("Missing dependency: pip install pyyaml")
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise ValueError(f"Config file not found: {cfg_path}")
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("Config file must contain a YAML mapping")

    ap_raw = _mapping(raw.get("ap") or {}, "ap")
    ap_credentials = APCredentials(
        username=str(ap_raw.get("username") or ""),
        password=str(ap_raw.get("password") or ""),
        enable=str(ap_raw.get("enable") or ""),
    )
    if not ap_credentials.username.strip():
        raise ValueError("Missing required config value: ap.username")
    if not ap_credentials.password.strip():
        raise ValueError("Missing required config value: ap.password")

    wifiops_raw = _mapping(raw.get("wifiops") or {}, "wifiops")
    fs_raw = _mapping(raw.get("ap_filesystems") or {}, "ap_filesystems")
    return APFilesystemConfig(
        wlc_targets=_load_wlc_targets(raw),
        ap_credentials=ap_credentials,
        audit=APFilesystemAuditConfig(
            include=_str_tuple(fs_raw.get("include", ())),
            exclude=_str_tuple(fs_raw.get("exclude", ())),
            min_used_percent=int(fs_raw.get("min_used_percent", 95)),
            show_all=bool(fs_raw.get("show_all", False)),
            ap_concurrency=int(fs_raw.get("ap_concurrency", 20)),
        ),
        wlc_concurrency=int(wifiops_raw.get("wlc_concurrency", 3)),
    )


def _load_wlc_targets(raw: dict[str, Any]) -> list[WlcTarget]:
    if raw.get("wlcs") is not None:
        wlcs = raw["wlcs"]
        if not isinstance(wlcs, list):
            raise ValueError("wlcs must be a list")
        targets = []
        for index, item in enumerate(wlcs, start=1):
            cfg = _mapping(item, "wlcs item")
            name = str(cfg.get("name") or f"wlc-{index}")
            targets.append(WlcTarget(name=name, config=_wlc_config(cfg)))
        return targets
    wlc_raw = _mapping(raw.get("wlc") or {}, "wlc")
    return [WlcTarget(name=str(wlc_raw.get("name") or "wlc"), config=_wlc_config(wlc_raw))]


def _wlc_config(raw: dict[str, Any]) -> WLCConfig:
    return WLCConfig(
        host=str(raw.get("host") or ""),
        username=str(raw.get("username") or ""),
        password=str(raw.get("password") or ""),
        enable=str(raw.get("enable") or ""),
        read_timeout=int(raw.get("read_timeout", 90)),
    )


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping")
    return value


def _str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


def parse_filesystems(output: str) -> APFilesystemSnapshot:
    rows: list[APFilesystemRow] = []
    warnings: list[str] = []
    in_table = False
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or PROMPT_RE.match(stripped):
            continue
        if HEADER_RE.match(stripped):
            in_table = True
            continue
        if not in_table:
            continue
        match = FS_ROW_RE.match(stripped)
        if match:
            rows.append(
                APFilesystemRow(
                    filesystem=match.group("filesystem"),
                    size=match.group("size"),
                    used=match.group("used"),
                    available=match.group("available"),
                    used_percent=int(match.group("used_percent")),
                    mount=match.group("mount"),
                )
            )
        else:
            warnings.append(f"Malformed filesystem row: {stripped}")
    return APFilesystemSnapshot(rows=rows, parser_warnings=warnings)


def parse_show_ap_summary(output: str, target: WlcTarget) -> list[APTarget]:
    aps = []
    seen: set[tuple[str, str]] = set()
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("-"):
            continue
        if stripped.lower().startswith(("ap name", "number of", "total")):
            continue
        fields = stripped.split()
        match = IP_RE.search(stripped)
        if len(fields) < 2 or not match:
            continue
        ap = APTarget(target.name, target.config.host, fields[0], match.group(0))
        key = (ap.name, ap.host)
        if key not in seen:
            aps.append(ap)
            seen.add(key)
    return aps


def discover_aps_from_wlc(target: WlcTarget) -> list[APTarget]:
    if ConnectHandler is None:
        raise RuntimeError("Missing dependency: pip install netmiko rich pyyaml")
    conn = ConnectHandler(
        device_type="cisco_ios",
        host=target.config.host,
        username=target.config.username,
        password=target.config.password,
        secret=target.config.enable,
    )
    try:
        if target.config.enable and hasattr(conn, "enable"):
            conn.enable()
        conn.send_command("terminal length 0", expect_string=r"[>#]", read_timeout=target.config.read_timeout)
        output = conn.send_command("show ap summary", expect_string=r"[>#]", read_timeout=target.config.read_timeout)
        return parse_show_ap_summary(output, target)
    finally:
        conn.disconnect()


def collect_ap_filesystems(
    target: APTarget,
    creds: APCredentials,
    config: APFilesystemAuditConfig,
) -> APFilesystemSnapshot:
    if ConnectHandler is None:
        raise RuntimeError("Missing dependency: pip install netmiko rich pyyaml")
    conn = ConnectHandler(
        device_type="cisco_ios",
        host=target.host,
        username=creds.username,
        password=creds.password,
        secret=creds.enable,
    )
    try:
        if creds.enable and hasattr(conn, "enable"):
            conn.enable()
        conn.send_command("terminal length 0", expect_string=r"[>#]")
        output = conn.send_command("sh filesystems", expect_string=r"[>#]")
        snapshot = parse_filesystems(output)
        parser_warnings = [f"{target.name}: {warning}" for warning in snapshot.parser_warnings]
        if not snapshot.rows:
            return APFilesystemSnapshot(
                failures=[
                    APFilesystemFailure(
                        target.wlc_name,
                        target.wlc_host,
                        target.name,
                        target.host,
                        "no filesystem rows parsed",
                    )
                ],
                parser_warnings=parser_warnings,
                timestamp=snapshot.timestamp,
            )
        rows = [
            replace(row, wlc_name=target.wlc_name, wlc_host=target.wlc_host, ap_name=target.name, ap_host=target.host)
            for row in snapshot.rows
        ]
        reload_results, reload_failures = _maybe_reload_full_tmp(conn, target, rows, config)
        return APFilesystemSnapshot(
            rows=rows,
            failures=[*snapshot.failures, *reload_failures],
            parser_warnings=parser_warnings,
            reload_results=reload_results,
            timestamp=snapshot.timestamp,
        )
    finally:
        conn.disconnect()


def _maybe_reload_full_tmp(
    conn,
    target: APTarget,
    rows: list[APFilesystemRow],
    config: APFilesystemAuditConfig,
) -> tuple[list[APReloadResult], list[APFilesystemFailure]]:
    if not config.reload_full_tmp:
        return [], []
    identity = {
        "wlc_name": target.wlc_name,
        "wlc_host": target.wlc_host,
        "ap_name": target.name,
        "ap_host": target.host,
    }
    if not any(row.mount == "/tmp" and row.used_percent == 100 for row in rows):
        return [], []
    try:
        output = conn.send_command_timing("reload", read_timeout=30, last_read=3)
        if "confirm" not in output.lower():
            message = f"reload confirmation prompt not received: {output}"
            return (
                [APReloadResult(**identity, action="failed", output=message)],
                [APFilesystemFailure(**identity, message=message)],
            )
        confirm_output = conn.send_command_timing("\r", read_timeout=30, last_read=3)
    except Exception as exc:
        message = f"reload failed: {exc}"
        return (
            [APReloadResult(**identity, action="failed", output=message)],
            [APFilesystemFailure(**identity, message=message)],
        )
    return (
        [
            APReloadResult(
                **identity,
                action="triggered",
                output="\n".join(part for part in (output, confirm_output) if part),
            )
        ],
        [],
    )


def row_status(row: APFilesystemRow, config: APFilesystemAuditConfig) -> str:
    if row.used_percent is None:
        return "UNKNOWN"
    if row.used_percent == 100:
        return "FULL"
    if row.used_percent >= config.min_used_percent:
        return "HIGH"
    return "OK"


def filter_ap_targets(targets: list[APTarget], config: APFilesystemAuditConfig) -> list[APTarget]:
    filtered = list(targets)
    if config.ap_names or config.ap_hosts:
        names = set(config.ap_names)
        hosts = set(config.ap_hosts)
        filtered = [target for target in filtered if target.name in names or target.host in hosts]
    if config.include:
        filtered = [target for target in filtered if any(fnmatch.fnmatchcase(target.name, p) for p in config.include)]
    if config.exclude:
        filtered = [target for target in filtered if not any(fnmatch.fnmatchcase(target.name, p) for p in config.exclude)]
    return filtered


def visible_rows(rows: list[APFilesystemRow], config: APFilesystemAuditConfig) -> list[APFilesystemRow]:
    if config.show_all:
        return list(rows)
    return [row for row in rows if row_status(row, config) != "OK"]


def build_filesystem_table(snapshot: APFilesystemSnapshot, config: APFilesystemAuditConfig):
    if Console is None:
        raise RuntimeError("Missing dependency: pip install rich")
    rows = visible_rows(snapshot.rows, config)
    renderables = []
    if rows:
        table = Table(title=f"{len(rows)} shown / {len(snapshot.rows)} filesystems | AP Filesystem Audit")
        for column in ("WLC", "AP", "AP IP", "Filesystem", "Mount", "Size", "Used", "Available", "Use%", "Status", "Notes"):
            table.add_column(column)
        for row in rows:
            table.add_row(
                row.wlc_name,
                row.ap_name,
                row.ap_host,
                row.filesystem,
                row.mount,
                row.size,
                row.used,
                row.available,
                "" if row.used_percent is None else f"{row.used_percent}%",
                row_status(row, config),
                "; ".join(row.notes),
            )
        renderables.append(table)
    else:
        renderables.append(Panel("No AP filesystem issues found", title="AP Filesystem Audit"))
    if snapshot.failures:
        failures = Table(title="Failures")
        for column in ("WLC", "AP", "AP IP", "Error"):
            failures.add_column(column)
        for failure in snapshot.failures:
            failures.add_row(failure.wlc_name, failure.ap_name, failure.ap_host, failure.message)
        renderables.append(failures)
    if snapshot.parser_warnings:
        warnings = Table(title="Parser Warnings")
        warnings.add_column("Status")
        warnings.add_column("Warning")
        for warning in snapshot.parser_warnings:
            warnings.add_row("UNKNOWN", warning)
        renderables.append(warnings)
    if snapshot.reload_results:
        reloads = Table(title="Reload Results")
        for column in ("WLC", "AP", "AP IP", "Action", "Output"):
            reloads.add_column(column)
        for result in snapshot.reload_results:
            reloads.add_row(result.wlc_name, result.ap_name, result.ap_host, result.action, result.output)
        renderables.append(reloads)
    return Group(*renderables)


def write_csv(path: str | Path, snapshot: APFilesystemSnapshot, config: APFilesystemAuditConfig) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    reloads_by_ap = {
        (result.wlc_name, result.wlc_host, result.ap_name, result.ap_host): result
        for result in snapshot.reload_results
    }
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in visible_rows(snapshot.rows, config):
            reload_result = reloads_by_ap.get((row.wlc_name, row.wlc_host, row.ap_name, row.ap_host))
            writer.writerow(
                {
                    "record_type": "filesystem",
                    "wlc_name": row.wlc_name,
                    "wlc_host": row.wlc_host,
                    "ap_name": row.ap_name,
                    "ap_host": row.ap_host,
                    "filesystem": row.filesystem,
                    "mount": row.mount,
                    "size": row.size,
                    "used": row.used,
                    "available": row.available,
                    "used_percent": "" if row.used_percent is None else row.used_percent,
                    "status": row_status(row, config),
                    "notes": "; ".join(row.notes),
                    "reload_action": "" if reload_result is None else reload_result.action,
                    "reload_output": "" if reload_result is None else reload_result.output,
                    "error": "",
                }
            )
        for failure in snapshot.failures:
            _write_metadata_row(writer, "failure", "", failure.message, failure)
        for warning in snapshot.parser_warnings:
            _write_metadata_row(writer, "failure", "UNKNOWN", warning)


def _write_metadata_row(writer, record_type: str, status: str, error: str, failure: APFilesystemFailure | None = None) -> None:
    failure = failure or APFilesystemFailure()
    writer.writerow(
        {
            "record_type": record_type,
            "wlc_name": failure.wlc_name,
            "wlc_host": failure.wlc_host,
            "ap_name": failure.ap_name,
            "ap_host": failure.ap_host,
            "filesystem": "",
            "mount": "",
            "size": "",
            "used": "",
            "available": "",
            "used_percent": "",
            "status": status,
            "notes": "",
            "reload_action": "",
            "reload_output": "",
            "error": error,
        }
    )


def run_audit(
    wlc_targets: list[WlcTarget],
    ap_credentials: APCredentials,
    audit_config: APFilesystemAuditConfig,
    wlc_concurrency: int,
    console=None,
) -> int:
    console = Console() if console is None else console
    rows: list[APFilesystemRow] = []
    failures: list[APFilesystemFailure] = []
    parser_warnings: list[str] = []
    reload_results: list[APReloadResult] = []

    discovery_results = _run_bounded(wlc_targets, discover_aps_from_wlc, wlc_concurrency)
    discovered: list[APTarget] = []
    for target, result in zip(wlc_targets, discovery_results):
        if isinstance(result, Exception):
            failures.append(APFilesystemFailure(target.name, target.config.host, message=str(result)))
        else:
            discovered.extend(result)

    filtered = filter_ap_targets(_dedupe_ap_targets(discovered), audit_config)
    collection_results = _run_bounded(
        filtered,
        lambda target: collect_ap_filesystems(target, ap_credentials, audit_config),
        audit_config.ap_concurrency,
    )
    for target, result in zip(filtered, collection_results):
        if isinstance(result, Exception):
            failures.append(APFilesystemFailure(target.wlc_name, target.wlc_host, target.name, target.host, str(result)))
        else:
            rows.extend(result.rows)
            failures.extend(result.failures)
            parser_warnings.extend(result.parser_warnings)
            reload_results.extend(result.reload_results)

    snapshot = APFilesystemSnapshot(rows=rows, failures=failures, parser_warnings=parser_warnings, reload_results=reload_results)
    console.print(build_filesystem_table(snapshot, audit_config))
    if audit_config.output:
        write_csv(audit_config.output, snapshot, audit_config)
    return 1 if failures else 0


def _run_bounded(items: list, fn, concurrency: int) -> list:
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
        futures = [executor.submit(fn, item) for item in items]
        results = []
        for future in futures:
            try:
                results.append(future.result())
            except Exception as exc:
                results.append(exc)
        return results


def _dedupe_ap_targets(targets: list[APTarget]) -> list[APTarget]:
    deduped = []
    seen: set[tuple[str, str]] = set()
    for target in targets:
        key = (target.name, target.host)
        if key in seen:
            continue
        deduped.append(target)
        seen.add(key)
    return deduped


def select_wlc_targets(targets: list[WlcTarget], names: tuple[str, ...]) -> list[WlcTarget]:
    if not names:
        return list(targets)
    selected = [target for target in targets if target.name in set(names)]
    missing = sorted(set(names) - {target.name for target in selected})
    if missing:
        raise ValueError(f"Unknown WLC target(s): {', '.join(missing)}")
    return selected


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
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
            audit_config = replace(audit_config, reload_full_tmp=True, confirm_reload_full_tmp=True)

        targets = select_wlc_targets(config.wlc_targets, tuple(args.wlc))
        concurrency = args.wlc_concurrency if args.wlc_concurrency is not None else config.wlc_concurrency
        return run_audit(targets, config.ap_credentials, audit_config, concurrency)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
