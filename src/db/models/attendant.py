from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relation

from src.db.db_session import SQLAlchemyBase


class Attendant(SQLAlchemyBase):
    __tablename__ = 'attendants'

    id = Column(Integer, primary_key=True, autoincrement=True, unique=True)
    user_id = Column(String, ForeignKey('users.id'))
    user = relation('User', foreign_keys=user_id)
    queue_id = Column(Integer, ForeignKey('queues.id'))
    queue = relation('Queue', foreign_keys=queue_id)
    position = Column(Integer)
