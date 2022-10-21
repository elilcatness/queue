import json
import os

from dotenv import load_dotenv
from telegram.ext import (Updater, CommandHandler, MessageHandler,
                          ConversationHandler, CallbackContext, Filters, CallbackQueryHandler)

from src.db.db_session import global_init, create_session
from src.db.models.state import State
from src.menu import menu, ask_surname, finish_registration, ask_name
from src.queue import QueueView


def load_states(updater: Updater, conv_handler: ConversationHandler):
    with create_session() as session:
        for state in session.query(State).all():
            conv_handler._conversations[(state.user_id, state.user_id)] = state.callback
            user_data = json.loads(state.data)
            updater.dispatcher.user_data[state.user_id] = user_data
            context = CallbackContext(updater.dispatcher)
            context._bot = updater.bot
            for job in updater.dispatcher.job_queue.get_jobs_by_name('process'):
                job.schedule_removal()


def main():
    updater = Updater(os.getenv('token'))
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', menu)],
        allow_reentry=True,
        states={
            'menu': [CallbackQueryHandler(QueueView.show_all, pattern='(active)|(planned)|(archived)')],
            'ask_name': [MessageHandler(Filters.text, ask_surname),
                         CallbackQueryHandler(menu, pattern='back')],
            'ask_surname': [MessageHandler(Filters.text, finish_registration),
                            CallbackQueryHandler(ask_name, pattern='back')],
            'queues': [CallbackQueryHandler(QueueView.show, pattern='[0-9]+'),
                       CallbackQueryHandler(menu, pattern='back')],
            'queue': [CallbackQueryHandler(QueueView.register, pattern='[0-9]+'),
                      CallbackQueryHandler(QueueView.show_all, pattern='back')]
        },
        fallbacks=[CommandHandler('start', menu)])
    updater.dispatcher.add_handler(conv_handler)
    load_states(updater, conv_handler)
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    load_dotenv()
    global_init(os.getenv('DATABASE_URL'))
    main()
