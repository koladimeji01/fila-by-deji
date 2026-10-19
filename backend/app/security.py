from datetime import datetime, timedelta, timezone
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError, VerificationError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from .config import get_settings
from .database import get_db
from .models import User

_hasher = PasswordHasher()
_dummy_hash = _hasher.hash('not-a-real-user-password')
_scheme = HTTPBearer(auto_error=False)
ISSUER = 'fila-by-deji'
AUDIENCE = 'fila-customers'


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, stored_hash: str | None) -> bool:
    try:
        return _hasher.verify(stored_hash or _dummy_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_token(user_id: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {'sub': user_id, 'iat': now, 'exp': now + timedelta(minutes=settings.access_token_minutes),
         'iss': ISSUER, 'aud': AUDIENCE, 'typ': 'access'},
        settings.jwt_secret_key,
        algorithm='HS256',
    )


def get_current_user(
    token: HTTPAuthorizationCredentials | None = Depends(_scheme),
    db: Session = Depends(get_db),
) -> User:
    if token is None or token.scheme.lower() != 'bearer':
        raise HTTPException(401, 'Authentication required', headers={'WWW-Authenticate': 'Bearer'})
    try:
        payload = jwt.decode(
            token.credentials,
            get_settings().jwt_secret_key,
            algorithms=['HS256'],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={'require': ['exp', 'iat', 'sub', 'iss', 'aud']},
        )
        if payload.get('typ') != 'access' or not isinstance(payload.get('sub'), str):
            raise jwt.InvalidTokenError()
    except jwt.PyJWTError:
        raise HTTPException(401, 'Invalid or expired token', headers={'WWW-Authenticate': 'Bearer'})
    user = db.get(User, payload['sub'])
    if user is None or not user.is_active:
        raise HTTPException(401, 'Invalid or expired token', headers={'WWW-Authenticate': 'Bearer'})
    return user
