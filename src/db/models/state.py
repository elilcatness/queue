from sqlalchemy import Column, Integer, String

from src.db.db_session import SQLAlchemyBase


class State(SQLAlchemyBase):
    __tablename__ = 'states'

    user_id = Column(String, primary_key=True, unique=True)
    callback = Column(String)
    data = Column(String, nullable=True)