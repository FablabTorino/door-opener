"""What the monitor watches, and how long each thing may stay silent."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Device:
    name: str       # esp-rfid hostname, or the <name> in doors/status/<name>
    timeout: float  # seconds of silence before the device is considered down


# esp-rfid doors publish {"type":"heartbeat",...} on esp-rfid/send every
# "syncrate" seconds (door web UI -> MQTT settings). Timeout = 3 x syncrate.
# Values measured on the broker on 2026-11-04 (heartbeats ~181 s apart).
DOOR_SYNCRATE = {
    "EGEO18-INT": 180,
    "EGEO18-EXT": 180,
    "FABLAB-MAKEIT": 180,
}

# Bots and the DoorBell Arduino publish "online" on doors/status/<name> every 60 s.
STATUS_TIMEOUT = 180

DEVICES = [Device(name, 3 * syncrate) for name, syncrate in DOOR_SYNCRATE.items()] + [
    Device("telegrambot", STATUS_TIMEOUT),
    Device("telegrambot-bell", STATUS_TIMEOUT),
    Device("doorbell-relay", STATUS_TIMEOUT),
]

OFFLINE_GRACE = 60    # after a Last Will "offline", wait this long for the device to come back
REBOOT_WINDOW = 300   # after "rebooting", allow this long before calling it down
BROKER_TIMEOUT = 120  # alert when the monitor can't reach the broker for this long
GROUP_WINDOW = 30     # down alerts are held this long so bursts can be grouped
GROUP_MIN = 3         # this many downs inside the window -> one grouped message
