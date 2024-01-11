import json
import os
from os.path import join, dirname
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
import re
import time
import json

ESPRFID_MQTT_TOPIC = os.getenv('ESPRFID_MQTT_TOPIC')
if ESPRFID_MQTT_TOPIC is None:
    logging.error('ESPRFID_MQTT_TOPIC not set in .env')
MQTT_BROKER_IP = os.getenv('MQTT_BROKER_IP')
if MQTT_BROKER_IP is None:
    logging.error('MQTT_BROKER_IP not set in .env')
ESPRFID_IP = os.getenv('DOOR2_IP')
if ESPRFID_IP is None:
    logging.error('DOOR2_IP not set in .env')


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
#  os.remove(sync_json_path)
  return users

def mqtt_delete_users():
  mqttClient.publish('esp-rfid/cmd', json.dumps({
     'cmd': 'deletusers',
     'doorip': ESPRFID_IP
  }))

def on_mqtt_message(client, userdata, message):
  try:
    json_message = json.loads(message.payload)
  except BaseException as e:
    logging.error(e)
    return

  type = json_message.get('type')
  if type == 'adduser' and len(users) > 0:
    user = users.pop(0)
    mqtt_send_user(user)


def mqtt_send_user(user):
  print('sending user ', user['fullName'])
  pincode = user['Pin']
  # if 3 or 4 digits are equal the pincode is not valid
  # we override it with an invalid one
  if re.match(r'[0-9]?([0-9])\1\1+', pincode, re.M) is not None:
    pincode = 'xxxx'
  # if pincode is not made of 4 digits
  # we override it with an invalid one
  if re.match(r'\d{4}', pincode) is None:
    pincode = 'xxxx'
  time.sleep(0.1)
  mqttClient.publish('esp-rfid/cmd', json.dumps({
      'cmd': 'adduser',
      'doorip': ESPRFID_IP,
      'uid': card_number_to_wiegand_format(user['cardNumber']),
      'user': user['fullName'],
      'acctype': user['accessLevel'],
      'pincode': pincode,
      'validuntil': user['validUntil']
  }))

def mqtt_add_users():
  # we send the first one, then the callback should send more
  # only when esp-rfid has finished
  user = users.pop(0)
  mqtt_send_user(user)

  while len(users) > 0:
    user = users.pop(0)
    mqtt_send_user(user)
    # every second we check if we are done 
    time.sleep(1)

mqttClient = mqtt.Client('WindDocSync')

try:
  mqttClient.connect(MQTT_BROKER_IP)
  mqttClient.loop_start()
  mqttClient.subscribe(ESPRFID_MQTT_TOPIC + '/send')
  mqttClient.on_message = on_mqtt_message
except ConnectionRefusedError as e:
  exit(30)

users = load_users()
mqtt_delete_users()
mqtt_add_users()

mqttClient.loop_stop()