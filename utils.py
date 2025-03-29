from sqlalchemy.orm import Session
from models import User
import uuid
from datetime import datetime, timedelta

def create_session(db: Session, user: User):
    session_token = str(uuid.uuid4())
    user.session_token = session_token
    user.session_expiry = datetime.utcnow() + timedelta(minutes=30)  # 30-minute expiration
    db.commit()
    return session_token

def get_user_by_session_token(db: Session, session_token: str):
    if not session_token:
        return None
    user = db.query(User).filter(User.session_token == session_token).first()
    if user and user.session_expiry < datetime.utcnow():
        # Session expired, clean up
        delete_session(db, user)
        return None
    return user

def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def create_user(db: Session, username: str, password: str):
    db_user = User(username=username, password=password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# Keep existing functions and add:
def delete_session(db: Session, user: User):
    user.session_token = None
    user.session_expiry = None  # Add this line
    db.commit()

def cleanup_expired_sessions(db: Session):
    expired_users = db.query(User).filter(User.session_expiry < datetime.utcnow())
    for user in expired_users:
        user.session_token = None
        user.session_expiry = None
    db.commit()