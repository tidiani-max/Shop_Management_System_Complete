"""Worker management (owner only) + owner admin-password management."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import security
from ..db import get_db
from ..errors import ApiError
from ..models import User
from ..services import audit
from .auth import gen_code, gen_password, next_username, user_out

router = APIRouter(tags=["users"])
owner_only = security.require_roles(security.OWNER)


class WorkerIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str | None = None
    can_sell_credit: bool = False
    can_receive_stock: bool = True


class WorkerPatch(BaseModel):
    name: str | None = None
    phone: str | None = None
    active: bool | None = None
    can_sell_credit: bool | None = None
    can_receive_stock: bool | None = None


@router.get("/workers")
def list_workers(db: Session = Depends(get_db), user: User = Depends(owner_only)):
    return [user_out(u) for u in db.execute(select(User).where(User.role == "WORKER").order_by(User.id)).scalars()]


@router.post("/workers")
def create_worker(body: WorkerIn, db: Session = Depends(get_db), user: User = Depends(owner_only)):
    pw, rec = gen_password(), gen_code("WK")
    w = User(role="WORKER", name=body.name.strip(), username=next_username(db, "EMP"), phone=body.phone,
             password_hash=security.hash_secret(pw), recovery_hash=security.hash_secret(rec),
             can_sell_credit=body.can_sell_credit, can_receive_stock=body.can_receive_stock)
    db.add(w)
    db.flush()
    audit.log(db, user, "WORKER_CREATED", "user", w.id, details={"username": w.username})
    # credentials are returned ONCE; only hashes are stored
    return {**user_out(w), "password": pw, "recovery_code": rec}


@router.patch("/workers/{wid}")
def patch_worker(wid: int, body: WorkerPatch, db: Session = Depends(get_db), user: User = Depends(owner_only)):
    w = db.get(User, wid)
    if not w or w.role != "WORKER":
        raise ApiError(404, "NOT_FOUND", "Employé introuvable.")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(w, k, v)
    audit.log(db, user, "WORKER_UPDATED", "user", w.id, details=body.model_dump(exclude_none=True))
    return user_out(w)


@router.post("/workers/{wid}/reset-password")
def reset_worker_password(wid: int, db: Session = Depends(get_db), user: User = Depends(owner_only)):
    w = db.get(User, wid)
    if not w or w.role != "WORKER":
        raise ApiError(404, "NOT_FOUND", "Employé introuvable.")
    pw, rec = gen_password(), gen_code("WK")
    w.password_hash, w.recovery_hash, w.pin_hash = security.hash_secret(pw), security.hash_secret(rec), None
    audit.log(db, user, "WORKER_PASSWORD_RESET", "user", w.id)
    return {"username": w.username, "password": pw, "recovery_code": rec}


class AdminPwChange(BaseModel):
    new_admin_password: str = Field(min_length=6, max_length=128)
    current_admin_password: str | None = None
    recovery_code: str | None = None


@router.post("/owner/admin-password")
def change_admin_password(body: AdminPwChange, db: Session = Depends(get_db), user: User = Depends(owner_only)):
    if body.current_admin_password:
        security.verify_admin_password(db, user, body.current_admin_password)
    elif body.recovery_code and security.verify_secret(user.recovery_hash, body.recovery_code.strip().upper()):
        pass
    else:
        raise ApiError(403, "ADMIN_PASSWORD_REQUIRED", "Mot de passe administrateur actuel ou code de récupération requis.")
    if security.verify_secret(user.password_hash, body.new_admin_password):
        raise ApiError(422, "SAME_PASSWORD", "Le mot de passe administrateur doit différer du mot de passe de connexion.")
    audit.set_setting(db, "owner_admin_hash", security.hash_secret(body.new_admin_password))
    audit.log(db, user, "ADMIN_PASSWORD_CHANGED", "security")
    return {"ok": True}


class AdminPwCheck(BaseModel):
    admin_password: str


@router.post("/security/verify-admin-password")
def verify_admin(body: AdminPwCheck, db: Session = Depends(get_db), user: User = Depends(security.current_user)):
    """Lets the UI confirm the password before showing a destructive form."""
    security.verify_admin_password(db, user, body.admin_password)
    return {"ok": True}
