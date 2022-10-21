import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode

from src.constants import MENU_STATUS_VERBOSES
from src.db.db_session import create_session
from src.db.models.queue import Queue
from src.db.models.user import User
from src.utils import delete_last_message


@delete_last_message
def ask_name(_, context):
    context.user_data['reg_data'] = dict()
    markup = InlineKeyboardMarkup([[InlineKeyboardButton('Вернуться назад', callback_data='back')]])
    return (context.bot.send_message(
        context.user_data['id'], 'Введите своё имя', reply_markup=markup), 'ask_name')


@delete_last_message
def ask_surname(update, context):
    if (not context.user_data['reg_data'].get('name')
            or not hasattr(context.match, 'string') or context.match.string != 'back'):
        name = update.message.text
        if not name:
            context.bot.send_message(context.user_data['id'], 'Не было введено имя')
            return ask_name(update, context)
        context.user_data['reg_data']['name'] = name
    markup = InlineKeyboardMarkup([[InlineKeyboardButton('Вернуться назад', callback_data='back')]])
    return (context.bot.send_message(
        context.user_data['id'], 'Введите свою фамилию', reply_markup=markup), 'ask_surname')


@delete_last_message
def finish_registration(update, context):
    surname = update.message.text
    if not surname:
        context.bot.send_message(context.user_data['id'], 'Не была введена фамилия')
        return ask_surname(update, context)
    context.user_data['reg_data']['surname'] = surname
    with create_session() as session:
        name, surname = context.user_data['reg_data']['name'], context.user_data['reg_data']['surname']
        if session.query(User).filter(
                (User.name == context.user_data['reg_data']['name']) &
                (User.surname == context.user_data['reg_data']['surname'])).first():
            context.bot.send_message(context.user_data['id'],
                                     f'Пользователь {name} {surname} уже есть в базе')
            return ask_name(update, context)
        user = User(id=context.user_data['id'], name=name, surname=surname,
                    is_admin=str(context.user_data['id']) == os.getenv('super_admin_id', ''))
        session.add(user)
        session.commit()
    context.bot.send_message(context.user_data['id'], 'Регистрация была успешно завершена')
    return menu(update, context)


@delete_last_message
def menu(update, context):
    if update.message is not None:
        user_id = update.message.from_user.id
        context.user_data['id'] = user_id
    elif context.user_data.get('id') is not None:
        user_id = context.user_data['id']
    else:
        return 'menu'
    with create_session() as session:
        user = session.query(User).get(user_id)
        if not user:
            context.bot.send_message(context.user_data['id'],
                                     'Здравствуйте, это бот очередей группы 4231 ГУАП.\n'
                                     'Пройдите, пожалуйста, регистрацию')
            return ask_name(update, context)
        buttons = []
        for status in ('active', 'planned', 'archived'):
            if session.query(Queue).filter(Queue.status == status).first():
                buttons.append([InlineKeyboardButton(f'{MENU_STATUS_VERBOSES[status]} очереди',
                                                     callback_data=status)])
        if user.is_admin:
            buttons.append([InlineKeyboardButton('Добавить очередь', callback_data='add_queue')])
        markup, submsg = ((InlineKeyboardMarkup(buttons),
                           '\n\nНикаких очередей пока нет') if buttons else
                          (None, '\n\nНикаких очередей пока нет'))
        markup = InlineKeyboardMarkup(buttons) if buttons else None
    return context.bot.send_message(
        context.user_data['id'], f'<b>Пользователь:</b> {user.name} {user.surname}{submsg}',
        reply_markup=markup, parse_mode=ParseMode.HTML), 'menu'
