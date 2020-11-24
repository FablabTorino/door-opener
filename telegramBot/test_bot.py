from telegram.ext import Updater
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler, Filters

from uuid import uuid4

from telegram import InlineQueryResultArticle, ParseMode, InputTextMessageContent, Update
from telegram.ext import InlineQueryHandler, CallbackContext
from telegram.utils.helpers import escape_markdown

# Abilito logging basico, potrebbe andare molto più nel dettaglio.
import logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def start(update, context):
	context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

def echo(update, context):
	context.bot.send_message(chat_id=update.effective_chat.id, text=update.message.text)

# Interessante perché prende come input tutto quello che viene passato dopo il comando nello stesso messaggio
# es: /caps ciao --> CIAO
def caps(update, context):
    text_caps = ' '.join(context.args).upper() # context.args contiene il messaggio dopo il comando
    context.bot.send_message(chat_id=update.effective_chat.id, text=text_caps)

# Gestione dei casi base: comando non conosciuto, richiesta di aiuto
def unknown(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, I didn't understand that command.")

def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    update.message.reply_text('Help!')

# Interessante perché usa le inlinequery, usabili con la sintassi "@botUsername testo"
def inlinequery(update: Update, context: CallbackContext) -> None:
    """Handle the inline query."""
    query = update.inline_query.query
    results = [
        InlineQueryResultArticle(
            id=uuid4(), title="Caps", input_message_content=InputTextMessageContent(query.upper())
        ),
        InlineQueryResultArticle(
            id=uuid4(),
            title="Bold",
            input_message_content=InputTextMessageContent(
                "*{}*".format(escape_markdown(query)), parse_mode=ParseMode.MARKDOWN
            ),
        ),
        InlineQueryResultArticle(
            id=uuid4(),
            title="Italic",
            input_message_content=InputTextMessageContent(
                "_{}_".format(escape_markdown(query)), parse_mode=ParseMode.MARKDOWN
            ),
        ),
    ]

    update.inline_query.answer(results)


def main() -> None:
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(TOKEN, use_context=True)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))

    # Questo non è gestisce i comandi (/comando), ma direttamente i messaggi di testo inviati normalmente senza formattazione specifica
    echo_handler = MessageHandler(Filters.text & (~Filters.command), echo) # Coi filters faccio una scrematura dei messaggi che mi arrivano, e prendo solo quelli testuali
    dispatcher.add_handler(echo_handler)

    caps_handler = CommandHandler('caps', caps)
    dispatcher.add_handler(caps_handler)

    unknown_handler = MessageHandler(Filters.command, unknown) # Filtro, e prendo tutti i messaggi formattati come comando, che però io non so gestire
    dispatcher.add_handler(unknown_handler)

    # on noncommand i.e message - echo the message on Telegram
    dispatcher.add_handler(InlineQueryHandler(inlinequery))

    # Start the Bot
    updater.start_polling()

    # Block until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()

if __name__ == '__main__':
    main()