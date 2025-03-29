from sqlalchemy import Column, Integer, String, DateTime
# from datetime import datetime, timedelta
from sqlite_db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    session_token = Column(String, nullable=True)
    session_expiry = Column(DateTime, nullable=True)  # Add this line