#!/bin/bash
# Local end-to-end check: throwaway Mosquitto on :18830, fake Telegram token.
# Needs `mosquitto`, `mosquitto_pub`, `mosquitto_sub` and pipenv deps installed.
set -euo pipefail
cd "$(dirname "$0")"
PORT=18830

mosquitto -p "$PORT" >/dev/null 2>&1 &
BROKER=$!
trap 'kill $BROKER 2>/dev/null || true' EXIT
sleep 1

PY=$(pipenv --py)   # run the venv python directly so $! is the monitor's own PID
MQTT_BROKER_IP=127.0.0.1 MQTT_BROKER_PORT=$PORT ESPRFID_MQTT_TOPIC=esp-rfid \
TOKEN_TBOT=0:fake CHAT_ID_TBOT=0 \
  "$PY" monitor.py >smoke.log 2>&1 &
MON=$!
trap 'kill $BROKER $MON 2>/dev/null || true' EXIT

for _ in $(seq 15); do grep -q "Connected to broker" smoke.log && break; sleep 1; done
grep -q "Connected to broker" smoke.log || { echo "monitor never connected"; cat smoke.log; exit 1; }

mosquitto_pub -p "$PORT" -t esp-rfid/send -m '{"type":"heartbeat","hostname":"FABLAB-MAKEIT"}'
mosquitto_pub -p "$PORT" -t doors/status/telegrambot -m online

echo "waiting 31 s for the periodic snapshot..."
sleep 31
STATE=$(mosquitto_sub -p "$PORT" -t doors/monitor/state -C 1 -W 5)
echo "$STATE" | python3 -m json.tool
echo "$STATE" | python3 -c '
import json, sys
d = json.load(sys.stdin)["devices"]
assert d["FABLAB-MAKEIT"]["state"] == "up", d
assert d["telegrambot"]["state"] == "up", d
assert d["EGEO18-INT"]["state"] == "unknown", d
'

kill -9 "$MON"   # hard kill so the broker publishes the Last Will
sleep 2
LWT=$(mosquitto_sub -p "$PORT" -t doors/monitor/state -C 1 -W 5)
echo "after kill: $LWT"
[ "$LWT" = '{"monitor": "offline"}' ]

rm -f smoke.log
echo "SMOKE OK"
