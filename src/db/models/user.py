from sqlalchemy import Column, String, Boolean
from sqlalchemy.orm import relation

from src.db.db_session import SQLAlchemyBase


class User(SQLAlchemyBase):
    __tablename__ = 'users'

    id = Column(String, primary_key=True, unique=True)
    name = Column(String)
    surname = Column(String)
    is_admin = Column(Boolean, default=False)
    attendants = relation('Attendant')
