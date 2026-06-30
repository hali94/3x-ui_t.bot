from datetime import datetime, timedelta, timezone
from typing import Any
from jose import JWTError, jwt
from fastapi import HTTPException, status
from app.config import settings


def create_access_token(subject: int | str, extra: dict[str, Any] | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(subject), "exp": expire, "type": "access"}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: int | str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(subject), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="توکن نامعتبر است",
            headers={"WWW-Authenticate": "Bearer"},
        )


def verify_access_token(token: str) -> dict[str, Any]:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="نوع توکن نامعتبر است")
    return payload
