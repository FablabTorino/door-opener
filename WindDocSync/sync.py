import json
import os
from os.path import join, dirname
from dotenv import load_dotenv
import paho.mqtt.client as mqtt

MQTT_BROKER_IP = os.getenv('MQTT_BROKER_IP')
ESPRFID_IP = os.getenv('ESPRFID_IP')

mqttClient = mqtt.Client('TelegramBot')
try:
  mqttClient.connect(MQTT_BROKER_IP)
  mqttClient.publish('log', "StartBot")
except ConnectionRefusedError as e:
  exit(30)

sync_json_path = join(dirname(__file__), 'sync.json')
file = open(sync_json_path)
users = json.load(file)

print('clean')
mqttClient.publish('esp-rfid/cmd', json.dumps({
     'cmd': 'deletusers',
     'doorip': ESPRFID_IP
  }))

for u in users:
  print(u['fullName'])
  hex_string = u['cardNumber']
  hex_string_pad = hex_string.zfill(14)
  hex_string_cut = hex_string_pad[:8]
  hex_data = bytearray.fromhex(hex_string_cut)
  hex_reverse = hex_data.reverse()
  hex_reverse = "".join(map(lambda b: format(b, "02x"), hex_data))
  print(u['cardNumber'])
  print(hex_reverse)
  mqttClient.publish('esp-rfid/cmd', json.dumps({
      'cmd': 'adduser',
      'doorip': ESPRFID_IP,
      'uid': hex_reverse,
      'user': u['fullName'],
      'acctype': u['accessLevel'],
      'pincode': u['Pin'],
      'validuntil': u['validUntil']
  }))

os.remove(sync_json_path)
