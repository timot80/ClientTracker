from client_tracker.config import load_config


def test_load_config_uses_yaml_and_env_overrides(tmp_path, monkeypatch):
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

    cfg = load_config(cfg_path, require_infra=True)

    assert cfg.wlc.host == "192.0.2.10"
    assert cfg.wlc.password == "env-password"
    assert cfg.ap.username == "ap-admin"
    assert cfg.local.ping_host == "1.1.1.1"
    assert cfg.local.sound_alerts is False
    assert cfg.local.identity_helper_path == "/Users/test/Applications/wifi-unredactor.app/Contents/MacOS/wifi-unredactor"


def test_load_config_does_not_require_file_for_local_mode(tmp_path):
    cfg = load_config(tmp_path / "missing.yaml", require_infra=False)

    assert cfg.wlc.host == ""
    assert cfg.local.sound_alerts is True
