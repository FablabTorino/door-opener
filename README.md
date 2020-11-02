# Door-opener
The Fablab door opener made with a ESP32, RFID reader and a Telegram bot.

Door-opener is a simple domotic system to manage the Fablab's entrance door.

The NFC reader identifies the associative cards which have an RFID tag embedded. If the card id is present in the database, the door is opened.

The NFC reader communicates with an online server that manages a users' database and a Telegram bot.

The Telegram bot serves three purposes: remote access, database management and access log.

The NFC reader and the server communicate using MQTT with [Adafruit IO](https://io.adafruit.com/).

## Hardware - v0.0.1-alpha
- [ESP32](https://www.amazon.it/ILS-Arduino-Bluetooth-ESP-32S-ESP8266/dp/B0769HNFTP/)
- [NFC reader PN532](https://www.amazon.it/ICQUANZX-Communication-Arduino-Raspberry-Android/dp/B07VT431QZ/)
- [relay](https://www.amazon.it/ARCELI-KY-019-Channel-Module-arduino/dp/B07BVXT1ZK/)
- [button](https://www.amazon.it/Coolais-interruttore-momentaneo-impermeabile-confezione/dp/B07L4LSXNR)
- LED red
- LED green
- [Buzzer](https://www.amazon.it/ARCELI-elettronico-Magnetico-Continuo-Confezione/dp/B07RDHNT1P/)

#### ESP32
Pinout 

![ESP32-OLED](docs/src/ESP32-pinout.jpeg)

## Software - v0.0.1-alpha

### ESP32
The ESP 32 needs to:
- extract the ID from the RFID card
- check if the ID is part of a list of locally saved IDs
- open the door
- connect to the WiFi

moreover, if it's online, it needs to:
- communicate via MQTT the card ID to the server
- listen to MQTT messages from the server to open the door

#### Door
Functions:
- open()

#### Buzzer
Functions:
- on(BUZZER)

#### NFC Reader
To read the TOKEN stored on Fablab card.

#### LED 
Functions:
- on(LED_GREEN | LED_RED)
- off(LED_GREEN | LED_RED)

#### MQTT
Publish `card_id`.

Subscribe to `open_door`.

### Server
Every operation that needs an Internet connection will be done server sie:
- interact with the Telegram bot
- interact with the users DB
- send/receiving MQTT messages with ESP32

#### Telegram_Bot
Telegram Group for Admins
Commands:
- `/open` opens the door
- `/cancel` cancel what the user was doing

Warning:
- Somebody pass the card
  - option 1: It's in the database -> Open door and send log message
  - option 2: It isn't in the database -> Ask what to do 

#### MQTT
Via [Adafruit IO](https://io.adafruit.com/) to have a simple, secure and reliable connection between the ESP32 and the server.

Subscribe to `card_id`.

Publish `open_door`.

#### Database
SQlite.

Simple interface for data entry/review.

#### User
- id: unique identification number, the card's ID _string_
- name: `name surname` _string_

## Flowchart

![Flowchart](docs/flowchart.svg)

## Future ideas

A users' database backup is hold on the SPIFFS memory of the ESP32, to guarantee the access to the Fablab when the Internet connection is absent.

### ESP32

#### SPIFFS
Save the users' DB on memory.

### Server

#### Telegram bot

- `/open` opens the door to the next person ringing the doorbell
- `/autoopen` opens the door for every person ringing the bell in the next X minutes
- `/update` forces a cache refresh of the users' DB on the ESP32
