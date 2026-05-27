import pytest

from ap_radio_monitor.config import load_config as load_radio_config
from client_tracker.config import load_config as load_client_config


def test_load_radio_config_applies_defaults(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        """
wlc:
  host: "192.0.2.10"
  username: "admin"
  password: "secret"
""",
        encoding="utf-8",
    )

    config = load_radio_config(path)

    assert config.wlc.host == "192.0.2.10"
    assert config.wlc.enable == ""
    assert config.ap_balance.refresh_seconds == 30
    assert config.ap_balance.ratio_threshold == 10
    assert config.ap_balance.limit == 75
    assert config.ap_balance.busy_idle_utilization == 20


def test_load_radio_config_reads_ap_balance_options(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        """
wlc:
  host: "192.0.2.10"
  username: "admin"
  password: "secret"
  read_timeout: 120
ap_balance:
  refresh_seconds: 15
  include: ["NOC-*"]
  exclude: ["*-TEST"]
  included_slots: [1, 2]
  excluded_slots: [0]
  only_imbalanced: true
  only_problem: true
  show_idle: true
  min_total_clients: 5
  busy_idle_utilization: 25
  limit: 10
  imbalance:
    ratio_threshold: 8
    min_difference: 12
    include_zero_client_slots: false
""",
        encoding="utf-8",
    )

    config = load_radio_config(path)

    assert config.ap_balance.refresh_seconds == 15
    assert config.wlc.read_timeout == 120
    assert config.ap_balance.include == ("NOC-*",)
    assert config.ap_balance.excluded_slots == (0,)
    assert config.ap_balance.include_zero_client_slots is False
    assert config.ap_balance.only_problem is True
    assert config.ap_balance.show_idle is True
    assert config.ap_balance.limit == 10
    assert config.ap_balance.busy_idle_utilization == 25


def test_load_radio_config_requires_wlc_credentials(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("wlc: {host: 192.0.2.10}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="wlc.username"):
        load_radio_config(path)


def test_load_client_config_uses_yaml_and_env_overrides(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        """
wlc:
  host: "192.0.2.10"
  username: "admin"
  password: "file-password"
  enable: "file-enable"
ap:
  username: "ap-admin"
  password: "ap-file-password"
  enable: "ap-file-enable"
local:
  ping_host: "1.1.1.1"
  sound_alerts: false
  identity_helper_path: "/Users/test/Applications/wifi-unredactor.app/Contents/MacOS/wifi-unredactor"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLIENT_TRACKER_WLC_PASSWORD", "env-password")

    cfg = load_client_config(cfg_path, require_infra=True)

    assert cfg.wlc.host == "192.0.2.10"
    assert cfg.wlc.password == "env-password"
    assert cfg.ap.username == "ap-admin"
    assert cfg.local.ping_host == "1.1.1.1"
    assert cfg.local.sound_alerts is False
    assert cfg.local.identity_helper_path == "/Users/test/Applications/wifi-unredactor.app/Contents/MacOS/wifi-unredactor"


def test_load_client_config_does_not_require_file_for_local_mode(tmp_path):
    cfg = load_client_config(tmp_path / "missing.yaml", require_infra=False)

    assert cfg.wlc.host == ""
    assert cfg.local.sound_alerts is True
