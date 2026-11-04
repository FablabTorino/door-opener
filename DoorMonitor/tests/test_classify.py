import json

from classify import classify

SEND = "esp-rfid/send"


def test_status_online():
    assert classify("doors/status/telegrambot", b"online", SEND) == ("seen", "telegrambot")


def test_status_offline():
    assert classify("doors/status/doorbell-relay", b"offline", SEND) == ("offline", "doorbell-relay")


def test_status_rebooting():
    assert classify("doors/status/doorbell-relay", b"rebooting", SEND) == ("rebooting", "doorbell-relay")


def test_status_unknown_payload_ignored():
    assert classify("doors/status/telegrambot", b"hello", SEND) is None


def test_status_empty_name_ignored():
    assert classify("doors/status/", b"online", SEND) is None


def test_esprfid_heartbeat():
    payload = json.dumps({"type": "heartbeat", "time": 1, "uptime": 5,
                          "ip": "10.0.0.5", "hostname": "FABLAB-MAKEIT"}).encode()
    assert classify(SEND, payload, SEND) == ("seen", "FABLAB-MAKEIT")


def test_esprfid_any_event_with_hostname_counts():
    payload = json.dumps({"type": "access", "hostname": "EGEO18-INT"}).encode()
    assert classify(SEND, payload, SEND) == ("seen", "EGEO18-INT")


def test_esprfid_without_hostname_ignored():
    assert classify(SEND, b'{"type": "heartbeat"}', SEND) is None


def test_esprfid_bad_or_non_object_json_ignored():
    assert classify(SEND, b"{nope", SEND) is None
    assert classify(SEND, b"[1, 2]", SEND) is None


def test_other_topics_ignored():
    assert classify("esp-rfid/cmd", b'{"hostname": "EGEO18-INT"}', SEND) is None


def test_esprfid_non_string_hostname_ignored():
    for bad in ('[1]', '{"a": 1}', '5', 'true'):
        assert classify(SEND, ('{"hostname": %s}' % bad).encode(), SEND) is None


def test_esprfid_deeply_nested_json_ignored():
    assert classify(SEND, b"[" * 100000, SEND) is None
