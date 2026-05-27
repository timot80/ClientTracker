import pytest

from ap_radio_monitor.config import load_config


def test_load_config_applies_defaults(tmp_path):
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

    config = load_config(path)

    assert config.wlc.host == "192.0.2.10"
    assert config.wlc.enable == ""
    assert config.ap_balance.refresh_seconds == 30
    assert config.ap_balance.ratio_threshold == 10


def test_load_config_reads_ap_balance_options(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        """
wlc:
  host: "192.0.2.10"
  username: "admin"
  password: "secret"
ap_balance:
  refresh_seconds: 15
  include: ["NOC-*"]
  exclude: ["*-TEST"]
  included_slots: [1, 2]
  excluded_slots: [0]
  only_imbalanced: true
  min_total_clients: 5
  imbalance:
    ratio_threshold: 8
    min_difference: 12
    include_zero_client_slots: false
""",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.ap_balance.refresh_seconds == 15
    assert config.ap_balance.include == ("NOC-*",)
    assert config.ap_balance.excluded_slots == (0,)
    assert config.ap_balance.include_zero_client_slots is False


def test_load_config_requires_wlc_credentials(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("wlc: {host: 192.0.2.10}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="wlc.username"):
        load_config(path)
