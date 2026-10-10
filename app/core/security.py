import secrets
import hashlib
import hmac

import bcrypt
import jwt
from datetime import datetime,timedelta,timezone
from app.core.config import settings

def hash_password(password:str) -> str:
    return bcrypt.hashpw(password.encode(),bcrypt.gensalt()).decode()

def verify_password(plain_password:str,hashed_password:str) -> bool:
    return bcrypt.checkpw(plain_password.encode(),hashed_password.encode())

def create_access_token(data:dict,expire_time:timedelta|None=None) ->str:
    to_encode=data.copy()
    expire=datetime.now(timezone.utc)+(expire_time or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp":expire})
    return jwt.encode(to_encode,settings.SECRET_KEY,algorithm=settings.ALGORITHM)

def decode_access_token(token:str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY,algorithms=[settings.ALGORITHM])

def generate_invite_token() -> str:
    return secrets.token_urlsafe(32)

def generate_password_reset_token() -> str:
    return secrets.token_urlsafe(32)

def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def hash_account_deletion_code(code: str, user_id: int) -> str:
    message = f"account-deletion:{user_id}:{code}".encode("utf-8")
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), message, hashlib.sha256).hexdigest()