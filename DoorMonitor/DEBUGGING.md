# Debugging the door-opener on site

Run these on the Pi. `mosquitto_sub` and `mosquitto_pub` are already installed there. The examples pipe into `jq`. If `jq` is missing, install it with `sudo apt install jq` (or drop `| jq`).

## 1. Is everything alive?

```bash
mosquitto_sub -h 127.0.0.1 -t doors/monitor/state -C 1 | jq
```

- `state` per device: `up`, `down` or `unknown` (not seen since the monitor started).
- `updated` is a Unix timestamp (`date -d @<value>`). If it's more than about a minute old, **the monitor itself is stuck**. `{"monitor": "offline"}` means it's not running: `systemctl status doormonitor`.

## 2. Watch the traffic

```bash
mosquitto_sub -h 127.0.0.1 -v -t '#'                          # everything
mosquitto_sub -h 127.0.0.1 -t esp-rfid/send | grep FABLAB-MAKEIT   # one door
mosquitto_sub -h 127.0.0.1 -t esp-rfid/send | jq                   # pretty JSON
mosquitto_sub -h 127.0.0.1 -v -t 'doors/status/+'                  # bot/Arduino heartbeats
```

Restarting TelegramBot via `telegrambot.sh` runs `killall mosquitto_sub`, which ends any watch you have open.

Every door should show a `"type":"heartbeat"` line every syncrate seconds.

## 3. Network or software?

```bash
ping <door IP>                 # IPs are in TelegramBot/.env (DOORx_IP)
systemctl status mosquitto     # broker running? (native service, not Docker)
systemctl status doormonitor
```

Door names for `DOORx_IP`: DOOR1=EGEO18-INT, DOOR2=EGEO18-EXT, DOOR4=FABLAB-MAKEIT (DOOR3 is unused).

A door that answers ping but sends no heartbeat usually has a problem with its MQTT settings, or its NTP time isn't set yet. Open its web UI.

## 4. Logs

| What | Where |
|---|---|
| TelegramBot | `TelegramBot/doorbot.log` |
| TelegramBotBell | `TelegramBotBell/doorbot.log` |
| Raw door traffic (written by `telegrambot.sh`) | `TelegramBot/mosquitto_esp-rfid_cmd_sub`, `TelegramBot/mosquitto_esp-rfid_send_sub` |
| DoorMonitor | `journalctl -u doormonitor -f` |
| Broker | `tail -n 100 /var/log/mosquitto/mosquitto.log` |
| DoorBell Arduino | USB serial monitor at 9600 baud |

## 5. Test actions

**⚠️ REAL SIDE EFFECT. Ring the bell.** The relay fires and the bell bot posts in the group:

```bash
mosquitto_pub -h 127.0.0.1 -t esp-rfid/send \
  -m '{"type":"INFO","src":"doorbell","cmd":"event","desc":"Doorbell ringing","hostname":"TEST"}'
```

**⚠️ REAL SIDE EFFECT. Open a door.** Use the door's IP from `TelegramBot/.env`:

```bash
mosquitto_pub -h 127.0.0.1 -t esp-rfid/cmd -m '{"cmd":"opendoor","doorip":"<DOOR IP>"}'
```

**Do NOT simulate an unknown card.** TelegramBot looks unknown cards up in WindDoc, and if it finds a match it pushes `adduser` to **every door**.

## 6. Symptom → what to check

- **Card doesn't open the door.** Watch `esp-rfid/send` while swiping. No message means a reader or door problem (section 3). An `access` message with `"isKnown":"false"` (esp-rfid sends it as a string) means the card isn't on the door; check WindDoc and `/sync`. `Disabled` or an expired membership is reported in the group.
- **Bell doesn't ring.** Watch `esp-rfid/send` while pressing the bell. No `Doorbell ringing` means a problem with the door/esp-rfid doorbell input. If the message appears but nothing rings, check `doorbell-relay` in the status snapshot and the Arduino serial log.
- **Bot is silent in the group.** Check `telegrambot` / `telegrambot-bell` in the status snapshot, then the bot's `doorbot.log`. The `up` status only proves the bot process and its MQTT link are alive, not Telegram polling, so check `doorbot.log` even when it shows `up`.
- **A door shows `down`.** Ping it (section 3), then look for its heartbeat (section 2).
