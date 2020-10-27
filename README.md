# Door opener
Fablab door opener made with a ESP32, RFID reader and a Telegram bot.

Door-opener è un semplice sistema domotico per la porta d'ingresso del Fablab.
Il lettore NFC identifica le tessere associative dotate di tag RFID in caso l'utente sia presente nel database.
Il bot di Telegram ha tre funzioni: accesso remoto, gestione del database e log degli accessi.
Il database di riferimento è momentaneamente su [IO di Adafruit](https://io.adafruit.com/), in futuro sarà su un server interno al Fablab. Un backup viene fatto sulla memoria SPIFFS della ESP32.


v0.0.1-alpha

## Hardware
- [ESP32 con OLED](https://www.amazon.it/ILS-Arduino-Bluetooth-ESP-32S-ESP8266/dp/B0769HNFTP/)
- [NFC reader PN532](https://www.amazon.it/ICQUANZX-Communication-Arduino-Raspberry-Android/dp/B07VT431QZ/)
- [relè](https://www.amazon.it/ARCELI-KY-019-Channel-Module-arduino/dp/B07BVXT1ZK/)
- [button](https://www.amazon.it/Coolais-interruttore-momentaneo-impermeabile-confezione/dp/B07L4LSXNR)
- LED red
- LED green
- [Buzzer](https://www.amazon.it/ARCELI-elettronico-Magnetico-Continuo-Confezione/dp/B07RDHNT1P/)

## Software elements
#### ESP32
Pinout 

    TODO
#### Door
Functions:

     open()
#### Buzzer
Functions:

    on(BUZZER)
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