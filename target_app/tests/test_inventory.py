from brightshop import inventory


def test_available_and_status(store):
    assert inventory.available(store, "A-1") == 10
    assert inventory.stock_status(store, "C-1") == "out"
