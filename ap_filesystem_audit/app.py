from __future__ import annotations

from dataclasses import replace

from netmiko import ConnectHandler
from rich.console import Console

from ap_filesystem_audit.discovery import discover_aps_from_wlc
from ap_filesystem_audit.display import build_filesystem_table
from ap_filesystem_audit.export import write_csv
from ap_filesystem_audit.models import (
    APCredentials,
    APFilesystemAuditConfig,
    APFilesystemFailure,
    APFilesystemSnapshot,
    APTarget,
)
from ap_filesystem_audit.parser import parse_filesystems
from ap_filesystem_audit.scoring import filter_ap_targets
from wifiops.concurrency import run_bounded
from wifiops.wlc_targets import WlcTarget


def collect_ap_filesystems(
    target: APTarget,
    creds: APCredentials,
    config: APFilesystemAuditConfig,
) -> APFilesystemSnapshot:
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
        return APFilesystemSnapshot(
            rows=[
                replace(
                    row,
                    wlc_name=target.wlc_name,
                    wlc_host=target.wlc_host,
                    ap_name=target.name,
                    ap_host=target.host,
                )
                for row in snapshot.rows
            ],
            failures=snapshot.failures,
            parser_warnings=snapshot.parser_warnings,
            timestamp=snapshot.timestamp,
        )
    finally:
        conn.disconnect()


def run_audit(
    wlc_targets: list[WlcTarget],
    ap_credentials: APCredentials,
    audit_config: APFilesystemAuditConfig,
    wlc_concurrency: int,
    console: Console | None = None,
) -> int:
    console = Console() if console is None else console
    rows = []
    failures: list[APFilesystemFailure] = []
    parser_warnings: list[str] = []

    discovery_results = run_bounded(wlc_targets, discover_aps_from_wlc, wlc_concurrency)
    discovered: list[APTarget] = []
    for target, result in zip(wlc_targets, discovery_results):
        if isinstance(result, Exception):
            failures.append(
                APFilesystemFailure(
                    wlc_name=target.name,
                    wlc_host=target.config.host,
                    message=str(result),
                )
            )
        else:
            discovered.extend(result)

    filtered = filter_ap_targets(_dedupe_ap_targets(discovered), audit_config)
    collection_results = run_bounded(
        filtered,
        lambda target: collect_ap_filesystems(target, ap_credentials, audit_config),
        audit_config.ap_concurrency,
    )
    for target, result in zip(filtered, collection_results):
        if isinstance(result, Exception):
            failures.append(
                APFilesystemFailure(
                    wlc_name=target.wlc_name,
                    wlc_host=target.wlc_host,
                    ap_name=target.name,
                    ap_host=target.host,
                    message=str(result),
                )
            )
        else:
            rows.extend(result.rows)
            failures.extend(result.failures)
            parser_warnings.extend(result.parser_warnings)

    snapshot = APFilesystemSnapshot(rows=rows, failures=failures, parser_warnings=parser_warnings)
    console.print(build_filesystem_table(snapshot, audit_config))
    if audit_config.output:
        try:
            write_csv(audit_config.output, snapshot, audit_config)
        except Exception as exc:
            console.print(f"Failed to write CSV output: {exc}")
            return 1
    return 1 if failures else 0


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
