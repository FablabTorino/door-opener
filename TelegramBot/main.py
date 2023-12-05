from xxlimited import new
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
DOOR1_IP = os.getenv('DOOR1_IP')
if DOOR1_IP is None:
    logging.error('DOOR1_IP not set in .env')
DOOR2_IP = os.getenv('DOOR2_IP')
if DOOR2_IP is None:
    logging.error('DOOR2_IP not set in .env')
DOOR3_IP = os.getenv('DOOR3_IP')
if DOOR3_IP is None:
    logging.error('DOOR3_IP not set in .env')
DOOR4_IP = os.getenv('DOOR4_IP')
if DOOR4_IP is None:
    logging.error('DOOR4_IP not set in .env')
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
TOKEN = os.getenv('WINDDOC_TOKEN')
if TOKEN is None:
    logging.error("WINDDOC_TOKEN not set in .env")
TOKEN_APP = os.getenv('WINDDOC_TOKEN_APP')
if TOKEN_APP is None:
    logging.error("WINDDOC_TOKEN_APP not set in .env")

URL = "https://app.winddoc.com/v1/api_json.php";

def wiegand_format_to_card_number(wiegand: str) -> str:
  hex_string = wiegand.zfill(8)
  hex_data = bytearray.fromhex(hex_string)
  hex_data.reverse()
  return hex_data.hex()

def http_build_query(dictionary, parent_key=False, separator='.', separator_suffix=''):
    """
    Turn a nested dictionary into a flattened dictionary
    :param dictionary: The dictionary to flatten
    :param parent_key: The string to prepend to dictionary's keys
    :param separator: The string used to separate flattened keys
    :return: A flattened dictionary
    """

    items = []
    for key, value in dictionary.items():
        new_key = str(parent_key) + separator + key + separator_suffix if parent_key else key
        if isinstance(value, MutableMapping):
            items.extend(http_build_query(value, new_key, separator, separator_suffix).items())
        elif isinstance(value, list) or isinstance(value, tuple):
            for k, v in enumerate(value):
                items.extend(http_build_query({str(k): v}, new_key, separator, separator_suffix).items())
        else:
            items.append((new_key, value))
    return dict(items)

def WindDoc_search( uid: str, hostname: str, syncpin: bool):
    headers = CaseInsensitiveDict()
    headers["accept"] = "application/json"
    headers["Content-Type"] = "application/x-www-form-urlencoded"

    cercasocio = {"method":"associazioni_soci_lista","request":{"token_key":{"token":TOKEN, "token_app":TOKEN_APP},"query": "campo1 like '"+ wiegand_format_to_card_number(uid) +"%'"}}
    cercasocio = http_build_query(cercasocio, False, '[', ']')
    q_cercasocio = urlencode(cercasocio)

    r = requests.post(URL, headers=headers, data=q_cercasocio)
    if json.loads(r.content) is not None:
        returnedData = json.loads(r.content)
        selectlista = returnedData['lista']
        filterdata = str(selectlista).strip('[]').strip('"')
    else:
        return new_card_presented(uid,hostname)

    if not len(filterdata) == 0:
        newlist = json.dumps(eval(filterdata))
        utente = json.loads(newlist)

        if utente['stato_socio'] == "3" or utente['deve_rinnovare'] == True :
            subs_not_renewed(utente['contatto_nome'] + " " + utente['contatto_cognome'], hostname)
        else:
            pincode = utente['campo6']

            if utente['campo2']== '1':
                acctype = '99'
            else:
                acctype = '1'

            if re.match(r'[0-9]?([0-9])\1\1+', utente['campo6'], re.M) is not None:
                pincode = 'xxxx'

            if re.match(r'\d{4}', utente['campo6']) is None:
                pincode = 'xxxx' 

            date=datetime.datetime.strptime(str(utente['data_scadenza_rinnovo']),"%Y-%m-%d")
            date=date.timestamp()
            adduser_mqtt(uid,utente['contatto_nome'] + " " + utente['contatto_cognome'],acctype,pincode,int(round(date)),syncpin)

    else:
        new_card_presented(uid,hostname)

mqttClient = mqtt.Client('TelegramBot')
last_mqtt_message = time.time()

# Telegram Bot setup
updater = Updater(TOKEN_TBOT)
dispatcher = updater.dispatcher


# Telegram Bot

def help_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Comandi Disponobili: /open per aprire la porta oppure usa /sync per sincronizzare manualmente con WindDoc')


