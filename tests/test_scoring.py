from ap_radio_monitor.models import APBalanceConfig, APLoad, RadioSlotLoad
from ap_radio_monitor.scoring import filter_aps, score_ap, sort_rows


def make_ap(name, clients, utilizations=None):
    utilizations = utilizations or [10 for _ in clients]
    return APLoad(
        name=name,
        radio_mac="0c75.bdb5.6380",
        identity_label="Radio Mac",
        slots=len(clients),
        total_clients=sum(value for value in clients if value is not None),
        slot_loads=[
            RadioSlotLoad(slot=index, clients=value, utilization=utilizations[index])
            for index, value in enumerate(clients)
        ],
    )


def make_ap_with_wlc_total(name, wlc_total, clients, utilizations=None):
    utilizations = utilizations or [10 for _ in clients]
    return APLoad(
        name=name,
        radio_mac="0c75.bdb5.6380",
        identity_label="Radio Mac",
        slots=len(clients),
        total_clients=wlc_total,
        slot_loads=[
            RadioSlotLoad(slot=index, clients=value, utilization=utilizations[index])
            for index, value in enumerate(clients)
        ],
    )


def test_filter_aps_uses_include_and_exclude_patterns():
    aps = [make_ap("NOC-AP-1", [1, 2]), make_ap("LAB-AP-1", [1, 2]), make_ap("NOC-TEST", [1, 2])]
    config = APBalanceConfig(include=("NOC-*",), exclude=("*-TEST",))

    assert [ap.name for ap in filter_aps(aps, config)] == ["NOC-AP-1"]


def test_score_flags_one_vs_fifty_as_imbalanced():
    score = score_ap(make_ap("NOC-AP-1", [1, 50, 0]), APBalanceConfig())

    assert score.status == "IMBALANCED"
    assert score.spread == 50
    assert score.ratio == 50.0


def test_score_zero_vs_fifty_uses_spread_without_ratio():
    score = score_ap(make_ap("NOC-AP-1", [0, 50, None]), APBalanceConfig())

    assert score.status == "IMBALANCED"
    assert score.spread == 50
    assert score.ratio is None


def test_score_returns_idle_for_all_zero_clients():
    score = score_ap(make_ap("ZERO", [0, 0, 0]), APBalanceConfig())

    assert score.status == "IDLE"
    assert score.spread == 0
    assert score.ratio is None


def test_score_returns_busy_idle_for_zero_clients_with_high_utilization():
    score = score_ap(
        make_ap("BUSY-IDLE", [0, 0, 0, None], utilizations=[43, 3, 0, None]),
        APBalanceConfig(busy_idle_utilization=20),
    )

    assert score.status == "BUSY-IDLE"
    assert score.reason == "zero clients with busy channel"


def test_score_ignores_excluded_slots_for_busy_idle():
    score = score_ap(
        make_ap("IDLE", [0, 0, 0], utilizations=[43, 0, 0]),
        APBalanceConfig(excluded_slots=(0,), busy_idle_utilization=20),
    )

    assert score.status == "IDLE"


def test_score_uses_included_slots_for_busy_idle():
    score = score_ap(
        make_ap("IDLE", [0, 0, 0], utilizations=[43, 0, 0]),
        APBalanceConfig(included_slots=(1, 2), busy_idle_utilization=20),
    )

    assert score.status == "IDLE"


def test_score_ignores_unknown_utilization_for_busy_idle():
    score = score_ap(
        make_ap("IDLE", [0, 0, None], utilizations=[None, None, None]),
        APBalanceConfig(busy_idle_utilization=20),
    )

    assert score.status == "IDLE"


def test_score_returns_insufficient_data_for_one_slot():
    assert score_ap(make_ap("ONE", [7, None, None]), APBalanceConfig()).status == "INSUFFICIENT_DATA"


def test_score_returns_ok_for_dual_radio_single_reporting_slot_with_clients():
    score = score_ap(make_ap("ONE-RADIO", [15, None]), APBalanceConfig())

    assert score.status == "OK"
    assert score.max_clients == 15
    assert score.min_clients == 15
    assert score.spread == 0
    assert score.reason == "single comparable slot"


def test_score_uses_slot_total_when_wlc_total_is_zero_but_slots_have_clients():
    ap = make_ap_with_wlc_total("STALE-WLC-TOTAL", 0, [1, 0, 0])

    score = score_ap(ap, APBalanceConfig())

    assert score.status == "OK"
    assert score.max_clients == 1
    assert score.min_clients == 0
    assert score.spread == 1


def test_score_min_clients_uses_filtered_comparable_slot_total():
    ap = make_ap_with_wlc_total("FILTERED", 50, [50, 0, 0])

    score = score_ap(ap, APBalanceConfig(included_slots=(1, 2), min_total_clients=1))

    assert score.status == "IDLE"
    assert score.reason == "zero clients"


def test_score_min_clients_honors_include_zero_client_slots_false():
    ap = make_ap_with_wlc_total("ZERO-EXCLUDED", 50, [50, 0, 0])

    score = score_ap(
        ap,
        APBalanceConfig(
            included_slots=(1, 2),
            min_total_clients=1,
            include_zero_client_slots=False,
        ),
    )

    assert score.status == "INSUFFICIENT_DATA"
    assert score.reason == "below minimum clients"


def test_score_ignores_auto_excluded_none_slots():
    ap = make_ap_with_wlc_total("AUTO-EXCLUDED", 6, [None, 1, 0])

    score = score_ap(ap, APBalanceConfig(included_slots=(0, 1, 2)))

    assert score.status == "OK"
    assert score.max_clients == 1
    assert score.min_clients == 0
    assert score.spread == 1


def test_slot_filters_limit_comparable_slots():
    config = APBalanceConfig(included_slots=(1, 2))
    score = score_ap(make_ap("NOC-AP-1", [50, 4, 5]), config)

    assert score.status == "OK"
    assert score.spread == 1


def test_sort_rows_places_imbalanced_first():
    aps = [
        make_ap("OK", [10, 12]),
        make_ap("BAD", [1, 50]),
        make_ap("BUSY", [0, 0], utilizations=[30, 0]),
        make_ap("WARN", [4, 14]),
        make_ap("IDLE", [0, 0], utilizations=[0, 0]),
    ]
    rows = sort_rows([(ap, score_ap(ap, APBalanceConfig())) for ap in aps])

    assert [ap.name for ap, _score in rows] == ["BAD", "BUSY", "WARN", "OK", "IDLE"]
