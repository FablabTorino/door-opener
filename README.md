# Door-opener

## Warning! This repository is a work in progress!

Door-opener is a simple domotic system to manage the Fablab's entrance door.

The system consists of several parts: 
- [esp-rfid](https://github.com/esprfid/esp-rfid/tree/dev) to manage peripherals;
- [Eclipse Mosquitto]() as MQTT broker; 
- [Telegram Bot](https://core.telegram.org/api) as remote user friendly interface.

## esp-rfid

**esp-rfid** in an access control system using PN532 RFID reader and Espressif's ESP8266 Microcontroller. 
The version used is the `dev`, as it supports all the MQTT commands the system needs.
You can find more information int the [official repository](https://github.com/esprfid/esp-rfid/tree/dev).

In [cad](/cad) folder you can find the case for PN532 reader. 

## Eclipse Mosquitto
Eclipse Mosquitto is an open source (EPL/EDL licensed) message broker that implements the MQTT protocol. It's installed on a Raspberry Pi 4 inside the [official Docker container](https://hub.docker.com/_/eclipse-mosquitto/).

### Installation
Create directory `mosquitto` in user folder`/home/pi` and create a configuration file `mosquitto.conf` inside. 

    mkdir mosquitto  
    touch mosquitto/mosquitto.conf

Copy the following text into the previously created file. 

    persistence true
    persistence_location /mosquitto/data/
    log_dest file /mosquitto/log/mosquitto.log

Install with 

    docker run --restart always -p 1883:1883 -p 9001:9001 -v /home/pi/mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf -v mosquitto_data:/mosquitto/data -v mosquitto_log:/mosquitto/log --name mosquitto eclipse-mosquitto

You can find more information about `mosquitto.conf` in the [ufficial documentation](https://mosquitto.org/man/mosquitto-conf-5.html).

## Telegram_Bot
The telegram bot is used to manage remote accesses in a simple and fast way. It is inserted in a specific telegram group, the only chat from which it will respond.

You can find it in [TelegramBot](/TelegramBot) folder.

Commands:
- `/open` opens the door

Warning:
- Somebody pass the card on RFID reader
  - option 1: It's in the database -> Open door and send log message
  - option 2: It isn't in the database -> Ask what to do 

## WindDocSync

