import ap_radio_monitor_standalone as standalone
from rich.console import Console


def test_standalone_loads_yaml_config(tmp_path):
    path = tmp_path / "monitor.yaml"
    path.write_text(
        """
wlc:
  host: "192.0.2.10"
  username: "admin"
  password: "secret"
  enable: "enable-secret"
  read_timeout: 120
ap_balance:
  refresh_seconds: 15
  include: ["NOC-*"]
  exclude: ["*-TEST"]
  included_slots: [1, 2]
  excluded_slots: [0]
  only_problem: true
  hide_idle: true
  limit: 25
  display_columns: 2
  auto_exclude_admin_down_slots: true
  min_total_clients: 3
  busy_idle_utilization: 35
  imbalance:
    ratio_threshold: 8
    min_difference: 12
    include_zero_client_slots: false
""",
        encoding="utf-8",
    )

    args = standalone.parse_args(["--config", str(path), "--once"])
    wlc_config, balance_config = standalone.build_configs(args)

    assert wlc_config.host == "192.0.2.10"
    assert wlc_config.username == "admin"
    assert wlc_config.password == "secret"
    assert wlc_config.enable == "enable-secret"
    assert wlc_config.read_timeout == 120
    assert balance_config.refresh_seconds == 15
    assert balance_config.include == ("NOC-*",)
    assert balance_config.exclude == ("*-TEST",)
    assert balance_config.included_slots == (1, 2)
    assert balance_config.excluded_slots == (0,)
    assert balance_config.only_problem is True
    assert balance_config.hide_idle is True
    assert balance_config.limit == 25
    assert balance_config.display_columns == 2
    assert balance_config.auto_exclude_admin_down_slots is True
    assert balance_config.min_total_clients == 3
    assert balance_config.busy_idle_utilization == 35
    assert balance_config.ratio_threshold == 8
    assert balance_config.min_difference == 12
    assert balance_config.include_zero_client_slots is False


def test_standalone_cli_overrides_yaml_config(tmp_path):
    path = tmp_path / "monitor.yaml"
    path.write_text(
        """
wlc:
  host: "192.0.2.10"
  username: "admin"
  password: "secret"
ap_balance:
  refresh_seconds: 30
  limit: 75
""",
        encoding="utf-8",
    )

    args = standalone.parse_args(
        [
            "--config",
            str(path),
            "--host",
            "198.51.100.10",
            "--refresh",
            "10",
            "--limit",
            "5",
            "--columns",
            "2",
            "--include",
            "ENG-*",
            "--exclude-slot",
            "0",
        ]
    )
    wlc_config, balance_config = standalone.build_configs(args)

    assert wlc_config.host == "198.51.100.10"
    assert balance_config.refresh_seconds == 10
    assert balance_config.limit == 5
    assert balance_config.display_columns == 2
    assert balance_config.include == ("ENG-*",)
    assert balance_config.excluded_slots == (0,)


def _make_ap(name, clients):
    return standalone.APLoad(
        name=name,
        radio_mac="0c75.bdb5.6380",
        identity_label="Radio Mac",
        slots=len(clients),
        total_clients=sum(value for value in clients if value is not None),
        slot_loads=[
            standalone.RadioSlotLoad(slot=index, clients=value, utilization=10)
            for index, value in enumerate(clients)
        ],
    )


def test_standalone_table_supports_two_display_columns():
    snapshot = standalone.LoadInfoSnapshot(
        ap_loads=[
            _make_ap("AP-0", [1, 1]),
            _make_ap("AP-1", [2, 2]),
            _make_ap("AP-2", [3, 3]),
            _make_ap("AP-3", [4, 4]),
        ]
    )
    console = Console(record=True, width=220)

    console.print(standalone.build_monitor_table(snapshot, standalone.APBalanceConfig(display_columns=2)))
    rendered = console.export_text()
    header_line = next(line for line in rendered.splitlines() if "┃ AP" in line)

    assert header_line.count("AP") == 2
    assert any("AP-0" in line and "AP-2" in line for line in rendered.splitlines())
    assert any("AP-1" in line and "AP-3" in line for line in rendered.splitlines())


def test_standalone_scores_dual_radio_single_reporting_slot_as_ok():
    score = standalone.score_ap(
        _make_ap("MBY-EVNT-CNTR_HLWY-22", [15, None]),
        standalone.APBalanceConfig(),
    )

    assert score.status == "OK"
    assert score.max_clients == 15
    assert score.min_clients == 15
    assert score.spread == 0
    assert score.reason == "single comparable slot"


def test_standalone_table_does_not_render_no_data_for_dual_radio_single_reporting_slot():
    snapshot = standalone.LoadInfoSnapshot(ap_loads=[_make_ap("MBY-EVNT-CNTR_HLWY-22", [15, None])])
    console = Console(record=True, width=120)

    console.print(standalone.build_monitor_table(snapshot, standalone.APBalanceConfig()))
    rendered = console.export_text()

    assert "MBY-EVNT-CNTR_HLWY-22" in rendered
    assert "OK" in rendered
    assert "NO DATA" not in rendered


def test_standalone_two_column_table_renders_metadata_rows():
    snapshot = standalone.LoadInfoSnapshot(
        ap_loads=[
            _make_ap("AP-0", [1, 1]),
            _make_ap("AP-1", [2, 2]),
            _make_ap("AP-2", [3, 3]),
        ],
        parser_warnings=["line 9: skipped malformed row"],
        poll_error="poll failed: timeout",
    )
    console = Console(record=True, width=220)

    console.print(
        standalone.build_monitor_table(
            snapshot,
            standalone.APBalanceConfig(display_columns=2, limit=2),
        )
    )
    rendered = console.export_text()

    assert "Hidden by limit: 1 OK" in rendered
    assert "poll failed: timeout" in rendered
    assert "line 9: skipped malformed row" in rendered


