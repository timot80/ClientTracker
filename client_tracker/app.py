from __future__ import annotations

import signal
import sys
from datetime import datetime
from pathlib import Path

from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException
from rich.live import Live

from .config import AppConfig
from .display import LiveDisplay
from .events import CSVLogger, EventTimeline
from .infra import APSessionPool, WLCSession
from .local import LocalTelemetryPoller, play_roam_sound
from .models import APClientState, LocalClientState, Mode, TrackerEvent, WLCClientState

POLL_INTERVAL = 5


def detect_infra_roam(
    previous_ap: str,
    current: WLCClientState,
    last_ap_state: APClientState | None,
    now: datetime | None = None,
) -> TrackerEvent | None:
    if not previous_ap or not current.ap_name or previous_ap == current.ap_name:
        return None
    now = now or datetime.now()
    return TrackerEvent(
        timestamp=now,
        source="infra",
        type="roam",
        message=f"WLC AP changed from {previous_ap} to {current.ap_name}",
        previous_ap=previous_ap,
        current_ap=current.ap_name,
        rssi=last_ap_state.rssi if last_ap_state else "",
        channel=last_ap_state.channel if last_ap_state else "",
    )


def detect_local_change(
    previous: LocalClientState | None,
    current: LocalClientState,
    now: datetime | None = None,
) -> TrackerEvent | None:
    if previous is None:
        return None
    now = now or datetime.now()
    if previous.bssid and current.bssid and previous.bssid != current.bssid:
        return TrackerEvent(
            timestamp=now,
            source="local",
            type="bssid-change",
            message=f"Local BSSID changed from {previous.bssid} to {current.bssid}",
            previous_bssid=previous.bssid,
            current_bssid=current.bssid,
            rssi=current.signal,
            channel=current.channel,
        )
    if previous.bssid and not current.bssid:
        return TrackerEvent(
            timestamp=now,
            source="local",
            type="disassociated",
            message="Local client disassociated",
            previous_bssid=previous.bssid,
        )
    if not previous.bssid and current.bssid:
        return TrackerEvent(
            timestamp=now,
            source="local",
            type="associated",
            message=f"Local client associated to {current.bssid}",
            current_bssid=current.bssid,
            rssi=current.signal,
            channel=current.channel,
        )
    return None


