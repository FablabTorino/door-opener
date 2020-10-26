# Door opener
Fablab door opener made with a Wemos, RFID reader and a Telegram bot.

v0.0.1-alpha

## Hardware
- [ESP32 con OLED](https://www.amazon.it/ILS-Arduino-Bluetooth-ESP-32S-ESP8266/dp/B0769HNFTP/)
- [NFC reader PN532](https://www.amazon.it/ICQUANZX-Communication-Arduino-Raspberry-Android/dp/B07VT431QZ/)
- [relè](https://www.amazon.it/ARCELI-KY-019-Channel-Module-arduino/dp/B07BVXT1ZK/)
- [button](https://www.amazon.it/Coolais-interruttore-momentaneo-impermeabile-confezione/dp/B07L4LSXNR)
- LED red
- LED green

## Software elements
#### ESP32
Pinout 

    TODO
#### Door
Functions:

     open()
#### NFC_Reader
To read the TOKEN stored on Fablab card.

#### LED 
Functions:

    on(LED_GREEN | LED_RED)
    off(LED_GREEN | LED_RED)

#### Telegram_Bot
Telegram Group for Admins
Commands:

`/open`  apre la porta al prossimo che suona il campanello    
`/autoopen` apre la porta a tutti quelli che suonano il campanello per tot minuti
`/update` aggiorna la cache    
`/cancel` annulla quello che stava facendo


Warning:
- Somebody pass the card
    - option 1: It's in the database -> Open door and send log message
    - option 2: It isn't in the database -> Ask what to do 

#### Database
IoT_Cloud. Database stored online on https://io.adafruit.com/

#### Cache
Database backup on SPIFFS.

#### OLED
Another output.

#### User
- id: unique identification number   
- name: `name surname` string

## Flowchart

![Flowchart](docs/flowchart.svg)