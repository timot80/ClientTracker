from __future__ import annotations

import re

from ap_port_audit.models import APPortRow, APPortSnapshot


AP_NAME_RE = re.compile(r"^AP Name\s*:\s*(?P<name>.+?)\s*$")
SPEED_RE = re.compile(r"^(?P<speed>\d+)\s+Mbps$", re.IGNORECASE)


def parse_ethernet_statistics(output: str) -> APPortSnapshot:
    rows: list[APPortRow] = []
    warnings: list[str] = []
    current_ap = ""
    in_table = False

    for line_number, line in enumerate(output.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        ap_match = AP_NAME_RE.match(stripped)
        if ap_match:
            current_ap = ap_match.group("name")
            in_table = False
            continue
        if stripped.startswith("Interface Name"):
            in_table = True
            continue
        if set(stripped) == {"-"}:
            continue
        if not in_table:
            continue
        parts = stripped.split()
        if len(parts) < 7 or not current_ap:
            warnings.append(
                f"line {line_number}: skipped malformed row for {current_ap or 'unknown AP'}: {stripped}"
            )
            continue
        rx_packets = _parse_int(parts[-3])
        tx_packets = _parse_int(parts[-2])
        discarded_packets = _parse_int(parts[-1])
        if rx_packets is None or tx_packets is None or discarded_packets is None:
            warnings.append(
                f"line {line_number}: skipped malformed row for {current_ap}: {stripped}"
            )
            continue
        speed_text = " ".join(parts[2:-4])
        rows.append(
            APPortRow(
                ap_name=current_ap,
                interface=parts[0],
                link_status=parts[1],
                speed_text=speed_text,
                speed_mbps=_parse_speed_mbps(speed_text),
                duplex=parts[-4],
                rx_packets=rx_packets,
                tx_packets=tx_packets,
                discarded_packets=discarded_packets,
            )
        )

    return APPortSnapshot(rows=rows, parser_warnings=warnings)


def _parse_speed_mbps(value: str) -> int | None:
    match = SPEED_RE.match(value.strip())
    if not match:
        return None
    return int(match.group("speed"))


def _parse_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None
