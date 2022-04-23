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
    logging.error("MQTT_BROKER_IP not set in .env")
DOOR1_IP = os.getenv('DOOR1_IP')
if DOOR1_IP is None:
    logging.error("DOOR1_IP not set in .env")
DOOR2_IP = os.getenv('DOOR2_IP')
if DOOR2_IP is None:
    logging.error("DOOR2_IP not set in .env")
TOKEN_TBOT = os.getenv('TOKEN_TBOT')
if TOKEN_TBOT is None:
    logging.error("token not set in .env")
CHAT_ID_TBOT = os.getenv('CHAT_ID_TBOT')
if CHAT_ID_TBOT is None:
    logging.error("CHATID_TBOT not set in .env")
CHAT_ID_TBOT = int(CHAT_ID_TBOT)
ESPRFID_MQTT_TOPIC = os.getenv('ESPRFID_MQTT_TOPIC')
if ESPRFID_MQTT_TOPIC is None:
    logging.error("ESPRFID_MQTT_TOPIC not set in .env")

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
            InlineKeyboardButton('Apri EGEO16', callback_data='open_confirm_{DOOR1_IP}'),
            InlineKeyboardButton('Apri INTERNO TOOLBOX', callback_data='open_confirm_{DOOR2_IP}'),
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
        query.edit_message_text(
            text=f'@{query.from_user.username} ha aperto la porta {query.data[len("open_confirm_"):]} da #remoto')
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
    elif query.data.startswith('add_cancel'):
        query.edit_message_text(
            text=f'@{query.from_user.username} ha ignorato la #tessera {query.data[len("add_cancel_"):]}')
    elif query.data.startswith('add_card'):
        add_user_prompt(query)
    elif query.data.startswith('discard_open_'):
        query.edit_message_text(
            f'@{query.from_user.username} ha aperto alla #tessera {query.data[len("discard_open_"):]}')
        opendoor_mqtt()
    elif query.data.startswith('discard_cancel_'):
        query.edit_message_text(
            f'@{query.from_user.username} ha ignorato la #tessera di {query.data[len("discard_cancel_"):]}')
    else:
        query.edit_message_text(
            text=f'Risposta non riconosciuta, comando annullato.')


def text_message(update: Update, context: CallbackContext) -> None:
    name_for_new_card = update.message.text
    sent_from = update.message.from_user.username
    reply_to = update.message.reply_to_message

    if reply_to is None:  # or len(reply_to.entities) != 2:
        return

    reply_to_text = reply_to.text
    original_user = reply_to_text[
                    reply_to.entities[0].offset + 1:reply_to.entities[
                        0].length]
    if original_user != sent_from:
        return

    card_number_match = re.match('.+(?=\\.)',
                                 reply_to_text[
                                 reply_to.entities[1].offset +
                                 reply_to.entities[1].length + 1:])
    if card_number_match is None:
        return
    card_number = card_number_match.group()

    dispatcher.bot.edit_message_text(chat_id=CHAT_ID_TBOT,
                                     message_id=reply_to.message_id,
                                     text=f'@{sent_from} ha aggiunto {name_for_new_card} #tessera {card_number}')

    save_new_card(card_number, name_for_new_card)


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
    # Other messages
    dispatcher.add_handler(MessageHandler(
        ~Filters.command & chat_filter, text_message))
    # Other chat
    dispatcher.add_handler(MessageHandler(
        ~Filters.chat(CHAT_ID_TBOT), unknown_chat))

    updater.start_polling()
    updater.idle()


def access_allowed(command):
    logging.info("open to : " + str(command))
    dispatcher.bot.send_message(chat_id=CHAT_ID_TBOT,
                                text=f'{command["username"]} ha aperto la porta {command["hostname"]} con la #tessera')


def new_card_presented(uid: str):
    logging.info("new_card_presented : " + str(uid))
    #keyboard = [[
     #   InlineKeyboardButton('Ignora', callback_data=f'add_cancel_{uid}'),
      #  InlineKeyboardButton('Aggiungi', callback_data=f'add_card_{uid}')]]

    #reply_markup = InlineKeyboardMarkup(keyboard)
    _text = f'La \#tessera *{uid}* ha provato ad aprire la porta, ma non è attiva\.'
#    _text = f'La \#tessera *{uid}* ha provato ad aprire la porta, ma non è attiva\. Cosa faccio?'
    dispatcher.bot.send_message(chat_id=CHAT_ID_TBOT,
    #                            reply_markup=reply_markup,
                                parse_mode=ParseMode.MARKDOWN_V2,
                                text=_text)


