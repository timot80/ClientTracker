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
