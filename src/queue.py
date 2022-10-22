from datetime import datetime, timedelta

from sqlalchemy import func
from telegram import Update, ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext

from src.constants import STATUS_VERBOSES, PAGINATION_STEP, VIEW_STATUS_VERBOSES, MIN_DELTA, MIN_DUR
from src.db.db_session import create_session
from src.db.models.attendant import Attendant
from src.db.models.queue import Queue
from src.db.models.user import User
from src.menu import menu
from src.utils import build_pagination, delete_last_message, parse_dt


def notify_queue(context: CallbackContext):
    try:
        queue_id = int(context.job.name)
    except ValueError:
        return print(f'[notify_queue] Something went wrong on {context.job.name=}')
    with create_session() as session:
        q = session.query(Queue).get(queue_id)
        if not q:
            return print(f'[notify_queue] No queue with id = {queue_id}')
        if q.notification_sent:
            return print(f'[notify_queue] Notification has already been sent')
        for user in session.query(User).all():
            context.bot.send_message(
                user.id, f'Очередь <b>{q.name}</b> откроется в '
                         f'<b>{q.start_dt.strftime("%d.%m.%Y %H:%M")}</b>',
                parse_mode=ParseMode.HTML)
        q.notification_sent = True
        session.add(q)
        session.commit()


def open_queue(context: CallbackContext):
    try:
        queue_id = int(context.job.name)
    except ValueError:
        return print(f'[open_queue] Something went wrong on {context.job.name=}')
    with create_session() as session:
        q = session.query(Queue).get(queue_id)
        if not q:
            return print(f'[open_queue] No queue with id = {queue_id}')
        if q.status != 'planned':
            return print(f'[open_queue] {q.status=} on {context.job.name=}')
        q.status = 'active'
        session.add(q)
        session.commit()
        text = []
        for attr in Queue.verbose_attrs:
            val = getattr(q, attr)
            if 'dt' in attr:
                val = val.strftime('%d.%m.%Y %H:%M:%S')
            if attr == 'status':
                val = VIEW_STATUS_VERBOSES.get(val, val)
            text.append(f'<b>{Queue.verbose_attrs.get(attr, attr)}:</b> {val}')
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton('Встать в очередь', callback_data=f'reg {q.id}')]])
        for user in session.query(User).all():
            context.bot.send_message(
                user.id,
                f'<b>Открылась новая очередь!</b>\n\n' + '\n'.join(text),
                reply_markup=markup, parse_mode=ParseMode.HTML)


def close_queue(context: CallbackContext):
    try:
        queue_id = int(context.job.name)
    except ValueError:
        return print(f'[close_queue] Something went wrong on {context.job.name=}')
    with create_session() as session:
        q = session.query(Queue).get(queue_id)
        if not q:
            return print(f'[close_queue] No queue with id = {queue_id}')
        if q.status != 'active':
            return print(f'[close_queue] {q.status=} on {context.job.name=}')
        for user in session.query(User).all():
            context.bot.send_message(user.id, f'Очередь <b>{q.name}</b> была закрыта',
                                     parse_mode=ParseMode.HTML)
        q.status = 'archived'
        session.add(q)
        session.commit()


