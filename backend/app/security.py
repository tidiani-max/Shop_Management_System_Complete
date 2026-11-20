"""Argon2id hashing, opaque session tokens, role guards and the separate
Owner Admin Password check (always verified server-side)."""
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config
from .db import get_db
from .errors import ApiError
from .models import AuthSession, LockoutCounter, User, utcnow
from .services import audit

_ph = PasswordHasher()  # Argon2id by default

OWNER, WORKER, DDS = "OWNER", "WORKER", "DDS_ADMIN"


def hash_secret(value: str) -> str:
    return _ph.hash(value)


def verify_secret(hashed: str | None, value: str) -> bool:
    if not hashed or value is None:
        return False
    try:
        return _ph.verify(hashed, value)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def _tok_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            token_hash=_tok_hash(token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(hours=config.SESSION_HOURS),
        )
    )
    db.flush()
    return token


def destroy_session(db: Session, token: str) -> None:
    s = db.execute(select(AuthSession).where(AuthSession.token_hash == _tok_hash(token))).scalar_one_or_none()
    if s:
        db.delete(s)
        db.flush()


def _bearer(authorization: str | None, access_token: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return access_token


def current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    token = _bearer(authorization, None)
    if not token:
        raise ApiError(401, "UNAUTHENTICATED", "Connexion requise.")
    s = db.execute(select(AuthSession).where(AuthSession.token_hash == _tok_hash(token))).scalar_one_or_none()
    if not s or s.expires_at < utcnow():
        raise ApiError(401, "SESSION_EXPIRED", "Session expirée. Reconnectez-vous.")
    user = db.get(User, s.user_id)
    if not user or not user.active:
        raise ApiError(401, "UNAUTHENTICATED", "Compte désactivé.")
    return user


def current_user_or_query(
    authorization: str | None = Header(default=None),
    access_token: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Used only by printable HTML views opened in a new window."""
    token = _bearer(authorization, access_token)
    return current_user(f"Bearer {token}" if token else None, db)


def require_roles(*roles: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            if user.role == WORKER:
                raise ApiError(403, "WORKER_FORBIDDEN", "Action réservée au propriétaire.")
            raise ApiError(403, "FORBIDDEN", "Accès refusé pour ce rôle.")
        return user

    return dep


def _lock_check(db: Session, key: str) -> LockoutCounter:
    row = db.get(LockoutCounter, key)
    if row is None:
        row = LockoutCounter(key=key, fails=0)
        db.add(row)
        db.flush()
    if row.locked_until and row.locked_until > utcnow():
        raise ApiError(429, "LOCKED", "Trop de tentatives. Réessayez dans quelques minutes.")
    return row


def register_failure(db: Session, key: str, actor: User | None, what: str) -> None:
    row = _lock_check_no_raise(db, key)
    row.fails += 1
    if row.fails >= config.ADMIN_MAX_FAILS:
        row.locked_until = utcnow() + timedelta(minutes=config.ADMIN_LOCK_MINUTES)
        row.fails = 0
    audit.log(db, actor, what, entity="security", details={"key": key})
    db.commit()  # persist the failure even though the request is about to error out


def _lock_check_no_raise(db: Session, key: str) -> LockoutCounter:
    row = db.get(LockoutCounter, key)
    if row is None:
        row = LockoutCounter(key=key, fails=0)
        db.add(row)
        db.flush()
    return row


def reset_failures(db: Session, key: str) -> None:
    row = db.get(LockoutCounter, key)
    if row and (row.fails or row.locked_until):
        row.fails, row.locked_until = 0, None
        db.flush()


def check_login_lock(db: Session, key: str) -> None:
    _lock_check(db, key)


def verify_admin_password(db: Session, actor: User | None, password: str | None) -> None:
    """Server-side check of the separate Owner Admin Password.
    Call BEFORE making any other write in the request."""
    if not password:
        raise ApiError(403, "ADMIN_PASSWORD_REQUIRED", "Mot de passe administrateur requis.")
    _lock_check(db, "admin_pw")
    stored = audit.get_setting(db, "owner_admin_hash", "")
    if not verify_secret(stored, password):
        register_failure(db, "admin_pw", actor, "ADMIN_PW_FAILED")
        raise ApiError(403, "ADMIN_PASSWORD_INVALID", "Mot de passe administrateur incorrect.")
    reset_failures(db, "admin_pw")
