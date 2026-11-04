"""Turns state transitions into Telegram messages and sends them."""
import logging
import threading
import time

import requests

from tracker import DOWN

BROKER_DOWN_TEXT = "⚠️ MQTT broker unreachable"
BROKER_UP_TEXT = "✅ MQTT broker back"


def duration(seconds):
    s = int(seconds)
    if s < 60:
        return f"{s} s"
    minutes = s // 60
    if minutes < 60:
        return f"{minutes} min"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min" if minutes else f"{hours} h"


def clock(ts):
    return time.strftime("%H:%M", time.localtime(ts))


def format_down(t):
    if t.last_seen is None:
        return f"⚠️ {t.name} not seen since monitor (re)connected"
    return f"⚠️ {t.name} offline (last seen {clock(t.last_seen)}, {duration(t.at - t.last_seen)} ago)"


def format_up(t):
    return f"✅ {t.name} back online (down for {duration(t.at - t.down_since)})"


def format_group(downs):
    return f"⚠️ {len(downs)} devices offline: " + ", ".join(t.name for t in downs)


class AlertBuffer:
    """Holds DOWN transitions for `window` seconds so bursts become one message."""

    def __init__(self, window=30, group_min=3):
        self._window = window
        self._group_min = group_min
        self._pending = []

    def push(self, transitions, now):
        """Feed new transitions (may be empty); returns messages ready to send."""
        out = []
        for t in transitions:
            if t.new_state == DOWN:
                self._pending.append(t)
                continue
            blip = next((p for p in self._pending if p.name == t.name), None)
            if blip is not None:
                self._pending.remove(blip)  # down and back up before we said anything
            else:
                out.append(format_up(t))
        return out + self._due(now)

    def _due(self, now):
        if not self._pending or now - self._pending[0].at < self._window:
            return []
        downs, self._pending = self._pending, []
        if len(downs) >= self._group_min:
            return [format_group(downs)]
        return [format_down(t) for t in downs]


def send_telegram(token, chat_id, text, post=requests.post):
    """Send-only Telegram call. Returns True on success, never raises."""
    try:
        r = post(f"https://api.telegram.org/bot{token}/sendMessage",
                 data={"chat_id": chat_id, "text": text}, timeout=10)
        if r.status_code == 200:
            return True
        logging.error("Telegram sendMessage failed: HTTP %s %s", r.status_code, r.text[:200])
    except requests.RequestException as e:
        logging.error("Telegram sendMessage failed: %s", e)
    return False


class Outbox:
    """Thread-safe queue of messages; each gets at most 2 attempts (now + next deliver)."""

    def __init__(self, send):
        self._send = send
        self._lock = threading.Lock()
        self._queue = []  # (text, attempts_so_far)

    def add(self, texts):
        with self._lock:
            self._queue.extend((text, 0) for text in texts)

    def deliver(self):
        with self._lock:
            batch, self._queue = self._queue, []
        retry = []
        for text, attempts in batch:
            if self._send(text):
                continue
            if attempts == 0:
                retry.append((text, 1))
            else:
                logging.error("Dropping alert after 2 failed attempts: %s", text)
        with self._lock:
            self._queue[:0] = retry
