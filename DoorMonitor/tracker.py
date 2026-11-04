"""Pure liveness state machines. No I/O: every call takes `now` (any monotonic seconds)."""
from dataclasses import dataclass
from typing import Optional

UNKNOWN, UP, DOWN = "unknown", "up", "down"


@dataclass(frozen=True)
class Transition:
    name: str
    new_state: str                      # UP or DOWN
    at: float                           # when the transition happened
    last_seen: Optional[float]          # last sign of life (None = never seen)
    down_since: Optional[float] = None  # UP transitions only: when it went DOWN


class Tracker:
    """Per-device unknown/up/down state driven by signs of life and deadlines."""

    def __init__(self, devices, now, offline_grace=60, reboot_window=300):
        self._timeouts = {d.name: d.timeout for d in devices}
        self._offline_grace = offline_grace
        self._reboot_window = reboot_window
        self._state = {n: UNKNOWN for n in self._timeouts}
        self._last_seen, self._down_since, self._rebooting, self._deadline = {}, {}, {}, {}
        self.reset(now)

    def reset(self, now):
        """Forget everything except DOWN devices (already announced; they stay DOWN)."""
        for n, timeout in self._timeouts.items():
            if self._state[n] == DOWN:
                continue
            self._state[n] = UNKNOWN
            self._last_seen[n] = None
            self._down_since[n] = None
            self._rebooting[n] = False
            self._deadline[n] = now + timeout

    def seen(self, name, now):
        """A sign of life. Returns [Transition] if the device was DOWN."""
        if name not in self._timeouts:
            return []
        previous = self._state[name]
        self._state[name] = UP
        self._last_seen[name] = now
        self._rebooting[name] = False
        self._deadline[name] = now + self._timeouts[name]
        if previous == DOWN:
            down_since, self._down_since[name] = self._down_since[name], None
            return [Transition(name, UP, now, now, down_since)]
        return []

    def offline(self, name, now):
        """Last Will received: down unless it comes back within the grace period."""
        if name in self._timeouts and not self._rebooting[name]:
            self._deadline[name] = min(self._deadline[name], now + self._offline_grace)

    def rebooting(self, name, now):
        """Planned reboot announced: allow the reboot window before calling it down."""
        if name in self._timeouts:
            self._rebooting[name] = True
            self._deadline[name] = now + self._reboot_window

    def tick(self, now):
        """Returns DOWN transitions for devices whose deadline has passed."""
        out = []
        for name, deadline in self._deadline.items():
            if self._state[name] != DOWN and now >= deadline:
                self._state[name] = DOWN
                self._down_since[name] = now
                out.append(Transition(name, DOWN, now, self._last_seen[name]))
        return out

    def snapshot(self, now, wall_offset=0.0):
        """wall_offset converts the monotonic clock to wall time (wall = now + offset)."""
        return {
            "updated": int(now + wall_offset),
            "devices": {
                n: {
                    "state": self._state[n],
                    "last_seen": None if self._last_seen[n] is None else int(self._last_seen[n] + wall_offset),
                }
                for n in self._timeouts
            },
        }


class BrokerWatch:
    """The monitor's own MQTT connection. Starts disconnected."""

    def __init__(self, now, timeout=120):
        self._timeout = timeout
        self.connected = False
        self._since = now
        self._alerted = False

    def on_connect(self, now):
        """Returns UP if a broker-down alert had been sent, else None."""
        self.connected = True
        was_alerted, self._alerted = self._alerted, False
        return UP if was_alerted else None

    def on_disconnect(self, now):
        if self.connected:
            self.connected = False
            self._since = now

    def tick(self, now):
        """Returns DOWN once, when disconnected for at least `timeout`."""
        if not self.connected and not self._alerted and now - self._since >= self._timeout:
            self._alerted = True
            return DOWN
        return None
