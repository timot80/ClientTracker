from __future__ import annotations

import math
import subprocess
import sys
from datetime import datetime

from .models import LocalClientState

AIRPORT = (
    "/System/Library/PrivateFrameworks/Apple80211.framework/"
    "Versions/Current/Resources/airport"
)


def _value_after_colon(line: str) -> tuple[str, str] | None:
    if ":" not in line:
        return None
    key, _, value = line.partition(":")
    return key.strip(), value.strip()


def parse_airport_output(output: str) -> LocalClientState:
    values = {}
    for line in output.splitlines():
        parsed = _value_after_colon(line)
        if parsed:
            key, value = parsed
            values[key] = value
    return LocalClientState(
        ssid=values.get("SSID", ""),
        bssid=values.get("BSSID", ""),
        channel=values.get("channel", ""),
        tx_rate=values.get("lastTxRate", ""),
        signal=values.get("agrCtlRSSI", "") or values.get("CtlRSSI", ""),
        noise=values.get("agrCtlNoise", ""),
        platform="darwin",
        timestamp=datetime.now(),
    )


def _strip_units(value: str, *units: str) -> str:
    cleaned = value.strip()
    for unit in units:
        if cleaned.endswith(unit):
            return cleaned[: -len(unit)].strip()
    return cleaned


def parse_wdutil_output(output: str) -> LocalClientState:
    values = {}
    for line in output.splitlines():
        parsed = _value_after_colon(line)
        if parsed:
            key, value = parsed
            values[key] = value
    return LocalClientState(
        ssid=values.get("SSID", ""),
        bssid=values.get("BSSID", ""),
        channel=values.get("Channel", ""),
        tx_rate=_strip_units(values.get("Tx Rate", ""), " Mbps", "Mbps"),
        signal=_strip_units(values.get("RSSI", ""), " dBm", "dBm"),
        noise=_strip_units(values.get("Noise", ""), " dBm", "dBm"),
        platform="darwin",
        timestamp=datetime.now(),
    )


def parse_networksetup_output(output: str) -> str:
    prefix = "Current Wi-Fi Network:"
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].strip()
    return ""


def parse_system_profiler_wifi_status(output: str) -> str:
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("Status:"):
            return stripped
    return ""


def parse_netsh_output(output: str) -> LocalClientState:
    values = {}
    for line in output.splitlines():
        parsed = _value_after_colon(line)
        if parsed:
            key, value = parsed
            values[key] = value
    signal_percent = values.get("Signal", "").rstrip("%")
    signal = ""
    if signal_percent.isdigit():
        signal = f"{int(signal_percent) / 2 - 100:.1f} approx dBm"
    return LocalClientState(
        ssid=values.get("SSID", ""),
        bssid=values.get("BSSID", ""),
        channel=values.get("Channel", ""),
        tx_rate=values.get("Transmit rate (Mbps)", ""),
        rx_rate=values.get("Receive rate (Mbps)", ""),
        signal=signal,
        platform="win32",
        timestamp=datetime.now(),
    )


def build_ping_argv(host: str, platform: str | None = None) -> list[str]:
    platform = platform or sys.platform
    if platform == "win32":
        return ["ping", "-w", "1000", "-n", "1", host]
    wait_seconds = str(max(1, math.ceil(1000 / 1000)))
    return ["ping", "-c", "1", "-W", wait_seconds, host]


def play_roam_sound(platform: str | None = None) -> None:
    platform = platform or sys.platform
    if platform == "win32":
        try:
            import winsound

            winsound.Beep(880, 120)
            winsound.Beep(1174, 120)
            return
        except (ImportError, RuntimeError):
            pass
    elif platform == "darwin":
        try:
            subprocess.run(
                ["afplay", "/System/Library/Sounds/Tink.aiff"],
                capture_output=True,
                timeout=5,
                check=False,
            )
            return
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
    print("\a", end="", flush=True)


class LocalTelemetryPoller:
    def __init__(
        self,
        ping_host: str = "",
        sound_alerts: bool = True,
        platform: str | None = None,
    ):
        self.ping_host = ping_host
        self.sound_alerts = sound_alerts
        self.platform = platform or sys.platform

    def poll(self) -> LocalClientState:
        if self.platform == "darwin":
            try:
                output = subprocess.check_output(
                    ["sudo", "-n", "wdutil", "info"],
                    timeout=15,
                    stderr=subprocess.DEVNULL,
                )
                return parse_wdutil_output(output.decode("utf-8", errors="replace"))
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
                raise RuntimeError(
                    "macOS local telemetry requires sudo for 'wdutil info'. "
                    "Run 'sudo -v' first, or run the tracker with sudo."
                ) from exc
            try:
                output = subprocess.check_output([AIRPORT, "-I"], timeout=15)
                return parse_airport_output(output.decode("utf-8", errors="replace"))
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                return self._poll_macos_fallback()
        if self.platform == "win32":
            output = subprocess.check_output(
                ["netsh", "wlan", "show", "interfaces"],
                timeout=30,
            )
            state = parse_netsh_output(output.decode("utf-8", errors="replace"))
            if self.ping_host:
                state.ping_status = self._ping()
            return state
        raise RuntimeError(f"Local telemetry is unsupported on {self.platform}")

    def _poll_macos_fallback(self) -> LocalClientState:
        state = LocalClientState(platform="darwin", timestamp=datetime.now())
        try:
            ssid_output = subprocess.check_output(
                ["networksetup", "-getairportnetwork", "en0"],
                timeout=10,
            )
            state.ssid = parse_networksetup_output(
                ssid_output.decode("utf-8", errors="replace")
            )
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            state.ssid = ""
        try:
            profiler_output = subprocess.check_output(
                ["system_profiler", "SPAirPortDataType", "-detailLevel", "mini"],
                timeout=20,
            )
            state.ping_status = parse_system_profiler_wifi_status(
                profiler_output.decode("utf-8", errors="replace")
            )
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            state.ping_status = "airport unavailable"
        return state

    def _ping(self) -> str:
        try:
            output = subprocess.check_output(
                build_ping_argv(self.ping_host, self.platform),
                timeout=5,
            )
        except subprocess.CalledProcessError:
            return "No ICMP data"
        except subprocess.TimeoutExpired:
            return "Ping timed out"
        text = output.decode("utf-8", errors="replace")
        for line in text.splitlines():
            if "bytes=" in line.lower():
                return line.strip()
        return "No ICMP data"