def test_standalone_collect_once_auto_excludes_admin_down_zero_zero_slots():
    class FakeSession:
        def __init__(self):
            self.admin_down_requests = []

        def get_load_info(self):
            return """
AP Name                           Radio Mac       Slots  Clients       Slot0                   Slot1                   Slot2
                                                                Clients  Utilisation(%)  Clients  Utilisation(%)  Clients  Utilisation(%)
-----------------------------------------------------------------------------------------------------
MBY-EVNT-CNTR_HLWY-22             2416.1b75.2f60   3      24      0        41              23       34              0        0
"""

        def get_admin_down_slots(self, ap_name, slot_numbers):
            self.admin_down_requests.append((ap_name, tuple(slot_numbers)))
            return {2}

    session = FakeSession()

    snapshot = standalone.collect_once(
        session,
        standalone.APBalanceConfig(auto_exclude_admin_down_slots=True),
    )

    assert session.admin_down_requests == [("MBY-EVNT-CNTR_HLWY-22", (2,))]
    assert [(slot.slot, slot.clients, slot.utilization) for slot in snapshot.ap_loads[0].slot_loads] == [
        (0, 0, 41),
        (1, 23, 34),
        (2, None, None),
    ]


def test_standalone_auto_exclude_respects_ap_filters():
    class FakeSession:
        def __init__(self):
            self.admin_down_requests = []

        def get_load_info(self):
            return """
AP Name                           Radio Mac       Slots  Clients       Slot0                   Slot1
                                                                Clients  Utilisation(%)  Clients  Utilisation(%)
-----------------------------------------------------------------------------------------------------
MATCH-AP                          0c75.bdb5.6380   2      0       0        0               0        0
SKIP-AP                           0c75.bdb5.6381   2      0       0        0               0        0
"""

        def get_admin_down_slots(self, ap_name, slot_numbers):
            self.admin_down_requests.append((ap_name, tuple(slot_numbers)))
            return set()

    session = FakeSession()

    standalone.collect_once(
        session,
        standalone.APBalanceConfig(auto_exclude_admin_down_slots=True, include=("MATCH-*",)),
    )

    assert session.admin_down_requests == [("MATCH-AP", (0, 1))]


def test_standalone_get_admin_down_slots_prefers_dot11_summary():
    class FakeConnection:
        def __init__(self):
            self.commands = []

        def send_command_timing(self, command, **kwargs):
            self.commands.append((command, kwargs))
            if command == "show ap dot11 24ghz summary":
                return """
AP Name                           Mac Address     Slot    Admin State    Oper State    Width    Txpwr           Channel                             Mode
---------------------------------------------------------------------------------------------------------------------------------------------------------
MBY-EVNT-CNTR_HLWY-22             2416.1b75.2f60  0       Enabled        Up            20       *6/8 (8 dBm)    (6)*                                Local
"""
            if command == "show ap dot11 5ghz summary":
                return """
AP Name                           Mac Address     Slot    Admin State    Oper State    Width    Txpwr           Channel                             Mode
---------------------------------------------------------------------------------------------------------------------------------------------------------
MBY-EVNT-CNTR_HLWY-22             2416.1b75.2f60  1       Enabled        Up            20       *2/5 (12 dBm)   (56)*                               Local
MBY-EVNT-CNTR_HLWY-22             2416.1b75.2f60  2       Disabled       Down          20       *1/8 (0 dBm)    (36)*                               Local
"""
            return ""

    session = standalone.WLCLoadInfoSession(
        standalone.WLCConfig(host="192.0.2.10", username="u", password="p")
    )
    session.connection = FakeConnection()

    assert session.get_admin_down_slots("MBY-EVNT-CNTR_HLWY-22", (2,)) == {2}
    assert session.get_admin_down_slots("MBY-EVNT-CNTR_HLWY-22", (2,)) == {2}

    assert [command for command, _kwargs in session.connection.commands] == [
        "show ap dot11 24ghz summary",
        "show ap dot11 5ghz summary",
        "show ap dot11 6ghz summary",
    ]


def test_standalone_run_once_reports_startup_steps(monkeypatch):
    output = """
AP Name                           Radio Mac       Slots  Clients       Slot0                   Slot1
                                                                Clients  Utilisation(%)  Clients  Utilisation(%)
-----------------------------------------------------------------------------------------------------
NOC-AP-1                          0c75.bdb5.6380   2      51      1        5               50       80
"""

    class FakeSession:
        def __init__(self, _config):
            self.output = output

        def connect(self):
            pass

        def get_load_info(self):
            return self.output

        def get_admin_down_slots(self, _ap_name, _slot_numbers):
            return set()

        def disconnect(self):
            pass

    class RecordingReporter:
        def __init__(self):
            self.steps = []

        def step(self, message):
            self.steps.append(message)

    reporter = RecordingReporter()
    console = Console(record=True, width=120)
    monkeypatch.setattr(standalone, "WLCLoadInfoSession", FakeSession)

    standalone.run_once(
        standalone.WLCConfig(host="192.0.2.10", username="u", password="p"),
        standalone.APBalanceConfig(auto_exclude_admin_down_slots=True),
        console,
        reporter=reporter,
    )

    assert reporter.steps == [
        "Connecting to WLC 192.0.2.10",
        "Collecting AP radio load-info",
        "Loading radio admin/oper state",
        "Rendering monitor",
    ]
