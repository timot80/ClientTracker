from __future__ import annotations

import threading
from typing import Optional

from netmiko import ConnectHandler

from ap_radio_monitor.models import WLCConfig


class WLCLoadInfoSession:
    """Persistent SSH session for AP radio load-info polling."""

    def __init__(self, config: WLCConfig):
        self.config = config
        self.connection: Optional[ConnectHandler] = None
        self._lock = threading.Lock()
        self._admin_down_slots_by_ap: dict[str, set[int]] = {}
        self._checked_slots_by_ap: dict[str, set[int]] = {}
        self._radio_summary_loaded = False

    def connect(self) -> None:
        self.connection = ConnectHandler(
            device_type="cisco_ios",
            host=self.config.host,
            username=self.config.username,
            password=self.config.password,
            secret=self.config.enable,
        )
        if self.config.enable and not self.connection.check_enable_mode():
            self.connection.enable()
        self.connection.send_command("terminal length 0", expect_string=r"#", read_timeout=30)

    def get_load_info(self) -> str:
        with self._lock:
            if self.connection is None:
                raise RuntimeError("WLC session not connected")
            return self.connection.send_command(
                "show ap summary load-info",
                expect_string=r"#",
                read_timeout=self.config.read_timeout,
            )

    def get_admin_down_slots(self, ap_name: str, slot_numbers: tuple[int, ...]) -> set[int]:
        checked = self._checked_slots_by_ap.get(ap_name, set())
        missing_slots = tuple(slot for slot in slot_numbers if slot not in checked)
        if not missing_slots:
            return set(self._admin_down_slots_by_ap.get(ap_name, set())).intersection(slot_numbers)

        with self._lock:
            if self.connection is None:
                raise RuntimeError("WLC session not connected")
            if not self._radio_summary_loaded:
                self._load_radio_summary_slot_states()
                self._radio_summary_loaded = True
                checked = self._checked_slots_by_ap.get(ap_name, set())
                missing_slots = tuple(slot for slot in slot_numbers if slot not in checked)
                if not missing_slots:
                    return set(self._admin_down_slots_by_ap.get(ap_name, set())).intersection(slot_numbers)
            known = self._admin_down_slots_by_ap.setdefault(ap_name, set())
            checked = self._checked_slots_by_ap.setdefault(ap_name, set())
            for slot in missing_slots:
                output = self.connection.send_command(
                    f"show ap name {ap_name} config slot {slot}",
                    expect_string=r"#",
                    read_timeout=self.config.read_timeout,
                )
                checked.add(slot)
                if _is_admin_down_slot_config(output):
                    known.add(slot)
        return set(self._admin_down_slots_by_ap.get(ap_name, set())).intersection(slot_numbers)

    def _load_radio_summary_slot_states(self) -> None:
        for command in (
            "show ap dot11 24ghz summary",
            "show ap dot11 5ghz summary",
            "show ap dot11 6ghz summary",
        ):
            try:
                output = _send_command_timing(
                    self.connection,
                    command,
                    read_timeout=self.config.read_timeout,
                )
            except Exception:
                continue
            _merge_radio_summary(output, self._admin_down_slots_by_ap, self._checked_slots_by_ap)

    def disconnect(self) -> None:
        with self._lock:
            if self.connection is not None:
                try:
                    self.connection.disconnect()
                finally:
                    self.connection = None


def _is_admin_down_slot_config(output: str) -> bool:
    admin_state = _config_value(output, "Administrative State")
    operation_state = _config_value(output, "Operation State")
    if admin_state and admin_state.lower() != "enabled":
        return True
    if operation_state and operation_state.lower() != "up":
        return True
    return False


def _config_value(output: str, label: str) -> str:
    prefix = f"{label}"
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped.startswith(prefix) or ":" not in stripped:
            continue
        return stripped.split(":", 1)[1].strip()
    return ""


def _send_command_timing(connection, command: str, read_timeout: int) -> str:
    if hasattr(connection, "send_command_timing"):
        return connection.send_command_timing(command, read_timeout=read_timeout, last_read=3)
    return connection.send_command(command, expect_string=r"#", read_timeout=read_timeout)


def _merge_radio_summary(
    output: str,
    admin_down_slots_by_ap: dict[str, set[int]],
    checked_slots_by_ap: dict[str, set[int]],
) -> None:
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 6 or not parts[2].isdigit():
            continue
        ap_name = parts[0]
        slot = int(parts[2])
        admin_state = parts[3].lower()
        oper_state = parts[4].lower()
        checked_slots_by_ap.setdefault(ap_name, set()).add(slot)
        if admin_state != "enabled" or oper_state != "up":
            admin_down_slots_by_ap.setdefault(ap_name, set()).add(slot)
