from telegram import Update, ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext

from src.constants import STATUS_VERBOSES, PAGINATION_STEP, VIEW_STATUS_VERBOSES
from src.db.db_session import create_session
from src.db.models.attendant import Attendant
from src.db.models.queue import Queue
from src.db.models.user import User
from src.menu import menu
from src.utils import build_pagination, delete_last_message


class QueueView:
    @staticmethod
    @delete_last_message
    def show_all(update: Update, context: CallbackContext):
        status = context.match.string
        if not status:
            context.bot.send_message(context.user_data['id'], 'Эээээ.... штота не так с кнопками')
            return menu(update, context)
        with create_session() as session:
            queues = [(f'{q.name} [{q.start_dt.strftime("%d.%m.%Y %H:%M")} – '
                       f'{q.end_dt.strftime("%d.%m.%Y %H:%M")}]', q.id)
                      for q in session.query(Queue).filter(Queue.status == status).all()]
            if not queues:
                context.bot.send_message(context.user_data['id'],
                                         f'Очередей со статусом {status} пока нет!')
                return menu(update, context)
            if not context.user_data.get('pagination'):
                context.user_data['pagination'] = 1
            markup, pages_count = build_pagination(
                queues, PAGINATION_STEP, context.user_data['pagination'])
            context.user_data['pages_count'] = pages_count
            return (context.bot.send_message(
                context.user_data['id'],
                f'Найдено {len(queues)} {STATUS_VERBOSES.get(status, "")} очередей'
                '\nДля выбора страницы в пагинации также можно отправить её номер',
                reply_markup=markup),
                    'queues')

    @staticmethod
    @delete_last_message
    def show(update: Update, context: CallbackContext):
        try:
            queue_id = int(context.match.string)
        except ValueError:
            context.bot.send_message(context.user_data['id'], 'Что-то не так с переходом')
            return menu(update, context)
        with create_session() as session:
            queue = session.query(Queue).get(queue_id)
            if not queue:
                context.bot.send_message(context.user_data['id'], 'Данной очереди не существует')
                return menu(update, context)
            buttons = [[InlineKeyboardButton('Вернуться назад', callback_data='back')]]
            if (int(context.user_data['id']) not in [att.user_id for att in queue.attendants]
                    and queue.status == 'active'):
                buttons.insert(0, [InlineKeyboardButton('Встать в очередь', callback_data=queue_id)])
            markup = InlineKeyboardMarkup(buttons)
            text = []
            for attr in Queue.verbose_attrs:
                val = getattr(queue, attr)
                if 'dt' in attr:
                    val = val.strftime('%d.%m.%Y %H:%M:%S')
                if attr == 'status':
                    val = VIEW_STATUS_VERBOSES.get(val, val)
                text.append(f'<b>{Queue.verbose_attrs.get(attr, attr)}:</b> {val}')
            if queue.attendants:
                text.append('')
                for att in queue.attendants:
                    att_str = f'{att.position}. {att.user.name} {att.user.surname}'
                    if att.user_id == int(context.user_data['id']):
                        att_str = f'<b>{att_str}</b>'
                    text.append(att_str)
            return (context.bot.send_message(
                context.user_data['id'], '\n'.join(text),
                parse_mode=ParseMode.HTML, reply_markup=markup), 'queue')

    @staticmethod
    @delete_last_message
    def register(update: Update, context: CallbackContext):
        try:
            queue_id = int(context.match.string)
        except ValueError:
            context.bot.send_message(context.user_data['id'], 'Потерялся ID очереди...')
            return menu(update, context)
        with create_session() as session:
            user = session.query(User).get(context.user_data['id'])
            if not user:
                return menu(update, context)
            queue = session.query(Queue).get(queue_id)
            if not queue:
                context.bot.send_message(context.user_data['id'], 'Очередь пропала...')
                return menu(update, context)
            if user in queue.attendants:
                context.bot.send_message(context.user_data['id'], 'Вы уже встали в эту очередь')
                return QueueView.show(update, context)
            att = Attendant(user_id=user.id, queue_id=queue.id, position=len(queue.attendants) + 1)
            session.add(att)
            session.commit()
            queue.attendants.append(att)
            session.add(queue)
            session.commit()
            context.bot.send_message(
                context.user_data['id'], f'Вы успешно встали в очередь <b>{queue.name}</b>',
                parse_mode=ParseMode.HTML)
            return QueueView.show(update, context)
