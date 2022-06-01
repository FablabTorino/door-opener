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
from datetime import datetime

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
DOOR1_IP = os.getenv('DOOR1_IP')
if DOOR1_IP is None:
    logging.error('DOOR1_IP not set in .env')
DOOR2_IP = os.getenv('DOOR2_IP')
if DOOR2_IP is None:
    logging.error('DOOR2_IP not set in .env')
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
WINDDOC_SYNC_PATH = os.getenv('WINDDOC_SYNC_PATH')
if WINDDOC_SYNC_PATH is None:
    logging.error('WINDDOC_SYNC_PATH not set in .env')


mqttClient = mqtt.Client('TelegramBot')
last_mqtt_message = time.time()

# Telegram Bot setup
updater = Updater(TOKEN_TBOT)
dispatcher = updater.dispatcher


# Telegram Bot

def help_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Usa /open per aprire la porta oppure usa /sync per sincronizzare manualmente con WindDoc')


def open_command(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [
            InlineKeyboardButton('Annulla', callback_data='open_cancel'),
            InlineKeyboardButton('Apri EGEO16', callback_data=f'open_confirm_{DOOR1_IP}'),
            InlineKeyboardButton('Apri INTERNO TOOLBOX', callback_data=f'open_confirm_{DOOR2_IP}'),
        ]
    ]
    update.message.reply_text('Sicuro che devo aprire la porta?',
                              reply_markup=InlineKeyboardMarkup(keyboard))


def sync_command(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [
            InlineKeyboardButton('Annulla', callback_data='sync_cancel'),
            InlineKeyboardButton('Sincronizza', callback_data='sync_confirm'),
        ]
    ]
    update.message.reply_text('Devo procedere alla sincronizzazione con Winddoc?',
                              reply_markup=InlineKeyboardMarkup(keyboard))


def unknown_command(update, context) -> None:
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text='Ops, comando non riconosciuto')


