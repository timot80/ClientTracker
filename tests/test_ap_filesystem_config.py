from ap_filesystem_audit.config import load_config


def test_load_config_reads_wlcs_ap_credentials_and_defaults(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        """
wifiops:
  wlc_concurrency: 4
wlcs:
  - name: wlc-1
    host: 192.0.2.10
    username: wlc-user
    password: wlc-pass
ap:
  username: ap-user
  password: ap-pass
  enable: ap-enable
ap_filesystems:
  include: ["MBY-*"]
  exclude: ["*TEST*"]
  min_used_percent: 90
  show_all: true
  ap_concurrency: 7
""",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.wlc_targets[0].name == "wlc-1"
    assert config.ap_credentials.username == "ap-user"
    assert config.ap_credentials.password == "ap-pass"
    assert config.ap_credentials.enable == "ap-enable"
    assert config.audit.include == ("MBY-*",)
    assert config.audit.exclude == ("*TEST*",)
    assert config.audit.min_used_percent == 90
    assert config.audit.show_all is True
    assert config.audit.ap_concurrency == 7
    assert config.wlc_concurrency == 4
