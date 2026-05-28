from __future__ import annotations

import re
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from typing import Optional

from netmiko import ConnectHandler

from .models import APClientState, WLCClientState

_VALID_MAC_RE = re.compile(r"^[0-9a-f]{12}$")


def normalize_mac(mac: str) -> str:
    """Strip common MAC delimiters and return lowercase hex."""
    return re.sub(r"[:\-.]", "", mac).lower()


def mac_to_cisco(mac: str) -> str:
    """Convert any supported MAC format to Cisco dot notation."""
    raw = normalize_mac(mac)
    return f"{raw[0:4]}.{raw[4:8]}.{raw[8:12]}"


def mac_to_colon(mac: str) -> str:
    """Convert any supported MAC format to colon notation."""
    raw = normalize_mac(mac)
    return ":".join(raw[i:i + 2] for i in range(0, 12, 2))


def is_valid_mac(mac: str) -> bool:
    """Return True when the input is exactly 12 hex digits after normalization."""
    return bool(_VALID_MAC_RE.match(normalize_mac(mac)))


class WLCSession:
    def __init__(self, host: str, username: str, password: str, enable: str = ""):
        self.host = host
        self.username = username
        self.password = password
        self.enable = enable
        self.connection: Optional[ConnectHandler] = None
        self.hostname = ""
        self._lock = threading.Lock()

    def connect(self):
        self.connection = ConnectHandler(
            device_type="cisco_ios",
            host=self.host,
            username=self.username,
            password=self.password,
            secret=self.enable,
        )
        if self.enable and not self.connection.check_enable_mode():
            self.connection.enable()
            if not self.connection.check_enable_mode():
                raise RuntimeError(
                    "WLC did not enter enable mode; check wlc.enable in config.yaml"
                )
        self._send("terminal length 0")
        self._fetch_hostname()

    def _fetch_hostname(self):
        output = self._send("show run | include hostname")
        for line in output.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("hostname"):
                parts = stripped.split(None, 1)
                self.hostname = parts[1] if len(parts) > 1 else ""
                break

    def _send(self, command: str) -> str:
        with self._lock:
            if self.connection is None:
                raise RuntimeError("WLC session not connected")
            return self.connection.send_command(command)

    def _send_with_retry(self, command: str) -> str:
        try:
            return self._send(command)
        except Exception:
            self.reconnect()
            return self._send(command)

    def reconnect(self):
        self.disconnect()
        self.connect()

    def disconnect(self):
        with self._lock:
            if self.connection:
                try:
                    self.connection.disconnect()
                except Exception:
                    pass
                self.connection = None

    def get_client_state(self, mac: str) -> WLCClientState | None:
        cisco_mac = mac_to_cisco(mac)
        output = self._send_with_retry(f"show wireless client mac-address {cisco_mac} detail")
        if "Client MAC Address" not in output:
            return None
        return self.parse_client_detail(output, mac)

    def get_ap_ip(self, ap_name: str) -> str:
        output = self._send_with_retry(f"show ap name {ap_name} config general | include IP")
        ip = self.parse_ap_config_general_ip(output)
        if ip:
            return ip
        output = self._send_with_retry("show ap summary")
        return self.parse_ap_summary_ip(output, ap_name)

    @staticmethod
    def parse_ap_config_general_ip(output: str) -> str:
        for line in output.splitlines():
            key, separator, raw_value = line.partition(":")
            if not separator:
                continue
            if key.strip() != "IP Address":
                continue
            match = re.search(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", raw_value)
            if match:
                return match.group(1)
        return ""

    @staticmethod
    def parse_ap_summary_ip(output: str, ap_name: str) -> str:
        for line in output.splitlines():
            fields = line.split()
            if fields and fields[0] == ap_name:
                match = re.search(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", line)
                if match:
                    return match.group(1)
        return ""

    @staticmethod
    def parse_client_detail(output: str, mac: str) -> WLCClientState:
        state = WLCClientState(mac=mac, timestamp=datetime.now())
        field_map = {
            "AP Name": "ap_name",
            "Wireless LAN Network Name (SSID)": "ssid",
            "Protocol": "protocol",
            "Policy Manager State": "state",
            "Radio Signal Strength Indicator": "rssi",
            "Signal to Noise Ratio": "snr",
        }
        unit_strip = {"rssi": " dBm", "snr": " dB"}
        for line in output.splitlines():
            stripped = line.strip()
            if ":" not in stripped:
                continue
            key, _, raw_value = stripped.partition(":")
            attr = field_map.get(key.strip())
            if not attr:
                continue
            value = raw_value.strip()
            suffix = unit_strip.get(attr)
            if suffix and value.endswith(suffix):
                value = value[: -len(suffix)]
            setattr(state, attr, value)
        return state


class APSessionPool:
    def __init__(self, username: str, password: str, enable: str = ""):
        self.username = username
        self.password = password
        self.enable = enable
        self._sessions: dict[str, ConnectHandler] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=4)

    def query_rssi(self, ap_name: str, ap_ip: str, mac: str) -> Future:
        return self._executor.submit(self._fetch_rssi, ap_name, ap_ip, mac)

    def _get_or_create_session(self, ap_name: str, ap_ip: str) -> ConnectHandler:
        with self._lock:
            conn = self._sessions.get(ap_name)
            if conn and conn.is_alive():
                return conn

        conn = ConnectHandler(
            device_type="cisco_ios",
            host=ap_ip,
            username=self.username,
            password=self.password,
            secret=self.enable,
        )
        if self.enable:
            conn.enable()
        with self._lock:
            self._sessions[ap_name] = conn
        return conn

    def _fetch_rssi(self, ap_name: str, ap_ip: str, mac: str) -> APClientState:
        conn = self._get_or_create_session(ap_name, ap_ip)
        output = conn.send_command("show dot11 clients")
        return self.parse_dot11_clients(output, mac, ap_name)

    @staticmethod
    def parse_dot11_clients(output: str, mac: str, ap_name: str) -> APClientState:
        state = APClientState(mac=mac, ap_name=ap_name, timestamp=datetime.now())
        target = normalize_mac(mac)
        for line in output.splitlines():
            if target not in normalize_mac(line):
                continue
            tokens = line.split()
            if len(tokens) < 6:
                break
            state.slot_id = tokens[1]
            rssi_idx = next(
                (
                    i
                    for i in range(4, len(tokens))
                    if tokens[i].startswith("-")
                    and tokens[i][1:].isdigit()
                    and 1 <= int(tokens[i][1:]) <= 128
                ),
                None,
            )
            if rssi_idx is None:
                break
            state.ssid = " ".join(tokens[4:rssi_idx])
            state.rssi = tokens[rssi_idx]
            if rssi_idx + 1 < len(tokens):
                state.mcs_rate = tokens[rssi_idx + 1]
            break
        return state

    def close_session(self, ap_name: str):
        with self._lock:
            conn = self._sessions.pop(ap_name, None)
        if conn:
            try:
                conn.disconnect()
            except Exception:
                pass

    def shutdown(self):
        with self._lock:
            names = list(self._sessions.keys())
        for name in names:
            self.close_session(name)
        self._executor.shutdown(wait=False)
