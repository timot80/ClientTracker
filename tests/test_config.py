import pytest

from ap_radio_monitor.config import load_config as load_radio_config
from client_tracker.config import load_config as load_client_config


CLIENT_TRACKER_ENV = (
    "CLIENT_TRACKER_WLC_HOST",
    "CLIENT_TRACKER_WLC_USERNAME",
    "CLIENT_TRACKER_WLC_PASSWORD",
    "CLIENT_TRACKER_WLC_ENABLE",
    "CLIENT_TRACKER_AP_USERNAME",
    "CLIENT_TRACKER_AP_PASSWORD",
    "CLIENT_TRACKER_AP_ENABLE",
)


def _clear_client_tracker_env(monkeypatch):
    for name in CLIENT_TRACKER_ENV:
        monkeypatch.delenv(name, raising=False)


def _profile_config() -> str:
    return """
credentials:
  profiles:
    c9800-admin:
      username: "netops-admin"
      password_keyring: "wifiops:profile:c9800-admin:password"
      enable_keyring: "wifiops:profile:c9800-admin:enable"
wlc:
  host: "192.0.2.10"
  credential_profile: "c9800-admin"
ap:
  credential_profile: "c9800-admin"
"""


def _mock_keyring_get_password(monkeypatch, values):
    from wifiops import credentials

    def fake_get_password(service, key):
        assert service == "wifiops"
        return values.get(key)

    monkeypatch.setattr(credentials.keyring, "get_password", fake_get_password)


def test_load_client_config_resolves_profile_credentials(tmp_path, monkeypatch):
    _clear_client_tracker_env(monkeypatch)
    path = tmp_path / "config.yaml"
    path.write_text(_profile_config(), encoding="utf-8")
    _mock_keyring_get_password(
        monkeypatch,
        {
            "profile:c9800-admin:password": "profile-password",
            "profile:c9800-admin:enable": "profile-enable",
        },
    )

    cfg = load_client_config(path, require_infra=True)

    assert cfg.wlc.username == "netops-admin"
    assert cfg.wlc.password == "profile-password"
    assert cfg.wlc.enable == "profile-enable"
    assert cfg.ap.username == "netops-admin"
    assert cfg.ap.password == "profile-password"
    assert cfg.ap.enable == "profile-enable"


def test_load_client_config_resolves_multi_wlc_targets(tmp_path, monkeypatch):
    _clear_client_tracker_env(monkeypatch)
    path = tmp_path / "config.yaml"
    path.write_text(
        """
credentials:
  profiles:
    c9800-admin:
      username: "netops-admin"
      password_keyring: "wifiops:profile:c9800-admin:password"
wlcs:
  - name: "mby-1"
    host: "192.0.2.10"
    credential_profile: "c9800-admin"
  - name: "mby-2"
    host: "192.0.2.11"
    credential_profile: "c9800-admin"
ap:
  credential_profile: "c9800-admin"
""",
        encoding="utf-8",
    )
    _mock_keyring_get_password(
        monkeypatch,
        {
            "profile:c9800-admin:password": "profile-password",
        },
    )

    cfg = load_client_config(path, require_infra=True)

    assert [target.name for target in cfg.wlc_targets] == ["mby-1", "mby-2"]
    assert [target.config.host for target in cfg.wlc_targets] == ["192.0.2.10", "192.0.2.11"]
    assert cfg.wlc.host == "192.0.2.10"
    assert cfg.wlc.username == "netops-admin"
    assert cfg.wlc.password == "profile-password"


def test_load_client_config_selects_named_multi_wlc_targets(tmp_path, monkeypatch):
    _clear_client_tracker_env(monkeypatch)
    path = tmp_path / "config.yaml"
    path.write_text(
        """
wlcs:
  - name: "mby-1"
    host: "192.0.2.10"
    username: "admin"
    password: "secret"
  - name: "mby-2"
    host: "192.0.2.11"
    username: "admin"
    password: "secret"
ap:
  username: "ap-admin"
  password: "ap-secret"
""",
        encoding="utf-8",
    )

    cfg = load_client_config(path, require_infra=True, wlc_names=("mby-2",))

    assert [target.name for target in cfg.wlc_targets] == ["mby-2"]
    assert cfg.wlc.host == "192.0.2.11"


def test_load_client_config_env_overrides_profile_and_keyring(tmp_path, monkeypatch):
    _clear_client_tracker_env(monkeypatch)
    path = tmp_path / "config.yaml"
    path.write_text(_profile_config(), encoding="utf-8")
    monkeypatch.setenv("CLIENT_TRACKER_WLC_PASSWORD", "env-password")
    monkeypatch.setenv("CLIENT_TRACKER_AP_USERNAME", "env-ap-admin")
    _mock_keyring_get_password(
        monkeypatch,
        {
            "profile:c9800-admin:password": "profile-password",
            "profile:c9800-admin:enable": "profile-enable",
        },
    )

    cfg = load_client_config(path, require_infra=True)

    assert cfg.wlc.username == "netops-admin"
    assert cfg.wlc.password == "env-password"
    assert cfg.ap.username == "env-ap-admin"
    assert cfg.ap.password == "profile-password"