class QueueView:
    @staticmethod
    @delete_last_message
    def show_all(update: Update, context: CallbackContext):
        status = context.match.string
        if not status:
            context.bot.send_message(context.user_data['id'], 'Эээээ.... штота не так с кнопками')
            return menu(update, context)
        if status not in ('planned', 'active', 'archived'):
            status = context.user_data.get('last_queue_status')
        with create_session() as session:
            queues = [(f'{q.name} [{q.start_dt.strftime("%d.%m.%Y %H:%M")} – '
                       f'{q.end_dt.strftime("%d.%m.%Y %H:%M")}]', q.id)
                      for q in session.query(Queue).filter(Queue.status == status).all()]
            if not queues:
                context.bot.send_message(context.user_data['id'],
                                         f'Очередей со статусом {status} пока нет!')
                return menu(update, context)
            context.user_data['last_queue_status'] = status
            if not context.user_data.get('pagination'):
                context.user_data['pagination'] = 1
            markup, pages_count = build_pagination(
                queues, PAGINATION_STEP, context.user_data['pagination'])
            context.user_data['pages_count'] = pages_count
            return (context.bot.send_message(
                context.user_data['id'],
                f'Найдено <b>{len(queues)} {STATUS_VERBOSES.get(status, "")}</b> очередей'
                '\n\n<i>Для выбора страницы в пагинации также можно отправить её номер</i>',
                reply_markup=markup, parse_mode=ParseMode.HTML),
                    'queues')

    @staticmethod
    @delete_last_message
    def show(update: Update, context: CallbackContext):
        try:
            queue_id = int(context.match.string)
        except ValueError:
            try:
                queue_id = int(context.match.string.split()[-1].strip())
            except ValueError:
                context.bot.send_message(context.user_data['id'], 'Что-то не так с переходом')
                return menu(update, context)
        with create_session() as session:
            queue = session.query(Queue).get(queue_id)
            if not queue:
                context.bot.send_message(context.user_data['id'], 'Данной очереди не существует')
                return menu(update, context)
            buttons = [[InlineKeyboardButton('Обновить'), callback_data=f'refresh {queue.id}',
                        InlineKeyboardButton('Вернуться назад', callback_data='back')]]
            if (context.user_data['id'] not in [att.user_id for att in queue.attendants]
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
            try:
                queue_id = int(context.match.string.split()[-1].strip())
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
            if queue.status != 'active':
                context.bot.send_message(context.user_data['id'], 'Очередь ещё не открыта')
                return QueueView.show(update, context)
            if user.id in [att.user_id for att in queue.attendants]:
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

    @staticmethod
    def set_next_page(_, context):
        context.user_data['pagination'] += 1
        return QueueView.show_all(_, context)

    @staticmethod
    def set_previous_page(_, context):
        context.user_data['pagination'] -= 1
        return QueueView.show_all(_, context)

    @staticmethod
    def set_page(update, context):
        n = int(update.message.text)
        if not (1 <= n <= context.user_data['pages_count']):
            update.message.reply_text('Введён неверный номер страницы')
        else:
            context.user_data['pagination'] = n
        return QueueView.show_all(update, context)


class QueueAdd:
    @staticmethod
    @delete_last_message
    def ask_name(_, context: CallbackContext):
        context.user_data['q_add_data'] = dict()
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('Вернуться назад', callback_data='back')]])
        return (context.bot.send_message(context.user_data['id'], 'Введите название очереди',
                                         reply_markup=markup), 'QueueAdd.ask_name')

    @staticmethod
    @delete_last_message
    def ask_start_dt(update: Update, context: CallbackContext):
        # if (context.user_data['q_add_data'].get('name') and
        #         (not hasattr(context.match, 'string') or context.match.string != 'back')
        #         or not context.user_data['q_add_data'].get('name')):
        if not context.user_data['q_add_data'].get('name'):
            name = update.message.text
            with create_session() as session:
                if session.query(Queue).filter(func.lower(Queue.name) == func.lower(name)).first():
                    context.bot.send_message(context.user_data['id'],
                                             f'Очередь с названием <b>{name}</b> уже существует',
                                             parse_mode=ParseMode.HTML)
                    return QueueAdd.ask_name(update, context)
            context.user_data['q_add_data']['name'] = name
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('Вернуться назад', callback_data='back')]])
        return (context.bot.send_message(
            context.user_data['id'], 'Введите дату и время открытия очереди\n'
                                     'Формат: ДД.ММ.ГГГГ чч:мм:сс',
            reply_markup=markup),
                'QueueAdd.ask_start_dt')

    @staticmethod
    @delete_last_message
    def ask_end_dt(update: Update, context: CallbackContext):
        if not context.user_data['q_add_data'].get('start_dt'):
            start_dt = parse_dt(update.message.text)
            if isinstance(start_dt, str):
                context.bot.send_message(context.user_data['id'], start_dt)
                return QueueAdd.ask_start_dt(update, context)
            dt_now = datetime.utcnow() + timedelta(hours=3)
            if start_dt < dt_now:
                context.bot.send_message(context.user_data['id'], 'Не живите прошлым!')
                return QueueAdd.ask_start_dt(update, context)
            context.user_data['q_add_data']['start_dt'] = start_dt.isoformat()
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('Вернуться назад', callback_data='back')]])
        return (context.bot.send_message(
            context.user_data['id'], 'Введите дату и время закрытия очереди\n'
                                     'Формат: ДД.ММ.ГГГГ чч:мм:сс',
            reply_markup=markup),
                'QueueAdd.ask_end_dt')

    @staticmethod
    @delete_last_message
    def ask_notify_dt(update: Update, context: CallbackContext):
        if not context.user_data['q_add_data'].get('end_dt'):
            end_dt = parse_dt(update.message.text)
            if isinstance(end_dt, str):
                context.bot.send_message(context.user_data['id'], end_dt)
                return QueueAdd.ask_end_dt(update, context)
            start_dt = datetime.fromisoformat(context.user_data['q_add_data']['start_dt'])
            if (end_dt - start_dt).total_seconds() < MIN_DUR:
                context.bot.send_message(
                    context.user_data['id'],
                    f'Очередь должна быть открыта хотя бы {MIN_DUR} секунд')
                return QueueAdd.ask_end_dt(update, context)
            context.user_data['q_add_data']['end_dt'] = end_dt.isoformat()
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('Вернуться назад', callback_data='back')]])
        return (context.bot.send_message(
            context.user_data['id'],
            'Введите дату и время оповещения о предстоящем открытии очереди\n'
            'Формат: ДД.ММ.ГГГГ чч:мм:сс', reply_markup=markup), 'QueueAdd.ask_notify_dt')

    @staticmethod
    @delete_last_message
    def finish(update: Update, context: CallbackContext):
        notify_dt = parse_dt(update.message.text)
        if isinstance(notify_dt, str):
            context.bot.send_message(context.user_data['id'], notify_dt)
            return QueueAdd.ask_notify_dt(update, context)
        if notify_dt < datetime.utcnow() + timedelta(hours=3):
            context.bot.send_message(context.user_data['id'], 'Не живите прошлым!')
            return QueueAdd.ask_notify_dt(update, context)
        start_dt = datetime.fromisoformat(context.user_data['q_add_data']['start_dt'])
        if (start_dt - notify_dt).total_seconds() <= MIN_DELTA:
            context.bot.send_message(
                context.user_data['id'],
                f'Оповещение должно быть отправлено не позднее, '
                f'чем за {MIN_DELTA} секунд до открытия очереди')
            return QueueAdd.ask_notify_dt(update, context)
        end_dt = datetime.fromisoformat(context.user_data['q_add_data']['end_dt'])
        with create_session() as session:
            q = Queue(name=context.user_data['q_add_data']['name'],
                      start_dt=start_dt,
                      end_dt=end_dt,
                      notify_dt=notify_dt)
            session.add(q)
            session.commit()
            context.bot.send_message(
                context.user_data['id'], f'Очередь <b>{q.name}</b> была успешно добавлена',
                parse_mode=ParseMode.HTML)
            context.job_queue.run_once(
                notify_queue, (notify_dt - datetime.utcnow() - timedelta(hours=3)).total_seconds(),
                context=context, name=str(q.id))
            context.job_queue.run_once(
                open_queue, (start_dt - datetime.utcnow() - timedelta(hours=3)).total_seconds(),
                context=context, name=str(q.id))
            context.job_queue.run_once(
                close_queue, (end_dt - datetime.utcnow() - timedelta(hours=3)).total_seconds(),
                context=context, name=str(q.id))
        context.user_data.pop('q_add_data')
        return menu(update, context)
