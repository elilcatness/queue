from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relation

from src.db.db_session import SQLAlchemyBase


class User(SQLAlchemyBase):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, unique=True)
    name = Column(String)
    surname = Column(String)
    attendants = relation('Attendant')
