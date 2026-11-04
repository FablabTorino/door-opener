from devices import Device
from tracker import DOWN, UNKNOWN, UP, BrokerWatch, Tracker, Transition


def make(now=1000.0):
    return Tracker([Device("door", 180)], now, offline_grace=60, reboot_window=300)


def test_unknown_to_up_on_first_message_is_silent():
    t = make()
    assert t.seen("door", 1010) == []
    assert t.snapshot(1010)["devices"]["door"] == {"state": UP, "last_seen": 1010}


def test_unknown_to_down_after_timeout():
    t = make()
    assert t.tick(1179) == []
    assert t.tick(1180) == [Transition("door", DOWN, 1180, None)]


def test_down_is_reported_once():
    t = make()
    t.tick(1180)
    assert t.tick(2000) == []


def test_up_to_down_on_silence():
    t = make()
    t.seen("door", 1100)
    assert t.tick(1279) == []
    assert t.tick(1280) == [Transition("door", DOWN, 1280, 1100)]


def test_down_to_up_reports_down_since():
    t = make()
    t.seen("door", 1100)
    t.tick(1280)
    assert t.seen("door", 1400) == [Transition("door", UP, 1400, 1400, 1280)]


def test_offline_then_message_within_grace_is_silent():
    t = make()
    t.seen("door", 1100)
    t.offline("door", 1110)
    t.seen("door", 1150)
    assert t.tick(1171) == []


def test_offline_without_recovery_goes_down_after_grace():
    t = make()
    t.seen("door", 1100)
    t.offline("door", 1110)
    assert t.tick(1169) == []
    assert t.tick(1170) == [Transition("door", DOWN, 1170, 1100)]


def test_rebooting_suppresses_alert_for_reboot_window():
    t = make()
    t.seen("door", 1100)
    t.rebooting("door", 1110)
    t.offline("door", 1120)  # Last Will fires when the board resets
    assert t.tick(1409) == []
    assert t.tick(1410) == [Transition("door", DOWN, 1410, 1100)]


def test_rebooting_then_back_online_is_silent():
    t = make()
    t.seen("door", 1100)
    t.rebooting("door", 1110)
    t.offline("door", 1120)
    assert t.seen("door", 1200) == []
    assert t.tick(1300) == []


def test_unknown_device_names_are_ignored():
    t = make()
    assert t.seen("other", 1100) == []
    t.offline("other", 1100)
    t.rebooting("other", 1100)
    assert "other" not in t.snapshot(1100)["devices"]


def test_reset_returns_everything_to_unknown():
    t = make()
    t.seen("door", 1100)
    t.reset(1200)
    assert t.snapshot(1200)["devices"]["door"] == {"state": UNKNOWN, "last_seen": None}
    assert t.tick(1379) == []
    assert t.tick(1380) == [Transition("door", DOWN, 1380, None)]


def test_broker_alert_after_timeout_when_never_connected():
    b = BrokerWatch(1000, timeout=120)
    assert b.tick(1119) is None
    assert b.tick(1120) == DOWN
    assert b.tick(1200) is None


def test_broker_disconnect_alert_then_recovery():
    b = BrokerWatch(1000, timeout=120)
    assert b.on_connect(1001) is None
    b.on_disconnect(1100)
    assert b.tick(1219) is None
    assert b.tick(1220) == DOWN
    assert b.on_connect(1300) == UP


def test_short_broker_blip_is_silent():
    b = BrokerWatch(1000, timeout=120)
    b.on_connect(1001)
    b.on_disconnect(1100)
    assert b.on_connect(1150) is None
    assert b.tick(1300) is None