def disabled_card_presented(username: str):
    logging.info("disabled_card_presented : " + str(username))
    keyboard = [[
        InlineKeyboardButton('Ignora',
                             callback_data=f'discard_cancel_{username}'),
        InlineKeyboardButton('Apri',
                             callback_data=f'discard_open_{username}')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    _text = f'La \#tessera *{username}* ha provato ad aprire la porta, ma non è fuori orario\.\nCosa faccio?'
    dispatcher.bot.send_message(chat_id=CHAT_ID_TBOT,
                                reply_markup=reply_markup,
                                parse_mode=ParseMode.MARKDOWN_V2,
                                text=_text)


def add_user_prompt(query):
    uid = query.data[len('add_card_'):]
    keyboard = [
        [InlineKeyboardButton('Annulla', callback_data=f'add_cancel_{uid}'), ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(reply_markup=reply_markup,
                            text=f'@{query.from_user.username} sta aggiungendo la #tessera {uid}. Che nome gli associo?\n(Rispondi a questo messaggio)'
                            )


def save_new_card(card_number, name_for_new_card):
    adduser_mqtt(card_number, name_for_new_card)
    # TODO save on file


# MQTT

def opendoor_mqtt(query):
    DOORIP = query.data[len('open_confirm_'):]
    if DOORIP == DOOR1_IP:
        logging.info("opendoor_mqtt")
        _payload = json.dumps({'cmd': 'opendoor', 'doorip': DOOR1_IP})
        query.edit_message_text(
            text=f'@{query.from_user.username} ha aperto la porta EGEO16 da #remoto')
        return mqttClient.publish(ESPRFID_MQTT_TOPIC + '/cmd', _payload)

    elif DOORIP == DOOR2_IP:
        logging.info("opendoor_mqtt")
        _payload = json.dumps({'cmd': 'opendoor', 'doorip': DOOR2_IP})
        query.edit_message_text(
            text=f'@{query.from_user.username} ha aperto la porta INTERNA TOOLBOX da #remoto')
        return mqttClient.publish(ESPRFID_MQTT_TOPIC + '/cmd', _payload)

def sync_bash():
    logging.info("sync_bash")
    os.system(WINDDOC_SYNC_PATH)
    return

def adduser_mqtt(uid: str, user: str, acctype: int = 0):
    logging.info("adduser_mqtt: " + uid + ' ' + user)
    end_of_the_year = datetime(datetime.now().year + 1, 1, 1).timestamp() - 59
    _payload = json.dumps({
        'cmd': 'adduser',
        'doorip': ESPRFID_IP,
        'uid': uid,
        'user': user,
        'acctype': acctype,
        'validuntil': end_of_the_year
    })
    return mqttClient.publish(ESPRFID_MQTT_TOPIC + '/cmd', _payload)


def on_mqtt_message(client, userdata, message):
    _i = '[MQTT] '
    last_mqtt_message = time.time()
    try:
        _json = json.loads(message.payload)
    except BaseException as e:
        logging.error(e)
        return

    if message.topic == ESPRFID_MQTT_TOPIC:  # loopback
        pass

    elif message.topic == ESPRFID_MQTT_TOPIC + '/send':
        _type = _json.get('type')
        _cmd = _json.get('cmd')
        if _type == 'access':
            _access = _json.get('access')
            _is_know = _json.get('isKnown')
            if _is_know == 'true':
                if _access in ['Admin', 'Always']:
                    access_allowed(_json)
                    return
                elif _access == 'Disabled':
                    disabled_card_presented(_json.get('username'))
                    return
                else:
                    logging.warning(_i + "access '%s' non gestito ", _access)
            elif _is_know == 'false':
                new_card_presented(_json.get('uid'))
                return
            else:
                logging.warning(_i + "isKnow '%s' non gestito ", _is_know)
        elif _type == 'WARN':
            pass
        elif _type == 'INFO':
            logging.info(_i + "INFO " + _json.get('src'))
        elif _cmd == 'opendoor':
            logging.info(_i + "opendoor")
            return
        elif _cmd == 'listusr':
            pass
        elif _cmd == 'deletusers':
            pass
        elif _cmd == 'deletuid':
            pass
        elif _cmd == 'adduser':
            pass
        elif _json.get('command') == 'userfile':
            pass
        else:
            logging.warning(_i + "type '%s' and cmd '%s' non gestiti",
                            _type, _cmd)
    elif message.topic == ESPRFID_MQTT_TOPIC + '/send':
        _type = _json.get('type')
        if _type == 'heartbeat':  # heartbeat
            pass
        else:
            logging.warning(_i + "TOPIC '%s' non gestito", message.topic)
    elif message.topic == ESPRFID_MQTT_TOPIC + '/accesslist':
        logging.warning(_i + "TOPIC '%s' non gestito", message.topic)
    else:
        logging.warning(_i + "TOPIC '%s' non gestito", message.topic)
    logging.info(_i + "TOPIC: '%s', PAYLOAD: '%s'", message.topic,
                 message.payload)


def mqtt_setup():
    """ MQTT setup """
    logging.info("start MQTT setup")

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
    mqttClient.subscribe(ESPRFID_MQTT_TOPIC)
    mqttClient.subscribe(ESPRFID_MQTT_TOPIC + '/send')
    mqttClient.subscribe(ESPRFID_MQTT_TOPIC + '/sync')
    mqttClient.subscribe(ESPRFID_MQTT_TOPIC + '/accesslist')
    mqttClient.on_message = on_mqtt_message
    logging.debug("end MQTT setup")


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
