from passlib.context import CryptContext
from datetime import datetime, timedelta
import uuid
from models import UserSession
from pytz import timezone

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
    chongqing_tz = timezone("Asia/Chongqing")
    current_time = datetime.now(chongqing_tz)
    # Localize the naive created_at to Chongqing timezone
    created_at_aware = chongqing_tz.localize(db_session.created_at)
    if current_time > created_at_aware + timedelta(minutes=30):
        db.delete(db_session)
        db.commit()
        print("Session Expired")
        return None
    return db_session.user_id