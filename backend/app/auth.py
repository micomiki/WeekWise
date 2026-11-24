import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from .database import get_db
from .models import User

SECRET = os.getenv('JWT_SECRET')
if not SECRET:
    # Dev-only key saved outside Git so tokens survive local restarts.
    from pathlib import Path
    key_file = Path(__file__).resolve().parents[2] / '.weekwise-dev-secret'
    if key_file.exists():
        SECRET = key_file.read_text().strip()
    else:
        SECRET = secrets.token_urlsafe(48)
        key_file.write_text(SECRET)
        try: key_file.chmod(0o600)
        except OSError: pass

bearer = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return base64.b64encode(salt).decode() + '$' + base64.b64encode(digest).decode()

def check_password(password: str, stored: str) -> bool:
    try:
        a,b = stored.split('$',1)
        salt = base64.b64decode(a)
        expected = base64.b64decode(b)
        actual = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(expected,actual)
    except (ValueError, TypeError):
        return False

def create_token(user_id: int) -> str:
    return jwt.encode({'sub': str(user_id), 'exp': datetime.now(timezone.utc)+timedelta(hours=12)},SECRET,algorithm='HS256')

def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not credentials:
        raise HTTPException(401,'Authentication required')
    try:
        payload = jwt.decode(credentials.credentials,SECRET, algorithms=['HS256'])
        uid = int(payload['sub'])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401,'Invalid or expired session')
    user = db.get(User,uid)
    if user is None:
        raise HTTPException(401,'Account not found')
    return user
