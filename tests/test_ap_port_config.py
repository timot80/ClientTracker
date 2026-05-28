from ap_port_audit.config import load_config


def test_load_config_reads_wlc_and_ap_ports(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        """
wlc:
  host: "192.0.2.10"
  username: "admin"
  password: "secret"
  read_timeout: 120
ap_ports:
  include: ["MBY-*"]
  exclude: ["*-TEST"]
  show_all: true
  speed_threshold: 2500
""",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.wlc.host == "192.0.2.10"
    assert config.wlc.username == "admin"
    assert config.wlc.password == "secret"
    assert config.wlc.read_timeout == 120
    assert config.ap_ports.include == ("MBY-*",)
    assert config.ap_ports.exclude == ("*-TEST",)
    assert config.ap_ports.show_all is True
    assert config.ap_ports.speed_threshold == 2500


def test_load_config_reads_multi_wlc_targets_and_concurrency(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        """
wifiops:
  wlc_concurrency: 5
wlcs:
  - name: "mby-1"
    host: "192.0.2.10"
    username: "admin"
    password: "secret"
  - name: "mby-2"
    host: "192.0.2.11"
    username: "admin"
    password: "secret"
ap_ports:
  speed_threshold: 2500
""",
        encoding="utf-8",
    )

    config = load_config(path)

    assert [target.name for target in config.wlc_targets] == ["mby-1", "mby-2"]
    assert [target.config.host for target in config.wlc_targets] == ["192.0.2.10", "192.0.2.11"]
    assert config.wlc_concurrency == 5
    assert config.ap_ports.speed_threshold == 2500
