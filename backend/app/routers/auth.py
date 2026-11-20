"""First-run setup, login (password / PIN), fast user switching, recovery."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import security
from ..db import get_db
from ..errors import ApiError
from ..models import User
from ..services import audit

router = APIRouter(tags=["auth"])


def user_out(u: User) -> dict:
    return {"id": u.id, "name": u.name, "username": u.username, "phone": u.phone, "role": u.role,
            "active": u.active, "can_receive_stock": u.can_receive_stock, "can_sell_credit": u.can_sell_credit,
            "has_pin": bool(u.pin_hash)}


def gen_code(prefix: str, a: int = 4, b: int = 2) -> str:
    al = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return f"{prefix}-" + "".join(secrets.choice(al) for _ in range(a)) + "-" + "".join(secrets.choice(al) for _ in range(b))


def gen_password() -> str:
    al = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(al) for _ in range(4)) + "-" + "".join(secrets.choice(al) for _ in range(2))


def next_username(db: Session, prefix: str) -> str:
    while True:
        name = f"{prefix}-{secrets.randbelow(9000) + 1000}"
        if not db.execute(select(User).where(User.username == name)).scalar_one_or_none():
            return name


class SetupIn(BaseModel):
    shop_name: str = Field(min_length=2, max_length=120)
    shop_phone: str | None = None
    shop_city: str | None = None
    owner_name: str = Field(min_length=2, max_length=120)
    owner_phone: str | None = None
    owner_password: str = Field(min_length=6, max_length=128)
    admin_password: str = Field(min_length=6, max_length=128)


@router.get("/setup/status")
def setup_status(db: Session = Depends(get_db)):
    has_owner = db.execute(select(func.count()).select_from(User).where(User.role == "OWNER")).scalar_one() > 0
    return {"initialized": has_owner, "shop_name": audit.get_setting(db, "shop_name") if has_owner else None,
            "shop_phone": audit.get_setting(db, "shop_phone"), "shop_city": audit.get_setting(db, "shop_city")}


@router.post("/setup")
def setup(body: SetupIn, db: Session = Depends(get_db)):
    if db.execute(select(func.count()).select_from(User).where(User.role == "OWNER")).scalar_one():
        raise ApiError(409, "ALREADY_INITIALIZED", "La boutique est déjà configurée.")
    if body.owner_password == body.admin_password:
        raise ApiError(422, "SAME_PASSWORD", "Le mot de passe administrateur doit être différent du mot de passe de connexion.")
    recovery = gen_code("PRO")
    owner = User(role="OWNER", name=body.owner_name.strip(), username=next_username(db, "PRO"),
                 phone=body.owner_phone, password_hash=security.hash_secret(body.owner_password),
                 recovery_hash=security.hash_secret(recovery), can_sell_credit=True)
    db.add(owner)
    audit.set_setting(db, "shop_name", body.shop_name.strip())
    audit.set_setting(db, "shop_phone", body.shop_phone or "")
    audit.set_setting(db, "shop_city", body.shop_city or "")
    audit.set_setting(db, "owner_admin_hash", security.hash_secret(body.admin_password))
    db.flush()
    audit.log(db, owner, "SHOP_SETUP", "shop", None, details={"shop": body.shop_name})
    token = security.create_session(db, owner)
    return {"token": token, "user": user_out(owner), "recovery_code": recovery}


class LoginIn(BaseModel):
    identifier: str
    password: str
    role: str | None = None  # "owner" | "worker" | "admin" (UI hint only; never trusted)


@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    ident = body.identifier.strip()
    key = f"login:{ident.lower()}"
    security.check_login_lock(db, key)
    user = db.execute(select(User).where(or_(func.lower(User.username) == ident.lower(),
                                             User.phone == ident, func.lower(User.phone) == ident.lower()))).scalars().first()
    if not user or not user.active or not security.verify_secret(user.password_hash, body.password):
        security.register_failure(db, key, None, "LOGIN_FAILED")
        raise ApiError(401, "BAD_CREDENTIALS", "Identifiant ou mot de passe incorrect.")
    if body.role:
        want = {"owner": "OWNER", "worker": "WORKER", "admin": "DDS_ADMIN"}.get(body.role.lower())
        if want and want != user.role:
            raise ApiError(401, "BAD_CREDENTIALS", "Identifiant ou mot de passe incorrect.")
    security.reset_failures(db, key)
    return {"token": security.create_session(db, user), "user": user_out(user)}


class PinIn(BaseModel):
    user_id: int
    pin: str = Field(min_length=4, max_length=8)


@router.get("/auth/switch-list")
def switch_list(db: Session = Depends(get_db)):
    """Names only (no secrets) so the shared laptop can show a 'who is selling?' picker."""
    rows = db.execute(select(User).where(User.active == True, User.role.in_(("OWNER", "WORKER")))  # noqa: E712
                      .order_by(User.role.desc(), User.name)).scalars()
    return [{"id": u.id, "name": u.name, "username": u.username, "role": u.role, "has_pin": bool(u.pin_hash)} for u in rows]


@router.post("/auth/pin-login")
def pin_login(body: PinIn, db: Session = Depends(get_db)):
    key = f"pin:{body.user_id}"
    security.check_login_lock(db, key)
    user = db.get(User, body.user_id)
    if not user or not user.active or user.role == "DDS_ADMIN" or not security.verify_secret(user.pin_hash, body.pin):
        security.register_failure(db, key, None, "PIN_FAILED")
        raise ApiError(401, "BAD_CREDENTIALS", "Code PIN incorrect.")
    security.reset_failures(db, key)
    return {"token": security.create_session(db, user), "user": user_out(user)}


@router.post("/auth/logout")
def logout(authorization: str | None = Header(default=None), db: Session = Depends(get_db),
           user: User = Depends(security.current_user)):
    if authorization and authorization.lower().startswith("bearer "):
        security.destroy_session(db, authorization[7:].strip())
    return {"ok": True}


@router.get("/auth/me")
def me(user: User = Depends(security.current_user)):
    return user_out(user)


class PinSet(BaseModel):
    pin: str = Field(min_length=4, max_length=8, pattern=r"^\d+$")


@router.post("/auth/pin")
def set_pin(body: PinSet, db: Session = Depends(get_db), user: User = Depends(security.current_user)):
    user.pin_hash = security.hash_secret(body.pin)
    return {"ok": True}


class ChangePw(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=128)


@router.post("/auth/change-password")
def change_password(body: ChangePw, db: Session = Depends(get_db), user: User = Depends(security.current_user)):
    if not security.verify_secret(user.password_hash, body.current_password):
        raise ApiError(403, "BAD_CREDENTIALS", "Mot de passe actuel incorrect.")
    user.password_hash = security.hash_secret(body.new_password)
    audit.log(db, user, "PASSWORD_CHANGED", "user", user.id)
    return {"ok": True}


class RecoverIn(BaseModel):
    identifier: str
    recovery_code: str
    new_password: str = Field(min_length=6, max_length=128)


@router.post("/auth/recover")
def recover(body: RecoverIn, db: Session = Depends(get_db)):
    ident = body.identifier.strip().lower()
    key = f"recover:{ident}"
    security.check_login_lock(db, key)
    user = db.execute(select(User).where(or_(func.lower(User.username) == ident, func.lower(User.phone) == ident))).scalars().first()
    if not user or not user.active or not security.verify_secret(user.recovery_hash, body.recovery_code.strip().upper()):
        security.register_failure(db, key, None, "RECOVERY_FAILED")
        raise ApiError(403, "BAD_RECOVERY", "Code de récupération incorrect.")
    security.reset_failures(db, key)
    user.password_hash = security.hash_secret(body.new_password)
    audit.log(db, user, "PASSWORD_RECOVERED", "user", user.id)
    return {"ok": True}