def open_command(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [
            InlineKeyboardButton('Annulla', callback_data='open_cancel'),
            InlineKeyboardButton('EGEO18-INT', callback_data=f'open_confirm_{DOOR1_IP}')
        ],
        [
            InlineKeyboardButton('EGEO18-EXT', callback_data=f'open_confirm_{DOOR2_IP}'),
            InlineKeyboardButton('EGEO18-FABLAB', callback_data=f'open_confirm_{DOOR3_IP}')
        ],
        [
            InlineKeyboardButton('FABLAB-MAKEIT', callback_data=f'open_confirm_{DOOR4_IP}')
        ]
    ]
    update.message.reply_text('Quale porta devo aprire?',
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
    _text = f'Fablab Torino Door Bot Avviato'
    dispatcher.bot.send_message(chat_id=CHAT_ID_TBOT,
                                parse_mode=ParseMode.HTML,
                                text=_text)
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
        dispatcher.bot.send_message(chat_id=CHAT_ID_TBOT,
                                    text=f'Porta {command["hostname"]} aperta via MQTT')

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

def updt_start( hostname: str):
    logging.info('Aggiornamento dispositivo ' + str(hostname) + ' avviato')
    _text = f'Aggiornamento dispositivo {hostname} avviato'
    dispatcher.bot.send_message(chat_id=CHAT_ID_TBOT,
                                parse_mode=ParseMode.HTML,
                                text=_text)

def updt_stop( hostname: str):
    logging.info('L\'aggiornamento dispositivo ' + str(hostname) + ' è terminato!')
    _text = f'L\'aggiornamento del dispositivo {hostname} è terminato!'
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

def subs_not_renewed(uid: str, hostname: str):
    logging.info('Utente ' + str(uid) + ' con tessera scaduta ha tentato di accedere da ' + str(hostname))
    _text = f'La #tessera <b>{uid}</b> ha provato ad aprire la porta {hostname}, ma non ha rinnovato la quota associativa.'
    dispatcher.bot.send_message(chat_id=CHAT_ID_TBOT,
                                parse_mode=ParseMode.HTML,
                                text=_text)


# MQTT

def opendoor_mqtt(query):
    door_ip = query.data[len('open_confirm_'):]
    logging.info('opendoor_mqtt ' + door_ip)
    if door_ip == DOOR1_IP:
        _payload = json.dumps({'cmd': 'opendoor', 'doorip': DOOR1_IP})
        query.edit_message_text(
            text=f'@{query.from_user.username} ha aperto la porta EGEO18-INT da #remoto')
        return mqttClient.publish(ESPRFID_MQTT_TOPIC + '/cmd', _payload)
    elif door_ip == DOOR2_IP:
        _payload = json.dumps({'cmd': 'opendoor', 'doorip': DOOR2_IP})
        query.edit_message_text(
            text=f'@{query.from_user.username} ha aperto la porta EGEO18-EXT da #remoto')
        return mqttClient.publish(ESPRFID_MQTT_TOPIC + '/cmd', _payload)
    elif door_ip == DOOR3_IP:
        _payload = json.dumps({'cmd': 'opendoor', 'doorip': DOOR3_IP})
        query.edit_message_text(
            text=f'@{query.from_user.username} ha aperto la porta EGEO18-FABLAB da #remoto')
        return mqttClient.publish(ESPRFID_MQTT_TOPIC + '/cmd', _payload)
    elif door_ip == DOOR4_IP:
        _payload = json.dumps({'cmd': 'opendoor', 'doorip': DOOR4_IP})
        query.edit_message_text(
            text=f'@{query.from_user.username} ha aperto la porta FABLAB-MAKEIT da #remoto')
        return mqttClient.publish(ESPRFID_MQTT_TOPIC + '/cmd', _payload)

def adduser_mqtt(uid: str, user: str, acctype: str, pincode: str, validuntil: str, syncpin: bool):
    if syncpin is False:
        logging.info('Utente ' + str(uid) + ' con tessera valida trovato su Winddoc lo aggiungo alle porte')
        _text = f'Utente {user} presente su WindDoc ma non sulle porte, lo aggiungo'
    else:
        logging.info('Utente ' + str(uid) + 'ha imputato un pin errato, lo sincronizzo con WindDoc')
        _text = f'Utente {user} ha imputato un pin errato, lo sincronizzo con WindDoc'
    dispatcher.bot.send_message(chat_id=CHAT_ID_TBOT,
                                parse_mode=ParseMode.HTML,
                                text=_text)

    _payload = json.dumps({'cmd': 'adduser', 'doorip': DOOR1_IP, 'uid': str(uid), "user": str(user) , "acctype": str(acctype), "pincode": str(pincode), "validuntil": str(validuntil)})
    mqttClient.publish(ESPRFID_MQTT_TOPIC + '/cmd', _payload)

    _payload2 = json.dumps({'cmd': 'adduser', 'doorip': DOOR2_IP, 'uid': str(uid), "user": str(user) , "acctype": str(acctype), "pincode": str(pincode), "validuntil": str(validuntil)})
    mqttClient.publish(ESPRFID_MQTT_TOPIC + '/cmd', _payload2)

    _payload3 = json.dumps({'cmd': 'adduser', 'doorip': DOOR3_IP, 'uid': str(uid), "user": str(user) , "acctype": str(acctype), "pincode": str(pincode), "validuntil": str(validuntil)})
    mqttClient.publish(ESPRFID_MQTT_TOPIC + '/cmd', _payload3)

    _payload4 = json.dumps({'cmd': 'adduser', 'doorip': DOOR4_IP, 'uid': str(uid), "user": str(user) , "acctype": str(acctype), "pincode": str(pincode), "validuntil": str(validuntil)})
    mqttClient.publish(ESPRFID_MQTT_TOPIC + '/cmd', _payload4)

def sync_bash():
    logging.info('sync_bash')
    os.system(WINDDOC_SYNC_PATH)


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
    _access = _json.get('access')
    _is_known = _json.get('isKnown')
    _src = _json.get('src')
    _desc = _json.get('desc')

    if _type == 'access':
        if _is_known == 'true':
            if _access in ['Admin', 'Always'] and not same_timestamp_as_previous_message:
                access_allowed(_json)
            elif _access == 'Disabled':
                disabled_card_presented(_json.get('username'), _json.get('hostname'))
            elif _access =='Wrong pin code':
                WindDoc_search(_json.get('uid'), _json.get('hostname'),True)
        elif _is_known == 'false':
            WindDoc_search(_json.get('uid'), _json.get('hostname'),False)
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
        elif _src == 'updt':
            if _desc == 'Firmware update started':
                updt_start(_json.get('hostname'))
            elif _desc == 'Firmware update is finished':
                updt_stop(_json.get('hostname'))
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
                attempts = 15
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
