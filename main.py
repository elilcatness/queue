import json
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from telegram.ext import (Updater, CommandHandler, MessageHandler,
                          ConversationHandler, CallbackContext, Filters, CallbackQueryHandler)

from src.db.db_session import global_init, create_session
from src.db.models.queue import Queue
from src.db.models.state import State
from src.menu import menu, ask_surname, finish_registration, ask_name
from src.queue import QueueView, QueueAdd, notify_queue, open_queue, close_queue


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


def start_jobs(dispatcher, bot):
    context = CallbackContext(dispatcher)
    context._bot = bot
    with create_session() as session:
        for q in session.query(Queue).filter(Queue.status != 'archived').all():
            if q.status == 'planned':
                if not q.notification_sent:
                    secs = (q.notify_dt - datetime.utcnow() - timedelta(hours=3)).total_seconds()
                    context.job_queue.run_once(
                        notify_queue, secs if secs >= 0 else 0,
                        context=context, name=str(q.id))
                secs = (q.start_dt - datetime.utcnow() - timedelta(hours=3)).total_seconds()
                context.job_queue.run_once(
                    open_queue, secs if secs >= 0 else 0,
                    context=context, name=str(q.id))
            secs = (q.end_dt - datetime.utcnow() - timedelta(hours=3)).total_seconds()
            context.job_queue.run_once(
                close_queue, secs if secs >= 0 else 0,
                context=context, name=str(q.id))


def main():
    updater = Updater(os.getenv('token'))
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', menu)],
        allow_reentry=True,
        states={
            'menu': [CallbackQueryHandler(QueueView.show_all, pattern='(active)|(planned)|(archived)'),
                     CallbackQueryHandler(QueueAdd.ask_name, pattern='add_queue')],
            'ask_name': [MessageHandler(Filters.text, ask_surname),
                         CallbackQueryHandler(menu, pattern='back')],
            'ask_surname': [MessageHandler(Filters.text, finish_registration),
                            CallbackQueryHandler(ask_name, pattern='back')],
            'queues': [CallbackQueryHandler(QueueView.show, pattern='[0-9]+'),
                       CallbackQueryHandler(QueueView.set_next_page, pattern='next_page'),
                       CallbackQueryHandler(QueueView.show_all, pattern='refresh'),
                       CallbackQueryHandler(QueueView.set_previous_page, pattern='prev_page'),
                       MessageHandler(Filters.regex('[0-9]+'), QueueView.set_page),
                       CallbackQueryHandler(menu, pattern='back')],
            'queue': [CallbackQueryHandler(QueueView.register, pattern='[0-9]+'),
                      CallbackQueryHandler(QueueView.show_all, pattern='back')],
            'QueueAdd.ask_name': [MessageHandler(Filters.text, QueueAdd.ask_start_dt),
                                  CallbackQueryHandler(menu, pattern='back')],
            'QueueAdd.ask_start_dt': [MessageHandler(Filters.text, QueueAdd.ask_end_dt),
                                      CallbackQueryHandler(QueueAdd.ask_name, pattern='back')],
            'QueueAdd.ask_end_dt': [MessageHandler(Filters.text, QueueAdd.ask_notify_dt),
                                    CallbackQueryHandler(QueueAdd.ask_start_dt, pattern='back')],
            'QueueAdd.ask_notify_dt': [MessageHandler(Filters.text, QueueAdd.finish),
                                       CallbackQueryHandler(QueueAdd.ask_end_dt, pattern='back')],
        },
        fallbacks=[CommandHandler('start', menu),
                   CallbackQueryHandler(QueueView.register, pattern='reg [0-9]+')])
    updater.dispatcher.add_handler(conv_handler)
    load_states(updater, conv_handler)
    start_jobs(updater.dispatcher, updater.bot)
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    load_dotenv()
    global_init(os.getenv('DATABASE_URL'))
    main()
