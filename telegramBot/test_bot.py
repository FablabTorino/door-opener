import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, InlineQueryResultArticle, ParseMode, InputTextMessageContent
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, InlineQueryHandler, ConversationHandler, MessageHandler, Filters
from telegram.utils.helpers import escape_markdown

import json
from uuid import uuid4
import os
from os.path import join, dirname
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
import logging
import re

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

mqttBroker = os.getenv('MQTT_BROKER_IP')
espRfidIp = os.getenv('ESPRFID_IP')
token = os.getenv('TOKEN')
doorOpenerChatId = os.getenv('CHAT_ID')

mqttClient = mqtt.Client('esp-rfid')
try:
    mqttClient.connect(mqttBroker)
except ConnectionRefusedError as e:
    logging.error(e)
    exit(30)

updater = Updater(token)
dispatcher = updater.dispatcher


def unknown(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text='Ops, comando non riconosciuto')


def help_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Usa /open per aprire la porta')


def open_command(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [
            InlineKeyboardButton('Annulla', callback_data='open_cancel'),
            InlineKeyboardButton('Apri', callback_data='open'),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Sicuro che devo aprire la porta?',
                              reply_markup=reply_markup)


def access_allowed(command):
    dispatcher.bot.send_message(chat_id=doorOpenerChatId,
                                text=f'{command["username"]} ha aperto la porta con la #tessera')


def new_card_presented(command):
    keyboard = [
        [
            InlineKeyboardButton('Aggiungi',
                                 callback_data=f'add_card_{command["uid"]}'),
            InlineKeyboardButton('Apri',
                                 callback_data=f'open_card_{command["uid"]}'),
        ],
        [InlineKeyboardButton('Ignora',
                              callback_data=f'add_cancel_{command["uid"]}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    dispatcher.bot.send_message(chat_id=doorOpenerChatId,
                                reply_markup=reply_markup,
                                text=f'La #tessera {command["uid"]} ha provato ad aprire la porta, ma non è abilitata. Cosa faccio?'
                                )


def add_user_prompt(query):
    uid = query.data[len('add_card_'):]
    keyboard = [
        [
            InlineKeyboardButton('Annulla', callback_data=f'add_cancel_{uid}'),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(reply_markup=reply_markup,
                            text=f'@{query.from_user.username} sta aggiungendo la #tessera {uid}. Che nome gli associo?'
                            )


def add_user(update: Update, context: CallbackContext) -> None:
    name_for_new_card = update.message.text
    sent_from = update.message.from_user.username
    reply_to = update.message.reply_to_message
    reply_to_text = reply_to.text

    if len(reply_to.entities) != 2:
        return
    original_user = reply_to_text[
                    reply_to.entities[0].offset + 1:reply_to.entities[
                        0].length]
    if original_user != sent_from:
        return

    card_number_match = re.match('.+(?=\\.)', reply_to_text[
                                              reply_to.entities[1].offset +
                                              reply_to.entities[
                                                  1].length + 1:])
    if card_number_match is None:
        return
    card_number = card_number_match.group()

    dispatcher.bot.edit_message_text(chat_id=doorOpenerChatId,
                                     message_id=reply_to.message_id,
                                     text=f'@{sent_from} ha aggiunto {name_for_new_card} #tessera {card_number}')

    save_new_card(card_number, name_for_new_card)


def save_new_card(card_number, name_for_new_card):
    mqttClient.publish('esp-rfid', json.dumps({
        'cmd': 'adduser',
        'doorip': espRfidIp,
        'uid': card_number,
        'username': name_for_new_card
    }))
    # TODO save on file


def unmanaged_command(command):
    dispatcher.bot.send_message(chat_id=doorOpenerChatId,
                                text=f'#tessera presentata, ma con comando non gestito')


def messages_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    if query.data == 'open':
        query.edit_message_text(
            text=f'@{query.from_user.username} ha aperto la porta da #remoto')
        mqttClient.publish('esp-rfid', json.dumps({
            'cmd': 'opendoor',
            'doorip': espRfidIp
        }))
    elif query.data == 'open_cancel':
        query.edit_message_text(
            text=f'Tentativo di @{query.message.reply_to_message.from_user.username} di aprire la porta annullato da @{query.from_user.username}')
    elif query.data.startswith('open_card'):
        query.edit_message_text(
            text=f'@{query.from_user.username} ha aperto alla #tessera {query.data[len("open_card_"):]}')
        mqttClient.publish('esp-rfid', json.dumps({
            'cmd': 'opendoor',
            'doorip': espRfidIp
        }))
    elif query.data.startswith('add_cancel'):
        query.edit_message_text(
            text=f'@{query.from_user.username} ha ignorato la #tessera {query.data[len("add_cancel_"):]}')
    elif query.data.startswith('add_card'):
        add_user_prompt(query)
    else:
        query.edit_message_text(
            text=f'Risposta non riconosciuta, comando annullato.')


def on_mqtt_message(client, userdata, message):
    command = json.loads(message.payload)
    if (command.__contains__('type') and command['type'] == 'access' and (
            command['access'] == 'Admin' or command['access'] == 'Always')):
        access_allowed(command)
    elif (command.__contains__('type') and command['type'] == 'access' and
          command['access'] == 'Denied'):
        new_card_presented(command)
    elif command.__contains__('cmd') and command['cmd'] == 'opendoor':
        pass
    else:
        unmanaged_command(command)


def main() -> None:
    mqttClient.loop_start()

    mqttClient.subscribe('esp-rfid')
    mqttClient.on_message = on_mqtt_message

    dispatcher.add_handler(CommandHandler('help', help_command))
    dispatcher.add_handler(CommandHandler('open', open_command))
    dispatcher.add_handler(CallbackQueryHandler(messages_callback))

    dispatcher.add_handler(
        MessageHandler(Filters.text & ~Filters.command, add_user))

    unknown_handler = MessageHandler(Filters.command, unknown)
    dispatcher.add_handler(unknown_handler)

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
