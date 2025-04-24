from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
from pytz import timezone

SQLALCHEMY_DATABASE_URL = "sqlite:///./recommendation.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)

class UserSession(Base):
    __tablename__ = "sessions"
    token = Column(String, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now(timezone("Asia/Chongqing")))

class Preference(Base):
    __tablename__ = "preferences"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    file_type = Column(String, default="pdf")
    language = Column(String, default="en")

Base.metadata.create_all(bind=engine)
