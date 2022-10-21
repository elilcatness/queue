from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relation

from src.db.db_session import SQLAlchemyBase


class Queue(SQLAlchemyBase):
    __tablename__ = 'queues'

    verbose_attrs = {'name': 'Название', 'start_dt': 'Дата открытия', 'end_dt': 'Дата закрытия',
                     'status': 'Статус'}

    id = Column(Integer, primary_key=True, autoincrement=True, unique=True)
    name = Column(String)
    start_dt = Column(DateTime)
    end_dt = Column(DateTime)
    notify_dt = Column(DateTime)
    status = Column(String, default='planned')
    attendants = relation('Attendant')
