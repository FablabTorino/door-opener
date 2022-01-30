import json
import os
from os.path import join, dirname
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
import re

# convert the full card uid to a shorter format
# compatible with wiegand output of esp-rfid
def card_number_to_wiegand_format(card_number: str) -> str:
  # make all cards 14 bytes long
  hex_string_pad = card_number.zfill(14)
  # keep only the first 8 bytes
  hex_string_cut = hex_string_pad[:8]
  hex_data = bytearray.fromhex(hex_string_cut)
  hex_data.reverse()
  return hex_data.hex()

def load_users():
  sync_json_path = join(dirname(__file__), 'sync.json')
  file = open(sync_json_path)
  users = json.load(file)
  os.remove(sync_json_path)
  return users

def mqtt_delete_users():
  mqttClient.publish('esp-rfid/cmd', json.dumps({
     'cmd': 'deletusers',
     'doorip': ESPRFID_IP
  }))

def mqtt_add_users(users):
  for u in users:
    pincode = u['Pin']
    # if 3 or 4 digits are equal the pincode is not valid
    # we override it with an invalid one
    if re.match(r'[0-9]?([0-9])\1\1+', pincode, re.M) is not None:
      pincode = 'xxxx'
    # if pincode is not made of 4 digits
    # we override it with an invalid one
    if re.match(r'\d{4}', pincode) is None:
      pincode = 'xxxx'
    mqttClient.publish('esp-rfid/cmd', json.dumps({
        'cmd': 'adduser',
        'doorip': ESPRFID_IP,
        'uid': card_number_to_wiegand_format(u['cardNumber']),
        'user': u['fullName'],
        'acctype': u['accessLevel'],
        'pincode': pincode,
        'validuntil': u['validUntil']
    }))

MQTT_BROKER_IP = os.getenv('MQTT_BROKER_IP')
ESPRFID_IP = os.getenv('ESPRFID_IP')
mqttClient = mqtt.Client('TelegramBot')

try:
  mqttClient.connect(MQTT_BROKER_IP)
  mqttClient.loop_start()
except ConnectionRefusedError as e:
  exit(30)

users = load_users()
mqtt_delete_users()
mqtt_add_users(users)

mqttClient.loop_stop()
