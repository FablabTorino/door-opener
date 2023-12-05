#!/bin/bash
killall mosquitto_sub
mosquitto_sub -h 127.0.0.1 -t esp-rfid/cmd >> ./mosquitto_esp-rfid_cmd_sub &
mosquitto_sub -h 127.0.0.1 -t esp-rfid/send >> ./mosquitto_esp-rfid_send_sub &

pushd ${BASH_SOURCE%/*}

pipenv run python main.py &
popd