def callback_message(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    if query.data.startswith ('open_confirm'):
        opendoor_mqtt(query)
    elif query.data == 'open_cancel':
        query.edit_message_text(
            text=f'Tentativo di @{query.message.reply_to_message.from_user.username} di aprire la porta annullato da @{query.from_user.username}')
    elif query.data == 'sync_confirm':
        query.edit_message_text(
            text=f'@{query.from_user.username} ha sincronizzato con WindDoc manualmente')
        sync_bash()
    elif query.data == 'sync_cancel':
        query.edit_message_text(
            text=f'Tentativo di @{query.message.reply_to_message.from_user.username} di sincronizzazione annullato da @{query.from_user.username}')
    elif query.data.startswith('open_card'):
        query.edit_message_text(
            text=f'@{query.from_user.username} ha aperto alla #tessera {query.data[len("open_card_"):]}')
        opendoor_mqtt()
    else:
        query.edit_message_text(
            text=f'Risposta non riconosciuta, comando annullato.')


def unknown_chat(update: Update, context: CallbackContext):
    dispatcher.bot.sendMessage(chat_id=update.message.chat_id,
                               text="Sorry, this bot isn't for you.")


def tbot_setup():
    """Telegram Bot setup"""
    chat_filter = Filters.text & Filters.chat(CHAT_ID_TBOT)
    # /help
    dispatcher.add_handler(CommandHandler('help', help_command, chat_filter))
    # /open
    dispatcher.add_handler(CommandHandler('open', open_command, chat_filter))
    # /sync
    dispatcher.add_handler(CommandHandler('sync', sync_command, chat_filter))
    # /[unknown command]
    dispatcher.add_handler(MessageHandler(
        Filters.command & chat_filter, unknown_command))
    # Callback from Inline Keyboard
    dispatcher.add_handler(CallbackQueryHandler(callback_message))
    # Other chat
    dispatcher.add_handler(MessageHandler(
        ~Filters.chat(CHAT_ID_TBOT), unknown_chat))

    updater.start_polling()
    updater.idle()


def access_allowed(command):
    if command["username"] == 'MQTT':
        logging.info('[MQTT] opendoor')
    else:
        logging.info('open to : ' + str(command))
    dispatcher.bot.send_message(chat_id=CHAT_ID_TBOT,
                                text=f'{command["username"]} ha aperto la porta {command["hostname"]} con la #tessera')


def new_card_presented(uid: str, hostname: str):
    logging.info('new_card_presented : ' + str(uid))
    _text = f'La #tessera <b>{uid}</b> ha provato ad aprire la porta {hostname}, ma non è una tessera registrata.'
    dispatcher.bot.send_message(chat_id=CHAT_ID_TBOT,
                                parse_mode=ParseMode.HTML,
                                text=_text)

def boot_device( hostname: str):
    logging.info('Device boot : ' + str(hostname))
    _text = f'Il dispositivo {hostname} si è avviato!'
    dispatcher.bot.send_message(chat_id=CHAT_ID_TBOT,
                                parse_mode=ParseMode.HTML,
                                text=_text)

def enabling_wifi( hostname: str):
    logging.info('Il dispositivo ' + str(hostname) + ' si è riconnesso al wifi!')
    _text = f'Il dispositivo {hostname} si è riconnesso al wifi!'
    dispatcher.bot.send_message(chat_id=CHAT_ID_TBOT,
                                parse_mode=ParseMode.HTML,
                                text=_text)

def login_attemp( data: str, hostname: str):
    logging.info('Il dispositivo ' + str(data) + ' ha tentato di connettersi al device ' + str(hostname))
    _text = f'Il dispositivo {data} ha tentato di connettersi al device {hostname}'
    dispatcher.bot.send_message(chat_id=CHAT_ID_TBOT,
                                parse_mode=ParseMode.HTML,
                                text=_text)

def login_success( data: str, hostname: str):
    logging.info('Il dispositivo ' + str(data) + ' si è collegato al device ' + str(hostname) + ' via interfaccia web')
    _text = f'Il dispositivo {data} si è collegato al device {hostname} via interfaccia web'
    dispatcher.bot.send_message(chat_id=CHAT_ID_TBOT,
                                parse_mode=ParseMode.HTML,
                                text=_text)

def config_change( hostname: str):
    logging.info('La configurazione del dispositivo ' + str(hostname) + ' è stata modificata!')
    _text = f'La configurazione del dispositivo {hostname} è stata salvata'
    dispatcher.bot.send_message(chat_id=CHAT_ID_TBOT,
                                parse_mode=ParseMode.HTML,
                                text=_text)

def disabled_card_presented(username: str, hostname: str):
    logging.info('disabled_card_presented : ' + str(username) + ' ' + str(hostname))
    _text = f'La #tessera <b>{username}</b> ha provato ad aprire la porta {hostname}, ma l\'accesso non è consentito.'
    dispatcher.bot.send_message(chat_id=CHAT_ID_TBOT,
                                parse_mode=ParseMode.HTML,
                                text=_text)


# MQTT

def opendoor_mqtt(query):
    door_ip = query.data[len('open_confirm_'):]
    if door_ip == DOOR1_IP:
        logging.info('opendoor_mqtt')
        _payload = json.dumps({'cmd': 'opendoor', 'doorip': DOOR1_IP})
        query.edit_message_text(
            text=f'@{query.from_user.username} ha aperto la porta EGEO16 da #remoto')
        return mqttClient.publish(ESPRFID_MQTT_TOPIC + '/cmd', _payload)
    elif door_ip == DOOR2_IP:
        logging.info('opendoor_mqtt')
        _payload = json.dumps({'cmd': 'opendoor', 'doorip': DOOR2_IP})
        query.edit_message_text(
            text=f'@{query.from_user.username} ha aperto la porta INTERNA TOOLBOX da #remoto')
        return mqttClient.publish(ESPRFID_MQTT_TOPIC + '/cmd', _payload)


def sync_bash():
    logging.info('sync_bash')
    os.system(WINDDOC_SYNC_PATH)


def on_mqtt_message(client, userdata, message):
    _i = '[MQTT] '
    last_mqtt_message = time.time()
    try:
        _json = json.loads(message.payload)
    except BaseException as e:
        logging.error('JSON parsing error')
        logging.error(e)
        return

    _type = _json.get('type')
    _access = _json.get('access')
    _is_known = _json.get('isKnown')
    _src = _json.get('src')
    _desc = _json.get('desc')

    if _type == 'access':
        if _is_known == 'true':
            if _access in ['Admin', 'Always']:
                access_allowed(_json)
            elif _access == 'Disabled':
                disabled_card_presented(_json.get('username'), _json.get('hostname'))
        elif _is_known == 'false':
            new_card_presented(_json.get('uid'), _json.get('hostname'))
    elif _type == 'INFO':
        logging.info(_i + 'INFO ' + _json.get('src'))
        if _src == 'websrv':
            if _desc == 'Login success!':
                login_success(_json.get('data'), _json.get('hostname'))
        elif _src == 'sys':
            if _desc == 'Config stored in the SPIFFS':
                config_change (_json.get('hostname'))
        elif _src == 'wifi':
            if _desc == 'Enabling WiFi':
                enabling_wifi(_json.get('hostname'))
    elif _type == 'boot':
        boot_device(_json.get('hostname'))
    elif _type == 'WARN':
        if _src == 'websrv':
            if _desc == 'New login attempt':
                login_attemp(_json.get('data'), _json.get('hostname'))
        elif _src == 'sys':
            if _desc == 'Config stored in the SPIFFS':
                config_change (_json.get('hostname'))
    

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
    logging.debug('end MQTT setup')


def main() -> None:
    mqtt_setup()
    tbot_setup()
    while True:
        try:
            if time.time() - last_mqtt_message > 130:
                attempts = 5
                while attempts:
                    try:
                        mqttClient.connect(MQTT_BROKER_IP)
                        break
                    except BaseException as e:
                        logging.error(e)
                    attempts -= 1
                    time.sleep(0.1)

                mqttClient.subscribe(ESPRFID_MQTT_TOPIC)
                mqttClient.subscribe(ESPRFID_MQTT_TOPIC + '/send')
                mqttClient.subscribe(ESPRFID_MQTT_TOPIC + '/sync')
                mqttClient.subscribe(ESPRFID_MQTT_TOPIC + '/accesslist')
            time.sleep(1)
        except KeyboardInterrupt as e:
            exit(2)


if __name__ == '__main__':
    main()
