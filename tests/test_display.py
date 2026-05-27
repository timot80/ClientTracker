from ap_radio_monitor.display import render_slot_distribution
from ap_radio_monitor.models import APLoad, RadioSlotLoad


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


def test_render_slot_distribution_uses_relative_bars_and_na_marker():
    ap = make_ap("NOC-AP-1", [1, 50, None])

    rendered = render_slot_distribution(ap, width=12)

    assert "S0 1 cl / 10% util" in rendered
    assert "S1 50 cl / 10% util" in rendered
    assert "S2 --" in rendered
    assert "████" in rendered
