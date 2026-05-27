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

    def get_load_info(self) -> str:
        with self._lock:
            if self.connection is None:
                raise RuntimeError("WLC session not connected")
            return self.connection.send_command("show ap summary load-info")

    def disconnect(self) -> None:
        with self._lock:
            if self.connection is not None:
                try:
                    self.connection.disconnect()
                finally:
                    self.connection = None
