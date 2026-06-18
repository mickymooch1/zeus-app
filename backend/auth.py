"""
auth.py — JWT + bcrypt authentication for Zeus SaaS platform.
Uses PyJWT and passlib[bcrypt].
"""
import logging
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header, HTTPException, Query
from passlib.context import CryptContext

from db import get_db_path, get_db_path_dep, get_user_by_id

log = logging.getLogger("zeus.auth")

SECRET_KEY = os.environ.get("JWT_SECRET", "")
if not SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET environment variable is not set. "
        "Generate a stable secret and add it to Railway: "
        "python -c \"import secrets; print(secrets.token_hex(32))\". "
        "Never change it once users have active sessions."
    )
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 365

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
    # Peek at the exp claim without verifying the signature, so we can log
    # useful diagnostics regardless of why verification later fails.
    try:
        unverified = jwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": False},
            algorithms=[ALGORITHM],
        )
        exp = unverified.get("exp")
        sub = unverified.get("sub", "?")
        now_ts = datetime.now(timezone.utc).timestamp()
        if exp is not None:
            delta_days = (exp - now_ts) / 86400
            log.info("JWT verify: sub=%s exp_in_days=%.1f (exp=%s now=%s)", sub, delta_days, exp, now_ts)
        else:
            log.warning("JWT verify: sub=%s — no exp claim in token", sub)
    except Exception as peek_err:
        log.warning("JWT verify: could not peek at token claims: %s", peek_err)

    try:
        # 30-second leeway guards against minor clock drift between issuer and verifier
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], leeway=timedelta(seconds=30))
        return payload
    except jwt.ExpiredSignatureError as exc:
        log.warning("JWT EXPIRED: %s", exc)
        return None
    except jwt.InvalidTokenError as exc:
        log.warning("JWT INVALID: %s", exc)
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


async def get_optional_user(
    token: str = Query(None),
    authorization: str = Header(None),
    db_path=Depends(get_db_path_dep),
) -> dict | None:
    """Like get_current_user but returns None instead of raising 401."""
    raw_token: str | None = None
    if token:
        raw_token = token
    elif authorization and authorization.lower().startswith("bearer "):
        raw_token = authorization[7:].strip()
    if not raw_token:
        return None
    payload = verify_token(raw_token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return get_user_by_id(db_path, user_id)