class ClientTrackerApp:
    def __init__(
        self,
        mode: Mode,
        config: AppConfig,
        mac: str | None = None,
        log_path: str | Path | None = None,
    ):
        self.mode = mode
        self.config = config
        self.mac = mac or ""
        self.display = LiveDisplay()
        self.timeline = EventTimeline()
        self.logger = CSVLogger(log_path) if log_path else None
        self.wlc: WLCSession | None = None
        self.ap_pool: APSessionPool | None = None
        self.local_poller: LocalTelemetryPoller | None = None
        self.wlc_state: WLCClientState | None = None
        self.ap_state: APClientState | None = None
        self.local_state: LocalClientState | None = None
        self._current_ap = ""
        self._stop = False
        self.wlc_error = ""
        self.ap_error = ""
        self.local_error = ""

    def run(self):
        self._setup()
        signal.signal(signal.SIGINT, self._handle_signal)
        with Live(self._render(), console=self.display.console, refresh_per_second=2) as live:
            while not self._stop:
                self.poll_once()
                live.update(self._render())
                signal.pause() if False else None
                import time

                time.sleep(POLL_INTERVAL)
        self.cleanup()

    def poll_once(self):
        if self.mode in ("infra", "combined"):
            self._poll_wlc()
            self._poll_ap()
        if self.mode in ("local", "combined"):
            self._poll_local()
        self._write_sample()

    def _setup(self):
        if self.mode in ("infra", "combined"):
            self.wlc = WLCSession(
                self.config.wlc.host,
                self.config.wlc.username,
                self.config.wlc.password,
                self.config.wlc.enable,
            )
            self.ap_pool = APSessionPool(
                self.config.ap.username,
                self.config.ap.password,
                self.config.ap.enable,
            )
            try:
                self.wlc.connect()
            except (NetmikoAuthenticationException, NetmikoTimeoutException) as exc:
                print(f"Failed to connect to WLC: {exc}")
                sys.exit(1)
        if self.mode in ("local", "combined"):
            self.local_poller = LocalTelemetryPoller(
                ping_host=self.config.local.ping_host,
                sound_alerts=self.config.local.sound_alerts,
            )

    def _poll_wlc(self):
        if self.wlc is None:
            return
        try:
            state = self.wlc.get_client_state(self.mac)
            self.wlc_error = ""
        except Exception as exc:
            self.wlc_error = str(exc)
            self._append_event(TrackerEvent(datetime.now(), "infra", "poll-error", self.wlc_error, error=self.wlc_error))
            return
        if state is None:
            self.wlc_state = None
            return
        if state.ap_name:
            try:
                state.ap_ip = self.wlc.get_ap_ip(state.ap_name)
            except Exception:
                state.ap_ip = ""
        event = detect_infra_roam(self._current_ap, state, self.ap_state)
        if event:
            self._append_event(event)
            if self.ap_pool:
                self.ap_pool.close_session(self._current_ap)
            self.ap_state = None
        if state.ap_name:
            self._current_ap = state.ap_name
        self.wlc_state = state

    def _poll_ap(self):
        if not self.ap_pool or not self.wlc_state or not self.wlc_state.ap_name:
            return
        if not self.wlc_state.ap_ip:
            self.ap_error = f"No IP resolved for AP {self.wlc_state.ap_name}"
            return
        try:
            future = self.ap_pool.query_rssi(self.wlc_state.ap_name, self.wlc_state.ap_ip, self.mac)
            self.ap_state = future.result(timeout=10)
            self.ap_error = ""
        except Exception as exc:
            self.ap_error = str(exc)
            self._append_event(TrackerEvent(datetime.now(), "ap", "poll-error", self.ap_error, error=self.ap_error))

    def _poll_local(self):
        if self.local_poller is None:
            return
        previous = self.local_state
        try:
            current = self.local_poller.poll()
            self.local_error = ""
        except Exception as exc:
            self.local_error = str(exc)
            self._append_event(TrackerEvent(datetime.now(), "local", "poll-error", self.local_error, error=self.local_error))
            return
        event = detect_local_change(previous, current)
        if event:
            self._append_event(event)
            if self.config.local.sound_alerts and self.mode == "local":
                play_roam_sound()
        self.local_state = current

    def _append_event(self, event: TrackerEvent):
        self.timeline.append(event)
        if self.logger:
            self.logger.write_event(self.mode, event)

    def _write_sample(self):
        if not self.logger:
            return
        self.logger.write_sample(
            mode=self.mode,
            infra_ap_name=self.wlc_state.ap_name if self.wlc_state else "",
            infra_ap_ip=self.wlc_state.ap_ip if self.wlc_state else "",
            infra_ssid=self.wlc_state.ssid if self.wlc_state else "",
            infra_rssi=self.wlc_state.rssi if self.wlc_state else "",
            infra_snr=self.wlc_state.snr if self.wlc_state else "",
            ap_rssi=self.ap_state.rssi if self.ap_state else "",
            ap_channel=self.ap_state.channel if self.ap_state else "",
            ap_mcs_rate=self.ap_state.mcs_rate if self.ap_state else "",
            local_ssid=self.local_state.ssid if self.local_state else "",
            local_bssid=self.local_state.bssid if self.local_state else "",
            local_channel=self.local_state.channel if self.local_state else "",
            local_signal=self.local_state.signal if self.local_state else "",
            local_noise=self.local_state.noise if self.local_state else "",
        )

    def _render(self):
        return self.display.build(
            wlc_hostname=self.wlc.hostname if self.wlc else "",
            wlc_state=self.wlc_state,
            ap_state=self.ap_state,
            local_state=self.local_state,
            events=self.timeline.items(),
            wlc_error=self.wlc_error,
            ap_error=self.ap_error,
            local_error=self.local_error,
            mode=self.mode,
        )

    def _handle_signal(self, _signum, _frame):
        self._stop = True

    def cleanup(self):
        self._append_event(TrackerEvent(datetime.now(), "system", "shutdown", "Shutting down"))
        if self.ap_pool:
            self.ap_pool.shutdown()
        if self.wlc:
            self.wlc.disconnect()
        if self.logger:
            self.logger.close()
