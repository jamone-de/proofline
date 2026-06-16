from brightshop import invoicing


def test_reminder_levels():
    assert invoicing.reminder_level(3) == 0
    assert invoicing.reminder_level(7) == 1
    assert invoicing.reminder_level(40) == 3


def test_reminder_fee_for_consumers():
    assert invoicing.reminder_fee(1, False) == 0
    assert invoicing.reminder_fee(3, False) == 1500
