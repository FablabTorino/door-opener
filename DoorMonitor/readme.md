# DoorMonitor

Watches every part of the door-opener system over MQTT. Posts to the Telegram group when something goes offline, and again when it comes back.

| Watched | How |
|---|---|
| Doors `EGEO18-INT`, `EGEO18-EXT`, `FABLAB-MAKEIT` | esp-rfid `heartbeat` messages on `esp-rfid/send` |
| `telegrambot`, `telegrambot-bell`, `doorbell-relay` | `online` heartbeats on `doors/status/<name>` every 60 s, plus MQTT Last Will `offline` |
| MQTT broker | the monitor's own connection (alert sent directly over the Telegram HTTP API) |

Alerts are sent once per change (offline / back online). If 3 or more devices drop within 30 s, they're grouped into one message. The DoorBell's daily reboot is announced first, so it doesn't trigger an alert.

The monitor also keeps a retained status snapshot on `doors/monitor/state`. See [DEBUGGING.md](DEBUGGING.md).

## Setup

Runs on the Pi's stock Python 3.9 (Raspbian 11). `Pipfile.lock` was generated there, so `pipenv install` works as-is.

1. `cp .env.sample .env` and fill it in. Use the same `TOKEN_TBOT` and `CHAT_ID_TBOT` as `TelegramBot/.env`.
2. `pipenv install`
3. **Set each door's heartbeat interval.** On each door's web UI, open the MQTT settings and note the **syncrate** (seconds). If it's 0 or very large, set it to 60 and save. Put the values into `DOOR_SYNCRATE` in `devices.py`. Also confirm each door's `hostname` exactly matches a key in `DOOR_SYNCRATE`, e.g. `mosquitto_sub -h 127.0.0.1 -t esp-rfid/send | grep heartbeat`. A mismatch means a door that is never tracked, plus a permanent "not seen" alert.
4. Install the service. Adjust `User`, `WorkingDirectory` and the pipenv path (`which pipenv`) in `doormonitor.service` first if they differ:

   ```bash
   sudo cp doormonitor.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now doormonitor
   journalctl -u doormonitor -f
   ```

5. Deploy the updated `TelegramBot`, `TelegramBotBell` and the DoorBell Arduino sketch. They now send heartbeats. Run the bots and the esp-rfid traffic log as systemd units, so they come back after a reboot or a crash. First stop the copies started by hand (`telegrambot.sh` and `nohup … main.py`), otherwise two instances of each bot run at once:

   ```
   sudo cp ../TelegramBot/telegrambot.service ../TelegramBot/esp-rfid-log.service ../TelegramBotBell/telegrambot-bell.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now telegrambot telegrambot-bell esp-rfid-log
   ```

   The DoorBell also publishes a retained diagnostics message (reset cause, uptime, drops since boot, last drop reason, RSSI, NINA firmware): `mosquitto_sub -h 127.0.0.1 -v -t doors/diag/doorbell-relay`.

The service connects with MQTT client id `DoorMonitor`. Stop it (`sudo systemctl stop doormonitor`) before running `monitor.py` by hand: two instances would keep kicking each other off the broker.

## Development

```bash
pipenv install --dev
pipenv run pytest -v     # unit tests
./smoke_test.sh          # end-to-end against a throwaway local Mosquitto on :18830
```

## On-site checklist

Run these after installing:

1. `sudo systemctl stop telegrambot`. Expect `⚠️ telegrambot offline …` after about 1.5 min (Last Will 60 s + 30 s grouping), and at most about 3.5 min. `sudo systemctl start telegrambot`: `✅ telegrambot back online …`.
2. Watch `mosquitto_sub -h 127.0.0.1 -v -t doors/status/doorbell-relay` around the DoorBell's daily reboot (it reboots after 24 h uptime). You should see `rebooting`, then `online`, and **no** alert. A quick press of the reset button must not alert either, because the device is back well within the 180 s timeout.
3. Unplug a door. After 3 × syncrate + 30 s: `⚠️ <door> offline …`. Plug it back in: recovery message.
4. `sudo systemctl stop mosquitto`. After about 2 min: `⚠️ MQTT broker unreachable`. `sudo systemctl start mosquitto`: `✅ MQTT broker back`, and no device alerts in the following ~4 min (bots reconnect with up to 120 s backoff).
5. `sudo systemctl stop doormonitor`, then `mosquitto_sub -h 127.0.0.1 -t doors/monitor/state -C 1` shows `{"monitor": "offline"}`. Start it again afterwards.
