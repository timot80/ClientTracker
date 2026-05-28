from __future__ import annotations

from unittest.mock import Mock, call, patch

import pytest
import yaml

from wifiops import __version__
from wifiops.cli import main


def test_version_import_is_available():
    assert __version__ == "0.1.0"


def test_help_mentions_top_level_command_groups(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])

    captured = capsys.readouterr()

    assert exc.value.code == 0
    assert "c9800" in captured.out
    assert "client" in captured.out
    assert "check" in captured.out


def test_credentials_set_profile_writes_yaml_and_keyring_secrets(tmp_path, capsys):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("wlc:\n  host: 192.0.2.10\n", encoding="utf-8")

    with (
        patch("wifiops.credentials.keyring.set_password") as set_password,
        patch("getpass.getpass", side_effect=["profile-password", "profile-enable"]),
    ):
        exit_code = main(
            [
                "credentials",
                "set-profile",
                "c9800-admin",
                "--username",
                "netops-admin",
                "--config",
                str(config_path),
            ]
        )

    captured = capsys.readouterr()
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert data["wlc"]["host"] == "192.0.2.10"
    assert data["credentials"]["profiles"]["c9800-admin"] == {
        "username": "netops-admin",
        "password_keyring": "wifiops:profile:c9800-admin:password",
        "enable_keyring": "wifiops:profile:c9800-admin:enable",
    }
    assert set_password.call_args_list == [
        call("wifiops", "profile:c9800-admin:password", "profile-password"),
        call("wifiops", "profile:c9800-admin:enable", "profile-enable"),
    ]
    assert "profile-password" not in captured.out
    assert "c9800-admin" in captured.out


def test_credentials_show_profiles_reads_yaml_index(tmp_path, capsys):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
credentials:
  profiles:
    c9800-admin:
      username: "netops-admin"
      password_keyring: "wifiops:profile:c9800-admin:password"
""",
        encoding="utf-8",
    )

    with patch("wifiops.credentials.keyring.get_password") as get_password:
        exit_code = main(["credentials", "show-profiles", "--config", str(config_path)])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "c9800-admin" in captured.out
    assert "netops-admin" in captured.out
    get_password.assert_not_called()


def test_credentials_delete_profile_removes_yaml_and_known_keyring_entries(tmp_path, capsys):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
credentials:
  profiles:
    c9800-admin:
      username: "netops-admin"
      password_keyring: "wifiops:profile:c9800-admin:password"
      enable_keyring: "wifiops:profile:c9800-admin:enable"
wlc:
  credential_profile: "c9800-admin"
""",
        encoding="utf-8",
    )

    with patch("wifiops.credentials.keyring.delete_password") as delete_password:
        exit_code = main(["credentials", "delete-profile", "c9800-admin", "--config", str(config_path)])

    captured = capsys.readouterr()
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "c9800-admin" not in data.get("credentials", {}).get("profiles", {})
    assert data["wlc"]["credential_profile"] == "c9800-admin"
    assert delete_password.call_args_list == [
        call("wifiops", "profile:c9800-admin:password"),
        call("wifiops", "profile:c9800-admin:enable"),
    ]
    assert "may now be invalid" in captured.out


def test_credentials_set_profile_rejects_invalid_profile_name_before_writing(tmp_path):
    config_path = tmp_path / "config.yaml"

    with (
        patch("wifiops.credentials.keyring.set_password") as set_password,
        patch("getpass.getpass") as getpass,
        pytest.raises(SystemExit),
    ):
        main(
            [
                "credentials",
                "set-profile",
                "bad/profile",
                "--username",
                "netops-admin",
                "--config",
                str(config_path),
            ]
        )

    assert not config_path.exists()
    set_password.assert_not_called()
    getpass.assert_not_called()


