import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, \
    InlineQueryResultArticle, ParseMode, InputTextMessageContent, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, \
    CallbackContext, InlineQueryHandler, ConversationHandler, MessageHandler, \
    Filters
from telegram.utils.helpers import escape_markdown

import json
import os
from os.path import join, dirname
from dotenv import load_dotenv, find_dotenv
import paho.mqtt.client as mqtt
import logging
import re
import time
import datetime
import requests
from requests.structures import CaseInsensitiveDict
from collections.abc import MutableMapping
from urllib.parse import urlencode, unquote


logging_path = join(os.getcwd(), dirname(__file__), 'doorbot.log')
logging.basicConfig(
    filename=logging_path,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
   # format=' %(levelname)s - %(message)s', # use only for debugging
    level=logging.INFO)

# environment variables
dotenv_path = join(os.getcwd(), dirname(__file__), '.env')
load_dotenv(find_dotenv(dotenv_path, raise_error_if_not_found=True))

MQTT_BROKER_IP = os.getenv('MQTT_BROKER_IP')
if MQTT_BROKER_IP is None:
    logging.error('MQTT_BROKER_IP not set in .env')
TOKEN_TBOT = os.getenv('TOKEN_TBOT')
if TOKEN_TBOT is None:
    logging.error('token not set in .env')
CHAT_ID_TBOT = os.getenv('CHAT_ID_TBOT')
if CHAT_ID_TBOT is None:
    logging.error('CHATID_TBOT not set in .env')
CHAT_ID_TBOT = int(CHAT_ID_TBOT)
ESPRFID_MQTT_TOPIC = os.getenv('ESPRFID_MQTT_TOPIC')
if ESPRFID_MQTT_TOPIC is None:
    logging.error('ESPRFID_MQTT_TOPIC not set in .env')

logging.info(MQTT_BROKER_IP)

mqttClient = mqtt.Client('TelegramBot')
last_mqtt_message = time.time()

# Telegram Bot setup
updater = Updater(TOKEN_TBOT)
dispatcher = updater.dispatcher

# Telegram Bot

def unknown_command(update, context) -> None:
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text='Ops, comando non riconosciuto')

def unknown_chat(update: Update, context: CallbackContext):
    dispatcher.bot.sendMessage(chat_id=update.message.chat_id,
                               text="Sorry, this bot isn't for you.")

def tbot_setup():
    """Telegram Bot setup"""
    _text = f'Fablab Torino Bell Bot Avviato'
    dispatcher.bot.send_message(chat_id=CHAT_ID_TBOT,
                                parse_mode=ParseMode.HTML,
                                text=_text)
    chat_filter = Filters.text & Filters.chat(CHAT_ID_TBOT)
    # /[unknown command]
    dispatcher.add_handler(MessageHandler(
        Filters.command & chat_filter, unknown_command))
    # Other chat
    dispatcher.add_handler(MessageHandler(
        ~Filters.chat(CHAT_ID_TBOT), unknown_chat))

    updater.start_polling()
    updater.idle()

def doorbell_rang(hostname: str):
    logging.info('Campanello ' + str(hostname) + ' suonato')
    _text = f'{hostname} suona il campanello'
    dispatcher.bot.send_message(chat_id=CHAT_ID_TBOT,
                                parse_mode=ParseMode.HTML,
                                text=_text)

# MQTT

def on_mqtt_message(client, userdata, message):
    global last_mqtt_message
    same_timestamp_as_previous_message = False
    _i = '[MQTT] '

    try:
        _json = json.loads(message.payload)
    except BaseException as e:
        logging.error('JSON parsing error')
        logging.error(e)
        return

    if _json.get('time'):
        message_time = int(_json.get('time'))

        # we skip multiple messages with the same timestamp
        if message_time == last_mqtt_message:
            same_timestamp_as_previous_message = True

        last_mqtt_message = message_time

    _type = _json.get('type')
    _src = _json.get('src')

    if _type == 'INFO' and _src == 'doorbell':
        logging.info(_i + 'INFO ' + _json.get('type'))
        doorbell_rang(_json.get('hostname'))

def mqtt_setup():
    """ MQTT setup """
    logging.info('start MQTT setup')

    attempts = 5
    while attempts:
        try:
            mqttClient.connect(MQTT_BROKER_IP)
            break
        except BaseException as e:
            logging.error(e)
        attempts -= 1
        time.sleep(0.1)
    mqttClient.loop_start()
    mqttClient.subscribe(ESPRFID_MQTT_TOPIC + '/send')
    mqttClient.on_message = on_mqtt_message
    logging.info('end MQTT setup')

def main() -> None:
    mqtt_setup()
    tbot_setup()

    while True:
        try:
            if time.time() - last_mqtt_message > 130:
                attempts = 15
                while attempts:
                    try:
                        mqttClient.connect(MQTT_BROKER_IP)
                        break
                    except BaseException as e:
                        logging.error(e)
                    attempts -= 1
                    time.sleep(0.1)

                mqttClient.subscribe(ESPRFID_MQTT_TOPIC + '/send')
            time.sleep(1)
        except KeyboardInterrupt as e:
            exit(2)


if __name__ == '__main__':
    main()
