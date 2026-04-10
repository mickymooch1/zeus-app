"""
auth.py — JWT + bcrypt authentication for Zeus SaaS platform.
Uses PyJWT and passlib[bcrypt].
"""
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header, HTTPException, Query
from passlib.context import CryptContext

from db import get_db_path, get_db_path_dep, get_user_by_id

SECRET_KEY = os.environ.get("JWT_SECRET", "zeus-dev-secret-CHANGE-IN-PROD-NOW")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Return bcrypt hash of plain-text password."""
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches bcrypt hash."""
    return _pwd_context.verify(plain, hashed)


def create_token(user_id: str, email: str, is_admin: bool = False) -> str:
    """Create a signed JWT valid for TOKEN_EXPIRE_DAYS days."""
    expire = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "email": email,
        "is_admin": is_admin,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict | None:
    """Decode and verify a JWT. Returns payload dict or None on failure."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def get_current_user(
    token: str = Query(None),
    authorization: str = Header(None),
    db_path=Depends(get_db_path_dep),
) -> dict:
    """
    FastAPI dependency: checks ?token=... query param OR Authorization header.
    Returns user dict. Raises HTTP 401 if token is invalid/missing.
    """
    raw_token: str | None = None

    if token:
        raw_token = token
    elif authorization and authorization.lower().startswith("bearer "):
        raw_token = authorization[7:].strip()

    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication required")

    payload = verify_token(raw_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = get_user_by_id(db_path, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user
