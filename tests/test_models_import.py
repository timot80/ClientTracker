from ap_radio_monitor.models import (
    APBalanceConfig,
    APLoad,
    BalanceScore,
    LoadInfoSnapshot,
    RadioSlotLoad,
)


def test_models_import_without_config_or_network_access():
    slot = RadioSlotLoad(slot=0, clients=5, utilization=12)
    ap = APLoad(
        name="NOC-AP-1",
        radio_mac="0c75.bdb5.6380",
        identity_label="Radio Mac",
        slots=3,
        total_clients=5,
        slot_loads=[slot],
    )
    snapshot = LoadInfoSnapshot(ap_loads=[ap])
    config = APBalanceConfig()
    score = BalanceScore(status="OK", max_clients=5, min_clients=5, spread=0, ratio=1.0)

    assert snapshot.ap_loads[0].name == "NOC-AP-1"
    assert config.refresh_seconds == 30
    assert score.status == "OK"
