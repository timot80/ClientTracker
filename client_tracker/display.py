from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import APClientState, LocalClientState, TrackerEvent, WLCClientState


class LiveDisplay:
    PANEL_WIDTH = 110

    def __init__(self):
        self.console = Console()

    def build(
        self,
        wlc_hostname: str,
        wlc_state: WLCClientState | None,
        ap_state: APClientState | None,
        local_state: LocalClientState | None,
        events: list[TrackerEvent],
        wlc_error: str = "",
        ap_error: str = "",
        local_error: str = "",
        mode: str = "infra",
    ) -> Table:
        outer = Table.grid(expand=False)
        outer.add_column()
        if mode in ("infra", "combined"):
            outer.add_row(self._wlc_panel(wlc_hostname, wlc_state, wlc_error))
            outer.add_row(self._ap_panel(ap_state, ap_error))
        if mode in ("local", "combined"):
            outer.add_row(self._local_panel(local_state, local_error))
        outer.add_row(self._events_panel(events))
        outer.add_row(Text("Ctrl+C to quit", style="dim"))
        return outer

    def _wlc_panel(self, hostname: str, state: WLCClientState | None, error: str) -> Panel:
        tbl = Table.grid(padding=(0, 2))
        tbl.add_column(min_width=10)
        tbl.add_column(min_width=26)
        if error:
            tbl.add_row("[red]Error[/red]", f"[red]{error}[/red]")
        elif state is None:
            tbl.add_row("[yellow]Status[/yellow]", "[yellow]Client not associated[/yellow]")
        else:
            ts = state.timestamp.strftime("%H:%M:%S") if state.timestamp else ""
            tbl.add_row("WLC:", hostname)
            tbl.add_row("Client:", state.mac)
            tbl.add_row("AP Name:", f"{state.ap_name:<26s}  AP IP: {state.ap_ip}")
            tbl.add_row("SSID:", f"{state.ssid:<26s}  Protocol: {state.protocol}")
            tbl.add_row("RSSI:", f"{state.rssi or 'N/A':<26s}  SNR: {state.snr or 'N/A'}")
            tbl.add_row("State:", f"{state.state:<26s}  Updated: {ts}")
        return Panel(tbl, title="WLC Client Stats", width=self.PANEL_WIDTH, border_style="yellow")

    def _ap_panel(self, state: APClientState | None, error: str) -> Panel:
        title = "AP Client Stats"
        tbl = Table.grid(padding=(0, 2))
        tbl.add_column()
        if error:
            tbl.add_row(f"[red]{error}[/red]")
        elif state is None:
            tbl.add_row("[dim]Waiting for data...[/dim]")
        else:
            title = f"AP Client Stats ([white]{state.ap_name}[/white])"
            tbl.add_row(
                f"Live RSSI: [cyan]{state.rssi or 'N/A'} dBm[/cyan]    "
                f"Rate: {state.mcs_rate or 'N/A'}    Slot: {state.slot_id or 'N/A'}"
            )
            ts = state.timestamp.strftime("%H:%M:%S") if state.timestamp else ""
            tbl.add_row(f"Updated: {ts}")
        return Panel(tbl, title=title, width=self.PANEL_WIDTH, border_style="yellow")

    def _local_panel(self, state: LocalClientState | None, error: str) -> Panel:
        tbl = Table.grid(padding=(0, 2))
        tbl.add_column(min_width=10)
        tbl.add_column()
        if error:
            tbl.add_row("[red]Error[/red]", f"[red]{error}[/red]")
        elif state is None:
            tbl.add_row("[dim]Waiting for local telemetry...[/dim]", "")
        else:
            ts = state.timestamp.strftime("%H:%M:%S") if state.timestamp else ""
            tbl.add_row("SSID:", state.ssid or "N/A")
            tbl.add_row("BSSID:", state.bssid or "N/A")
            tbl.add_row("Channel:", f"{state.channel or 'N/A'}  PHY: {state.phy_mode or 'N/A'}")
            tbl.add_row(
                "Signal:",
                f"{state.signal or 'N/A'}  Noise: {state.noise or 'N/A'}  CCA: {state.cca or 'N/A'}",
            )
            tbl.add_row("Rates:", f"TX: {state.tx_rate or 'N/A'}  RX: {state.rx_rate or 'N/A'}")
            tbl.add_row(
                "MCS:",
                f"{state.mcs_index or 'N/A'}  NSS: {state.nss or 'N/A'}  GI: {state.guard_interval or 'N/A'}",
            )
            tbl.add_row("Security:", state.security or "N/A")
            tbl.add_row("IP:", f"{state.ipv4_address or 'N/A'}  Router: {state.ipv4_router or 'N/A'}")
            tbl.add_row("Ping:", state.ping_status or "N/A")
            tbl.add_row("Updated:", ts)
        return Panel(tbl, title="Local Client Stats", width=self.PANEL_WIDTH, border_style="cyan")

    def _events_panel(self, events: list[TrackerEvent]) -> Panel:
        tbl = Table.grid(padding=(0, 1))
        tbl.add_column(min_width=10)
        tbl.add_column(min_width=10)
        tbl.add_column()
        if not events:
            tbl.add_row("", "", "[dim]No events yet[/dim]")
        else:
            for event in reversed(events):
                tbl.add_row(event.timestamp.strftime("%H:%M:%S"), event.source, event.message)
        return Panel(tbl, title="Event Timeline", width=self.PANEL_WIDTH, border_style="yellow")
