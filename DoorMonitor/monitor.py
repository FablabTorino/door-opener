"""DoorMonitor: watches door-opener components over MQTT and alerts the Telegram group."""
import json
import logging
import os
import threading
import time
from os.path import abspath, dirname, join

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from classify import STATUS_PREFIX, classify
from devices import (BROKER_TIMEOUT, DEVICES, GROUP_MIN, GROUP_WINDOW,
                     OFFLINE_GRACE, REBOOT_WINDOW)
from notifier import (BROKER_DOWN_TEXT, BROKER_UP_TEXT, AlertBuffer, Outbox,
                      send_telegram)
from tracker import DOWN, UP, BrokerWatch, Tracker

STATE_TOPIC = "doors/monitor/state"
SNAPSHOT_EVERY = 30
TICK_SECONDS = 1


def env(name):
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"{name} not set in .env")
    return value


def main():
    logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
    load_dotenv(join(dirname(abspath(__file__)), ".env"))  # real env vars take precedence
    broker_ip = env("MQTT_BROKER_IP")
    broker_port = int(os.getenv("MQTT_BROKER_PORT") or 1883)
    send_topic = env("ESPRFID_MQTT_TOPIC") + "/send"
    token = env("TOKEN_TBOT")
    chat_id = env("CHAT_ID_TBOT")

    now = time.time()
    lock = threading.Lock()  # guards tracker, broker, incoming
    tracker = Tracker(DEVICES, now, OFFLINE_GRACE, REBOOT_WINDOW)
    broker = BrokerWatch(now, BROKER_TIMEOUT)
    alerts = AlertBuffer(GROUP_WINDOW, GROUP_MIN)
    outbox = Outbox(lambda text: send_telegram(token, chat_id, text))
    incoming = []  # UP transitions from on_message, consumed by the tick loop

    def on_connect(client, userdata, flags, rc):
        if rc != 0:
            logging.error("MQTT connect failed, rc=%s", rc)
            return
        logging.info("Connected to broker %s:%s", broker_ip, broker_port)
        client.subscribe(send_topic)
        client.subscribe(STATUS_PREFIX + "+")
        with lock:
            t = time.time()
            if broker.on_connect(t) == UP:
                outbox.add([BROKER_UP_TEXT])
            tracker.reset(t)
            incoming.clear()

    def on_disconnect(client, userdata, rc):
        logging.warning("Disconnected from broker, rc=%s", rc)
        with lock:
            broker.on_disconnect(time.time())

    def on_message(client, userdata, msg):
        if msg.retain:
            return  # old news; only live messages prove a device is alive
        hit = classify(msg.topic, msg.payload, send_topic)
        if hit is None:
            return
        event, name = hit
        with lock:
            t = time.time()
            if event == "seen":
                incoming.extend(tracker.seen(name, t))
            elif event == "offline":
                tracker.offline(name, t)
            else:
                tracker.rebooting(name, t)

    client = mqtt.Client("DoorMonitor")
    client.will_set(STATE_TOPIC, json.dumps({"monitor": "offline"}), qos=1, retain=True)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.connect_async(broker_ip, broker_port)
    client.loop_start()

    last_snapshot = 0.0
    while True:
        time.sleep(TICK_SECONDS)
        snapshot = None
        with lock:
            t = time.time()
            if broker.tick(t) == DOWN:
                outbox.add([BROKER_DOWN_TEXT])
            if broker.connected:
                transitions = incoming[:] + tracker.tick(t)
                incoming.clear()
                for tr in transitions:
                    logging.info("%s -> %s", tr.name, tr.new_state)
                outbox.add(alerts.push(transitions, t))
                if transitions or t - last_snapshot >= SNAPSHOT_EVERY:
                    snapshot = json.dumps(tracker.snapshot(t))
                    last_snapshot = t
        if snapshot is not None:
            client.publish(STATE_TOPIC, snapshot, qos=1, retain=True)
        outbox.deliver()


if __name__ == "__main__":
    main()
