"""DDS_ADMIN (platform admin): technical support only - NO access to sales or finance."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config, security
from ..db import get_db
from ..errors import ApiError
from ..models import AuditLog, Invoice, Product, User
from ..services import audit
from .auth import gen_code, gen_password, user_out

router = APIRouter(prefix="/admin", tags=["dds-admin"])
dds_only = security.require_roles(security.DDS)
owner_or_admin = security.require_roles(security.OWNER, security.DDS)


@router.get("/overview")
def overview(db: Session = Depends(get_db), user: User = Depends(dds_only)):
    cnt = lambda m, *w: db.execute(select(func.count()).select_from(m).where(*w)).scalar_one()  # noqa: E731
    path = config.db_path()
    audit.log(db, user, "DDS_OVERVIEW_VIEWED", "admin")
    return {"shop_name": audit.get_setting(db, "shop_name"), "version": config.APP_VERSION,
            "users": cnt(User), "owners": cnt(User, User.role == "OWNER"), "workers": cnt(User, User.role == "WORKER"),
            "active_workers": cnt(User, User.role == "WORKER", User.active == True),  # noqa: E712
            "products": cnt(Product), "invoices": cnt(Invoice), "db_path": str(path),
            "db_size": path.stat().st_size if path.exists() else 0, "audit_chain": audit.verify_chain(db)}


@router.get("/users")
def users(db: Session = Depends(get_db), user: User = Depends(dds_only)):
    return [user_out(u) for u in db.execute(select(User).order_by(User.id)).scalars()]


@router.post("/users/{uid}/reset-password")
def reset_pw(uid: int, db: Session = Depends(get_db), user: User = Depends(dds_only)):
    u = db.get(User, uid)
    if not u:
        raise ApiError(404, "NOT_FOUND", "Utilisateur introuvable.")
    pw, rec = gen_password(), gen_code("PRO" if u.role == "OWNER" else "WK")
    u.password_hash, u.recovery_hash, u.pin_hash = security.hash_secret(pw), security.hash_secret(rec), None
    audit.log(db, user, "DDS_PASSWORD_RESET", "user", u.id)  # NB: does NOT touch the owner admin password
    return {"username": u.username, "password": pw, "recovery_code": rec}


@router.get("/audit")
def audit_log(limit: int = Query(200, le=1000), action: str | None = None, db: Session = Depends(get_db),
              user: User = Depends(owner_or_admin)):
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    return {"chain": audit.verify_chain(db),
            "items": [{"id": a.id, "ts": a.ts.isoformat(), "actor": a.actor_name, "action": a.action, "entity": a.entity,
                       "entity_id": a.entity_id, "reason": a.reason, "details": a.details} for a in db.execute(stmt).scalars()]}
