# WindDoc Sync

A hack of a PHP script to fetch data from a SOAP service and a Python script to send MQTT commands to esp-rfid.

Ideally would be better to do everything in Python, but I couldn't make SOAP play ball in Python :(

## Setup
Fill .env

Run `pipenv install` to install dependencies.

Then run `./sync.sh` which will fetch data from WindDoc, save them in a temporary `sync.json` file.

Then it will send MQTT commands to esp-rfid to clean the users' database and import the new list of users.