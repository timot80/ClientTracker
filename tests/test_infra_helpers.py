from client_tracker.infra import is_valid_mac, mac_to_cisco, normalize_mac


def test_normalize_mac_strips_common_delimiters():
    assert normalize_mac("AA:BB-CC.DD:EE-FF") == "aabbccddeeff"


def test_mac_to_cisco_formats_normalized_mac():
    assert mac_to_cisco("aa:bb:cc:dd:ee:ff") == "aabb.ccdd.eeff"


def test_is_valid_mac_accepts_common_formats():
    assert is_valid_mac("aa:bb:cc:dd:ee:ff")
    assert is_valid_mac("aabb.ccdd.eeff")
    assert is_valid_mac("aabbccddeeff")


def test_is_valid_mac_rejects_bad_values():
    assert not is_valid_mac("not-a-mac")
    assert not is_valid_mac("aa:bb:cc:dd:ee")
    assert not is_valid_mac("gg:bb:cc:dd:ee:ff")
