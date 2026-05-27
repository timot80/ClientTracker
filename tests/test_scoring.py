from ap_radio_monitor.models import APBalanceConfig, APLoad, RadioSlotLoad
from ap_radio_monitor.scoring import filter_aps, score_ap, sort_rows


def make_ap(name, clients):
    return APLoad(
        name=name,
        radio_mac="0c75.bdb5.6380",
        identity_label="Radio Mac",
        slots=len(clients),
        total_clients=sum(value for value in clients if value is not None),
        slot_loads=[
            RadioSlotLoad(slot=index, clients=value, utilization=10)
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


def test_score_returns_insufficient_data_for_all_zero_or_one_slot():
    assert score_ap(make_ap("ZERO", [0, 0, 0]), APBalanceConfig()).status == "INSUFFICIENT_DATA"
    assert score_ap(make_ap("ONE", [7, None, None]), APBalanceConfig()).status == "INSUFFICIENT_DATA"


def test_slot_filters_limit_comparable_slots():
    config = APBalanceConfig(included_slots=(1, 2))
    score = score_ap(make_ap("NOC-AP-1", [50, 4, 5]), config)

    assert score.status == "OK"
    assert score.spread == 1


def test_sort_rows_places_imbalanced_first():
    aps = [make_ap("OK", [10, 12]), make_ap("BAD", [1, 50]), make_ap("WARN", [4, 14])]
    rows = sort_rows([(ap, score_ap(ap, APBalanceConfig())) for ap in aps])

    assert [ap.name for ap, _score in rows] == ["BAD", "WARN", "OK"]
