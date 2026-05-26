from __future__ import annotations

import re

from ap_radio_monitor.models import APLoad, LoadInfoSnapshot, RadioSlotLoad


class LoadInfoParseError(ValueError):
    """Raised when WLC load-info output cannot be parsed."""


_MAC_RE = re.compile(r"^[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}$")
_SLOT_RE = re.compile(r"\bSlot(\d+)\b", re.IGNORECASE)


def parse_load_info(output: str) -> LoadInfoSnapshot:
    """Parse `show ap summary load-info` output from a Catalyst 9800 WLC."""
    header = _detect_header(output)
    if header is None:
        raise LoadInfoParseError("Could not find supported load-info header")

    mode, slot_numbers = header
    ap_loads: list[APLoad] = []
    parser_warnings: list[str] = []
    after_header = False

    for line_number, line in enumerate(output.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if _is_header_line(stripped):
            after_header = True
            continue
        if not after_header or _is_ignored_line(stripped):
            continue

        try:
            ap_load = _parse_row(stripped, mode, slot_numbers)
        except ValueError:
            parser_warnings.append(f"line {line_number}: skipped malformed row")
            continue

        slot_sum = sum(slot.clients for slot in ap_load.slot_loads if slot.clients is not None)
        if slot_sum != ap_load.total_clients:
            warning = (
                f"{ap_load.name}: slot sum {slot_sum} differs from total clients "
                f"{ap_load.total_clients}"
            )
            ap_load.warnings.append(warning)
            parser_warnings.append(warning)
        ap_loads.append(ap_load)

    if not ap_loads:
        raise LoadInfoParseError("Could not parse any AP rows from load-info output")

    return LoadInfoSnapshot(ap_loads=ap_loads, parser_warnings=parser_warnings)


def _detect_header(output: str) -> tuple[str, list[int]] | None:
    for line in output.splitlines():
        slot_numbers = [int(match) for match in _SLOT_RE.findall(line)]
        if not slot_numbers:
            continue
        normalized = " ".join(line.lower().split())
        if "ap name" in normalized and "radio mac" in normalized:
            return "observed", slot_numbers
        if "wtp-mac" in normalized and "ap-name" in normalized:
            return "documented", slot_numbers
    return None


def _is_header_line(line: str) -> bool:
    normalized = " ".join(line.lower().split())
    return (
        ("slot0" in normalized and ("ap name" in normalized or "ap-name" in normalized))
        or "clients utilisation" in normalized
        or "clients utilization" in normalized
    )


def _is_ignored_line(line: str) -> bool:
    lowered = line.lower()
    return (
        set(line) <= {"-"}
        or lowered.startswith("load for ")
        or lowered.startswith("time source ")
        or lowered.endswith("#sh ap summary load-info")
    )


def _parse_row(line: str, mode: str, slot_numbers: list[int]) -> APLoad:
    tokens = line.split()
    pair_count = len(slot_numbers)
    if len(tokens) < (pair_count * 2) + 4:
        raise ValueError("not enough fields")

    pair_tokens = tokens[-pair_count * 2 :]
    prefix = tokens[: -pair_count * 2]
    if len(prefix) < 4:
        raise ValueError("not enough identity fields")

    slots = _to_int(prefix[-2])
    total_clients = _to_int(prefix[-1])
    identity_tokens = prefix[:-2]

    if mode == "observed":
        if not identity_tokens or not _MAC_RE.match(identity_tokens[-1]):
            raise ValueError("missing radio mac")
        radio_mac = identity_tokens[-1].lower()
        name = " ".join(identity_tokens[:-1]).strip()
        identity_label = "Radio Mac"
    else:
        if not identity_tokens or not _MAC_RE.match(identity_tokens[0]):
            raise ValueError("missing wtp mac")
        radio_mac = identity_tokens[0].lower()
        name = " ".join(identity_tokens[1:]).strip()
        identity_label = "WTP-Mac"

    if not name:
        raise ValueError("missing ap name")

    slot_loads = [
        RadioSlotLoad(
            slot=slot,
            clients=_to_optional_int(pair_tokens[index * 2]),
            utilization=_to_optional_int(pair_tokens[index * 2 + 1]),
        )
        for index, slot in enumerate(slot_numbers)
    ]

    return APLoad(
        name=name,
        radio_mac=radio_mac,
        identity_label=identity_label,
        slots=slots,
        total_clients=total_clients,
        slot_loads=slot_loads,
    )


def _to_int(value: str) -> int:
    if not value.isdigit():
        raise ValueError(f"expected integer, got {value!r}")
    return int(value)


def _to_optional_int(value: str) -> int | None:
    if value.upper() == "NA":
        return None
    return _to_int(value)
