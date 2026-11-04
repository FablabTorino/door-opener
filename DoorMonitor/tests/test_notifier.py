import requests

from notifier import (AlertBuffer, Outbox, clock, duration, format_down,
                      format_up, send_telegram)
from tracker import DOWN, UP, Transition


def down(name, at):
    return Transition(name, DOWN, at, at - 200)


def test_duration():
    assert duration(45) == "45 s"
    assert duration(180) == "3 min"
    assert duration(3600) == "1 h"
    assert duration(7500) == "2 h 5 min"


def test_format_down_with_last_seen():
    t = Transition("door", DOWN, 1180, 1000)
    assert format_down(t) == f"⚠️ door offline (last seen {clock(1000)}, 3 min ago)"


def test_format_down_never_seen():
    t = Transition("door", DOWN, 1180, None)
    assert format_down(t) == "⚠️ door not seen since monitor (re)connected"


def test_format_up():
    t = Transition("door", UP, 1720, 1720, 1000)
    assert format_up(t) == "✅ door back online (down for 12 min)"


def test_buffer_holds_downs_for_window():
    b = AlertBuffer(window=30, group_min=3)
    assert b.push([down("a", 1000)], 1000) == []
    assert b.push([], 1029) == []
    assert b.push([], 1030) == [format_down(down("a", 1000))]
    assert b.push([], 1100) == []


def test_two_downs_are_sent_separately():
    b = AlertBuffer(window=30, group_min=3)
    b.push([down("a", 1000)], 1000)
    b.push([down("b", 1010)], 1010)
    assert b.push([], 1030) == [format_down(down("a", 1000)), format_down(down("b", 1010))]


def test_three_downs_are_grouped():
    b = AlertBuffer(window=30, group_min=3)
    b.push([down("a", 1000), down("b", 1000)], 1000)
    b.push([down("c", 1020)], 1020)
    assert b.push([], 1030) == ["⚠️ 3 devices offline: a, b, c"]


def test_up_is_sent_immediately():
    b = AlertBuffer(window=30, group_min=3)
    up = Transition("a", UP, 2000, 2000, 1000)
    assert b.push([up], 2000) == [format_up(up)]


def test_up_cancels_pending_down():
    b = AlertBuffer(window=30, group_min=3)
    b.push([down("a", 1000)], 1000)
    assert b.push([Transition("a", UP, 1010, 1010, 1000)], 1010) == []
    assert b.push([], 1100) == []


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code
        self.text = "body"


def test_send_telegram_posts_to_bot_api():
    calls = []

    def post(url, data, timeout):
        calls.append((url, data))
        return FakeResponse(200)

    assert send_telegram("TOK", "42", "hi", post=post) is True
    assert calls == [("https://api.telegram.org/botTOK/sendMessage", {"chat_id": "42", "text": "hi"})]


def test_send_telegram_returns_false_on_http_error():
    assert send_telegram("TOK", "42", "hi", post=lambda url, data, timeout: FakeResponse(500)) is False


def test_send_telegram_returns_false_on_network_error():
    def post(url, data, timeout):
        raise requests.ConnectionError("down")

    assert send_telegram("TOK", "42", "hi", post=post) is False


def test_outbox_retries_once_then_drops():
    attempts = []

    def send(text):
        attempts.append(text)
        return False

    o = Outbox(send)
    o.add(["x"])
    o.deliver()
    o.deliver()
    o.deliver()
    assert attempts == ["x", "x"]


def test_outbox_sends_each_message_once_on_success():
    sent = []
    o = Outbox(lambda text: sent.append(text) or True)
    o.add(["a", "b"])
    o.deliver()
    o.deliver()
    assert sent == ["a", "b"]
