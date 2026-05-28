from __future__ import annotations

import re

from netmiko import ConnectHandler

from ap_filesystem_audit.models import APTarget
from wifiops.wlc_targets import WlcTarget


IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")


def parse_show_ap_summary(output: str, target: WlcTarget) -> list[APTarget]:
    aps: list[APTarget] = []
    seen: set[tuple[str, str]] = set()
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("-"):
            continue
        if stripped.lower().startswith(("ap name", "number of", "total")):
            continue
        fields = stripped.split()
        if len(fields) < 2:
            continue
        match = IP_RE.search(stripped)
        if not match:
            continue
        ap = APTarget(
            wlc_name=target.name,
            wlc_host=target.config.host,
            name=fields[0],
            host=match.group(0),
        )
        key = (ap.name, ap.host)
        if key not in seen:
            aps.append(ap)
            seen.add(key)
    return aps


def discover_aps_from_wlc(target: WlcTarget) -> list[APTarget]:
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
