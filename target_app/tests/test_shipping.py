from brightshop import shipping


def test_zone_for():
    assert shipping.zone_for("DE") == "DE"
    assert shipping.zone_for("FR") == "EU"
    assert shipping.zone_for("US") == "WORLD"


def test_legacy_zone_lookup_default():
    assert shipping.legacy_zone_lookup("DE") == 490
    assert shipping.legacy_zone_lookup("JP") == 2990