def test_load_client_config_env_overrides_missing_profile(tmp_path, monkeypatch):
    _clear_client_tracker_env(monkeypatch)
    path = tmp_path / "config.yaml"
    path.write_text(
        """
wlc:
  host: "192.0.2.10"
  credential_profile: "missing-profile"
ap:
  credential_profile: "missing-profile"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLIENT_TRACKER_WLC_USERNAME", "env-wlc-admin")
    monkeypatch.setenv("CLIENT_TRACKER_WLC_PASSWORD", "env-wlc-password")
    monkeypatch.setenv("CLIENT_TRACKER_WLC_ENABLE", "env-wlc-enable")
    monkeypatch.setenv("CLIENT_TRACKER_AP_USERNAME", "env-ap-admin")
    monkeypatch.setenv("CLIENT_TRACKER_AP_PASSWORD", "env-ap-password")
    monkeypatch.setenv("CLIENT_TRACKER_AP_ENABLE", "env-ap-enable")

    cfg = load_client_config(path, require_infra=True)

    assert cfg.wlc.username == "env-wlc-admin"
    assert cfg.wlc.password == "env-wlc-password"
    assert cfg.wlc.enable == "env-wlc-enable"
    assert cfg.ap.username == "env-ap-admin"
    assert cfg.ap.password == "env-ap-password"
    assert cfg.ap.enable == "env-ap-enable"


def test_load_client_config_required_env_overrides_missing_profile_without_enable(
    tmp_path, monkeypatch
):
    _clear_client_tracker_env(monkeypatch)
    path = tmp_path / "config.yaml"
    path.write_text(
        """
wlc:
  host: "192.0.2.10"
  credential_profile: "missing-profile"
ap:
  credential_profile: "missing-profile"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLIENT_TRACKER_WLC_USERNAME", "env-wlc-admin")
    monkeypatch.setenv("CLIENT_TRACKER_WLC_PASSWORD", "env-wlc-password")
    monkeypatch.setenv("CLIENT_TRACKER_AP_USERNAME", "env-ap-admin")
    monkeypatch.setenv("CLIENT_TRACKER_AP_PASSWORD", "env-ap-password")

    cfg = load_client_config(path, require_infra=True)

    assert cfg.wlc.username == "env-wlc-admin"
    assert cfg.wlc.password == "env-wlc-password"
    assert cfg.wlc.enable == ""
    assert cfg.ap.username == "env-ap-admin"
    assert cfg.ap.password == "env-ap-password"
    assert cfg.ap.enable == ""


def test_load_client_config_device_keyring_overrides_profile_secret(tmp_path, monkeypatch):
    _clear_client_tracker_env(monkeypatch)
    path = tmp_path / "config.yaml"
    path.write_text(
        """
credentials:
  profiles:
    c9800-admin:
      username: "netops-admin"
      password_keyring: "wifiops:profile:c9800-admin:password"
wlc:
  host: "192.0.2.10"
  credential_profile: "c9800-admin"
  password_keyring: "wifiops:wlc:192.0.2.10:netops-admin:password"
ap:
  credential_profile: "c9800-admin"
""",
        encoding="utf-8",
    )
    _mock_keyring_get_password(
        monkeypatch,
        {
            "profile:c9800-admin:password": "profile-password",
            "wlc:192.0.2.10:netops-admin:password": "device-password",
        },
    )

    cfg = load_client_config(path, require_infra=True)

    assert cfg.wlc.username == "netops-admin"
    assert cfg.wlc.password == "device-password"
    assert cfg.ap.password == "profile-password"


def test_load_client_config_missing_profile_exits_with_clear_error(tmp_path, monkeypatch):
    _clear_client_tracker_env(monkeypatch)
    path = tmp_path / "config.yaml"
    path.write_text(
        """
wlc:
  host: "192.0.2.10"
  credential_profile: "missing-profile"
ap:
  username: "ap-admin"
  password: "ap-password"
""",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="Unknown credential profile 'missing-profile'"):
        load_client_config(path, require_infra=True)


def test_load_client_config_invalid_profile_name_exits_with_clear_error(tmp_path, monkeypatch):
    _clear_client_tracker_env(monkeypatch)
    path = tmp_path / "config.yaml"
    path.write_text(
        """
credentials:
  profiles:
    bad/profile:
      username: "netops-admin"
      password: "secret"
wlc:
  host: "192.0.2.10"
  credential_profile: "bad/profile"
ap:
  username: "ap-admin"
  password: "ap-password"
""",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="Invalid credential profile name 'bad/profile'"):
        load_client_config(path, require_infra=True)


def test_load_radio_config_resolves_profile_credentials(tmp_path, monkeypatch):
    _clear_client_tracker_env(monkeypatch)
    path = tmp_path / "config.yaml"
    path.write_text(_profile_config(), encoding="utf-8")
    _mock_keyring_get_password(
        monkeypatch,
        {
            "profile:c9800-admin:password": "profile-password",
            "profile:c9800-admin:enable": "profile-enable",
        },
    )

    config = load_radio_config(path)

    assert config.wlc.username == "netops-admin"
    assert config.wlc.password == "profile-password"
    assert config.wlc.enable == "profile-enable"


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
  display_columns: 2
  auto_exclude_admin_down_slots: true
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
    assert config.ap_balance.display_columns == 2
    assert config.ap_balance.auto_exclude_admin_down_slots is True
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


def test_load_client_config_does_not_resolve_keyring_for_local_mode(tmp_path, monkeypatch):
    _clear_client_tracker_env(monkeypatch)
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(_profile_config(), encoding="utf-8")

    def fail_get_password(service, key):
        raise AssertionError("local-only config load should not read keyring secrets")

    from wifiops import credentials

    monkeypatch.setattr(credentials.keyring, "get_password", fail_get_password)

    cfg = load_client_config(cfg_path, require_infra=False)

    assert cfg.wlc.host == "192.0.2.10"
    assert cfg.wlc.username == ""
    assert cfg.ap.password == ""
