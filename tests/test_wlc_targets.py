import pytest

from wifiops.wlc_targets import WlcTargetConfigError, resolve_wlc_targets, select_wlc_targets


def test_single_wlc_resolves_to_default_target():
    raw = {
        "wlc": {
            "host": "192.0.2.10",
            "username": "admin",
            "password": "secret",
            "read_timeout": 120,
        }
    }

    targets = resolve_wlc_targets(raw, env={})

    assert len(targets) == 1
    assert targets[0].name == "default"
    assert targets[0].config.host == "192.0.2.10"
    assert targets[0].config.username == "admin"
    assert targets[0].config.password == "secret"
    assert targets[0].config.read_timeout == 120


def test_single_wlc_uses_explicit_name():
    raw = {"wlc": {"name": "mby-1", "host": "192.0.2.10", "username": "admin", "password": "secret"}}

    assert resolve_wlc_targets(raw, env={})[0].name == "mby-1"


def test_wlcs_resolves_all_targets_and_wins_over_wlc():
    raw = {
        "wlc": {"host": "192.0.2.99", "username": "old", "password": "old"},
        "wlcs": [
            {"name": "mby-1", "host": "192.0.2.10", "username": "admin", "password": "secret"},
            {"name": "mby-2", "host": "192.0.2.11", "username": "admin", "password": "secret"},
        ],
    }

    targets = resolve_wlc_targets(raw, env={})

    assert [target.name for target in targets] == ["mby-1", "mby-2"]
    assert [target.config.host for target in targets] == ["192.0.2.10", "192.0.2.11"]


def test_wlcs_ignore_legacy_host_env_override():
    raw = {
        "wlcs": [
            {"name": "mby-1", "host": "192.0.2.10", "username": "admin", "password": "secret"},
            {"name": "mby-2", "host": "192.0.2.11", "username": "admin", "password": "secret"},
        ],
    }

    targets = resolve_wlc_targets(raw, env={"CLIENT_TRACKER_WLC_HOST": "192.0.2.99"})

    assert [target.config.host for target in targets] == ["192.0.2.10", "192.0.2.11"]


def test_single_wlc_preserves_legacy_host_env_override():
    raw = {"wlc": {"host": "192.0.2.10", "username": "admin", "password": "secret"}}

    targets = resolve_wlc_targets(raw, env={"CLIENT_TRACKER_WLC_HOST": "192.0.2.99"})

    assert targets[0].config.host == "192.0.2.99"


def test_wlcs_rejects_missing_name_and_duplicate_name():
    with pytest.raises(WlcTargetConfigError, match="wlcs must contain at least one WLC"):
        resolve_wlc_targets({"wlcs": []}, env={})

    with pytest.raises(WlcTargetConfigError, match="wlcs\\[0\\].name"):
        resolve_wlc_targets(
            {"wlcs": [{"host": "192.0.2.10", "username": "admin", "password": "secret"}]},
            env={},
        )

    with pytest.raises(WlcTargetConfigError, match="Duplicate WLC name"):
        resolve_wlc_targets(
            {
                "wlcs": [
                    {"name": "mby-1", "host": "192.0.2.10", "username": "admin", "password": "secret"},
                    {"name": "mby-1", "host": "192.0.2.11", "username": "admin", "password": "secret"},
                ]
            },
            env={},
        )


def test_select_wlc_targets_preserves_requested_order_and_rejects_unknown():
    targets = resolve_wlc_targets(
        {
            "wlcs": [
                {"name": "mby-1", "host": "192.0.2.10", "username": "admin", "password": "secret"},
                {"name": "mby-2", "host": "192.0.2.11", "username": "admin", "password": "secret"},
            ]
        },
        env={},
    )

    selected = select_wlc_targets(targets, ("mby-2", "mby-1"))

    assert [target.name for target in selected] == ["mby-2", "mby-1"]
    with pytest.raises(WlcTargetConfigError, match="Unknown WLC"):
        select_wlc_targets(targets, ("missing",))