def test_credentials_set_profile_without_enable_deletes_previous_enable_secret(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
credentials:
  profiles:
    c9800-admin:
      username: "old-admin"
      password_keyring: "wifiops:profile:c9800-admin:password"
      enable_keyring: "wifiops:profile:c9800-admin:enable"
""",
        encoding="utf-8",
    )

    with (
        patch("wifiops.credentials.keyring.set_password") as set_password,
        patch("wifiops.credentials.keyring.delete_password") as delete_password,
        patch("getpass.getpass", side_effect=["new-password", ""]),
    ):
        exit_code = main(
            [
                "credentials",
                "set-profile",
                "c9800-admin",
                "--username",
                "netops-admin",
                "--config",
                str(config_path),
            ]
        )

    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert data["credentials"]["profiles"]["c9800-admin"] == {
        "username": "netops-admin",
        "password_keyring": "wifiops:profile:c9800-admin:password",
    }
    set_password.assert_called_once_with("wifiops", "profile:c9800-admin:password", "new-password")
    delete_password.assert_called_once_with("wifiops", "profile:c9800-admin:enable")


def test_c9800_radio_delegates_to_ap_radio_monitor():
    radio_main = Mock(return_value=0)

    with patch("ap_radio_monitor.cli.main", radio_main):
        exit_code = main(["c9800", "radio", "--once", "--config", "config.yaml"])

    assert exit_code == 0
    radio_main.assert_called_once_with(["--once", "--config", "config.yaml"])


def test_c9800_radio_preserves_current_monitor_options():
    radio_main = Mock(return_value=0)

    with patch("ap_radio_monitor.cli.main", radio_main):
        exit_code = main(
            [
                "c9800",
                "radio",
                "--only-problem",
                "--hide-idle",
                "--limit",
                "10",
                "--columns",
                "2",
                "--auto-exclude-admin-down-slots",
                "--busy-idle-util",
                "25",
            ]
        )

    assert exit_code == 0
    radio_main.assert_called_once_with(
        [
            "--only-problem",
            "--hide-idle",
            "--limit",
            "10",
            "--columns",
            "2",
            "--auto-exclude-admin-down-slots",
            "--busy-idle-util",
            "25",
        ]
    )


def test_c9800_ap_ports_delegates_to_ap_port_audit():
    port_main = Mock(return_value=0)

    with patch("ap_port_audit.cli.main", port_main):
        exit_code = main(["c9800", "ap-ports", "--config", "config.yaml", "--include", "MBY-*"])

    assert exit_code == 0
    port_main.assert_called_once_with(["--config", "config.yaml", "--include", "MBY-*"])


def test_c9800_ap_ports_preserves_multi_wlc_options():
    port_main = Mock(return_value=0)

    with patch("ap_port_audit.cli.main", port_main):
        exit_code = main(
            [
                "c9800",
                "ap-ports",
                "--wlc",
                "mby-1",
                "--wlc",
                "mby-2",
                "--wlc-concurrency",
                "5",
            ]
        )

    assert exit_code == 0
    port_main.assert_called_once_with(["--wlc", "mby-1", "--wlc", "mby-2", "--wlc-concurrency", "5"])


def test_ap_filesystems_delegates_to_ap_filesystem_audit():
    fs_main = Mock(return_value=0)

    with patch("ap_filesystem_audit.cli.main", fs_main):
        exit_code = main(["ap", "filesystems", "--config", "config.yaml", "--include", "MBY-*"])

    assert exit_code == 0
    fs_main.assert_called_once_with(["--config", "config.yaml", "--include", "MBY-*"])


def test_ap_filesystems_preserves_reload_options():
    fs_main = Mock(return_value=0)

    with patch("ap_filesystem_audit.cli.main", fs_main):
        exit_code = main(
            [
                "ap",
                "filesystems",
                "--reload-full-tmp",
                "--confirm-reload-full-tmp",
            ]
        )

    assert exit_code == 0
    fs_main.assert_called_once_with(["--reload-full-tmp", "--confirm-reload-full-tmp"])


def test_c9800_client_defaults_to_infra_mode():
    client_main = Mock(return_value=None)

    with patch("client_tracker.cli.main", client_main):
        exit_code = main(["c9800", "client", "aa:bb:cc:dd:ee:ff"])

    assert exit_code == 0
    client_main.assert_called_once_with(["aa:bb:cc:dd:ee:ff", "--mode", "infra"])


def test_c9800_client_preserves_combined_mode_and_interval():
    client_main = Mock(return_value=None)

    with (
        patch("wifiops.cli._macos_sudo_ready", return_value=True),
        patch("client_tracker.cli.main", client_main),
    ):
        exit_code = main(
            [
                "c9800",
                "client",
                "aa:bb:cc:dd:ee:ff",
                "--mode",
                "combined",
                "--interval",
                "2",
            ]
        )

    assert exit_code == 0
    client_main.assert_called_once_with(
        ["aa:bb:cc:dd:ee:ff", "--mode", "combined", "--interval", "2"]
    )


def test_c9800_client_rejects_local_mode():
    with pytest.raises(SystemExit):
        main(["c9800", "client", "aa:bb:cc:dd:ee:ff", "--mode", "local"])


def test_client_local_delegates_to_client_tracker_local_mode():
    client_main = Mock(return_value=None)

    with (
        patch("wifiops.cli._macos_sudo_ready", return_value=True),
        patch("client_tracker.cli.main", client_main),
    ):
        exit_code = main(["client", "local", "--interval", "1", "--log", "local.csv"])

    assert exit_code == 0
    client_main.assert_called_once_with(
        ["--mode", "local", "--interval", "1", "--log", "local.csv"]
    )


def test_client_local_uses_wifiops_config_env(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    monkeypatch.setenv("WIFIOPS_CONFIG", str(config_path))
    client_main = Mock(return_value=None)

    with (
        patch("wifiops.cli._macos_sudo_ready", return_value=True),
        patch("client_tracker.cli.main", client_main),
    ):
        exit_code = main(["client", "local"])

    assert exit_code == 0
    client_main.assert_called_once_with(["--mode", "local", "--config", str(config_path)])


def test_client_local_exits_before_live_ui_when_macos_sudo_is_not_ready(capsys):
    client_main = Mock(return_value=None)
    sudo_ready = Mock(return_value=False)

    with (
        patch("wifiops.cli.sys.platform", "darwin"),
        patch("wifiops.cli._macos_sudo_ready", sudo_ready, create=True),
        patch("client_tracker.cli.main", client_main),
    ):
        exit_code = main(["client", "local"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Run 'sudo -v' first" in captured.err
    sudo_ready.assert_called_once_with()
    client_main.assert_not_called()


def test_c9800_combined_exits_before_live_ui_when_macos_sudo_is_not_ready(capsys):
    client_main = Mock(return_value=None)
    sudo_ready = Mock(return_value=False)

    with (
        patch("wifiops.cli.sys.platform", "darwin"),
        patch("wifiops.cli._macos_sudo_ready", sudo_ready, create=True),
        patch("client_tracker.cli.main", client_main),
    ):
        exit_code = main(["c9800", "client", "aa:bb:cc:dd:ee:ff", "--mode", "combined"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Run 'sudo -v' first" in captured.err
    sudo_ready.assert_called_once_with()
    client_main.assert_not_called()


def test_c9800_infra_does_not_check_macos_sudo():
    client_main = Mock(return_value=None)
    sudo_ready = Mock(return_value=False)

    with (
        patch("wifiops.cli.sys.platform", "darwin"),
        patch("wifiops.cli._macos_sudo_ready", sudo_ready, create=True),
        patch("client_tracker.cli.main", client_main),
    ):
        exit_code = main(["c9800", "client", "aa:bb:cc:dd:ee:ff"])

    assert exit_code == 0
    sudo_ready.assert_not_called()
    client_main.assert_called_once_with(["aa:bb:cc:dd:ee:ff", "--mode", "infra"])


def test_check_delegates_to_client_tracker_check():
    client_main = Mock(return_value=None)

    with patch("client_tracker.cli.main", client_main):
        exit_code = main(["check"])

    assert exit_code == 0
    client_main.assert_called_once_with(["--check"])


def test_check_uses_wifiops_config_env(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    monkeypatch.setenv("WIFIOPS_CONFIG", str(config_path))
    client_main = Mock(return_value=None)

    with patch("client_tracker.cli.main", client_main):
        exit_code = main(["check"])

    assert exit_code == 0
    client_main.assert_called_once_with(["--check", "--config", str(config_path)])
