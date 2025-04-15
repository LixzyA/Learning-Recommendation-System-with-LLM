from passlib.context import CryptContext
from datetime import datetime, timedelta
import uuid
from models import UserSession

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_session_token():
    return str(uuid.uuid4())

def validate_session(db, token):
    db_session = db.query(UserSession).filter(UserSession.token == token).first()
    if not db_session:
        return None
    if datetime.now() > db_session.created_at + timedelta(minutes=30):
        db.delete(db_session)
        db.commit()
        return None
    return db_session.user_id