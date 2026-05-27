from __future__ import annotations

import math
import json
import os
import pwd
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from .models import LocalClientState

AIRPORT = (
    "/System/Library/PrivateFrameworks/Apple80211.framework/"
    "Versions/Current/Resources/airport"
)
MACOS_IDENTITY_HELPER_APP = "client-tracker-wifi-identity.app"
MACOS_IDENTITY_HELPER_EXECUTABLE = "client-tracker-wifi-identity"
WDUTIL_SECTION_NAMES = {
    "NETWORK",
    "WIFI",
    "BLUETOOTH",
    "AWDL",
    "POWER",
    "WIFI FAULTS LAST HOUR",
    "WIFI RECOVERIES LAST HOUR",
    "WIFI LINK TESTS LAST HOUR",
}


def default_macos_identity_helper_path() -> str:
    return str(
        Path.home()
        / "Applications"
        / MACOS_IDENTITY_HELPER_APP
        / "Contents"
        / "MacOS"
        / MACOS_IDENTITY_HELPER_EXECUTABLE
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
    has_wifi_section = any(line.strip() == "WIFI" for line in output.splitlines())
    section = None
    for line in output.splitlines():
        stripped = line.strip()
        if stripped in WDUTIL_SECTION_NAMES:
            section = stripped
            continue
        if has_wifi_section and section != "WIFI":
            continue
        parsed = _value_after_colon(line)
        if parsed:
            key, value = parsed
            values[key] = value
    return LocalClientState(
        interface_name=values.get("Interface Name", ""),
        ssid=values.get("SSID", ""),
        bssid=values.get("BSSID", ""),
        channel=values.get("Channel", ""),
        tx_rate=_strip_units(values.get("Tx Rate", ""), " Mbps", "Mbps"),
        signal=_strip_units(values.get("RSSI", ""), " dBm", "dBm"),
        noise=_strip_units(values.get("Noise", ""), " dBm", "dBm"),
        cca=_strip_units(values.get("CCA", ""), " %", "%"),
        security=values.get("Security", ""),
        phy_mode=values.get("PHY Mode", ""),
        mcs_index=values.get("MCS Index", ""),
        guard_interval=values.get("Guard Interval", ""),
        nss=values.get("NSS", ""),
        country_code=values.get("Country Code", ""),
        ipv4_address=values.get("IPv4 Address", ""),
        ipv4_router=values.get("IPv4 Router", ""),
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


def parse_identity_helper_output(output: str) -> tuple[str, str]:
    payload = json.loads(output)
    if not isinstance(payload, dict):
        raise ValueError("identity helper returned non-object JSON")
    if payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    ssid = _clean_identity_value(str(payload.get("ssid", "")))
    bssid = _clean_identity_value(str(payload.get("bssid", "")))
    return ssid, bssid


def _clean_identity_value(value: str) -> str:
    cleaned = value.strip()
    if cleaned.lower().startswith("failed to retrieve"):
        return ""
    return cleaned


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
        identity_helper_path: str = "",
    ):
        self.ping_host = ping_host
        self.sound_alerts = sound_alerts
        self.platform = platform or sys.platform
        self.identity_helper_path = identity_helper_path

    def poll(self) -> LocalClientState:
        if self.platform == "darwin":
            try:
                output = subprocess.check_output(
                    ["sudo", "-n", "wdutil", "info"],
                    timeout=15,
                    stderr=subprocess.DEVNULL,
                )
                state = parse_wdutil_output(output.decode("utf-8", errors="replace"))
                self._enrich_identity(state)
                return state
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

    def _enrich_identity(self, state: LocalClientState):
        if state.ssid != "<redacted>" and state.bssid != "<redacted>":
            return
        helper = self._identity_helper_path()
        if not helper:
            return
        helper_path = Path(helper)
        if not helper_path.is_absolute():
            raise RuntimeError("identity helper path must be an absolute path")
        output = self._run_identity_helper(helper)
        ssid, bssid = parse_identity_helper_output(output.decode("utf-8", errors="replace"))
        if state.ssid == "<redacted>" and ssid:
            state.ssid = ssid
        if state.bssid == "<redacted>" and bssid:
            state.bssid = bssid

    def _run_identity_helper(self, helper: str) -> bytes:
        sudo_user = os.environ.get("SUDO_USER", "")
        run_as_user = os.geteuid() == 0 and sudo_user and sudo_user != "root"
        if not self.identity_helper_path and helper == default_macos_identity_helper_path():
            temp_kwargs = {
                "prefix": "client-tracker-wifi-",
                "suffix": ".json",
                "delete": False,
            }
            if run_as_user:
                temp_kwargs["dir"] = "/tmp"
            temp = tempfile.NamedTemporaryFile(**temp_kwargs)
            output_path = temp.name
            temp.close()
            if run_as_user:
                user_info = pwd.getpwnam(sudo_user)
                os.chown(output_path, user_info.pw_uid, user_info.pw_gid)
                os.chmod(output_path, 0o600)
            app_path = str(Path(helper).parents[2])
            argv = ["open", "-W", "-n", app_path, "--args", "--output", output_path]
            if run_as_user:
                argv = ["sudo", "-n", "-u", sudo_user, *argv]
            try:
                subprocess.check_output(argv, timeout=45)
                return Path(output_path).read_bytes()
            finally:
                try:
                    Path(output_path).unlink()
                except FileNotFoundError:
                    pass
        argv = [helper]
        if run_as_user:
            argv = ["sudo", "-n", "-u", sudo_user, helper]
        return subprocess.check_output(argv, timeout=10)

    def _identity_helper_path(self) -> str:
        if self.identity_helper_path:
            return self.identity_helper_path
        helper = default_macos_identity_helper_path()
        if Path(helper).exists():
            return helper
        return ""

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
