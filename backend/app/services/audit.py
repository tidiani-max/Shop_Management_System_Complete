"""Append-only, hash-chained audit log + tiny settings/counter helpers."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuditLog, Counter, Setting, User, utcnow

GENESIS = "0" * 64


def _canon(ts: datetime, actor_id, action, entity, entity_id, reason, details, prev) -> str:
    return json.dumps(
        [ts.strftime("%Y-%m-%dT%H:%M:%S.%f"), actor_id, action, entity, entity_id, reason, details, prev],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def log(
    db: Session,
    actor: User | None,
    action: str,
    entity: str | None = None,
    entity_id: Any = None,
    reason: str | None = None,
    details: dict | None = None,
) -> AuditLog:
    last = db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).scalar_one_or_none()
    prev = last.hash if last else GENESIS
    ts = utcnow()
    det = json.dumps(details, ensure_ascii=False, sort_keys=True, default=str) if details else None
    eid = None if entity_id is None else str(entity_id)
    payload = _canon(ts, actor.id if actor else None, action, entity, eid, reason, det, prev)
    row = AuditLog(
        ts=ts,
        actor_id=actor.id if actor else None,
        actor_name=actor.name if actor else None,
        action=action,
        entity=entity,
        entity_id=eid,
        reason=reason,
        details=det,
        prev_hash=prev,
        hash=hashlib.sha256(payload.encode()).hexdigest(),
    )
    db.add(row)
    db.flush()
    return row


def verify_chain(db: Session) -> dict:
    prev = GENESIS
    n = 0
    for r in db.execute(select(AuditLog).order_by(AuditLog.id)).scalars():
        payload = _canon(r.ts, r.actor_id, r.action, r.entity, r.entity_id, r.reason, r.details, prev)
        if r.prev_hash != prev or r.hash != hashlib.sha256(payload.encode()).hexdigest():
            return {"ok": False, "broken_at": r.id, "checked": n}
        prev = r.hash
        n += 1
    return {"ok": True, "checked": n}


# ---- settings / counters
def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.get(Setting, key)
    return row.value if row else default


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(Setting, key)
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))
    db.flush()


def next_counter(db: Session, name: str) -> int:
    row = db.get(Counter, name)
    if not row:
        row = Counter(name=name, value=0)
        db.add(row)
        db.flush()
    row.value += 1
    db.flush()
    return row.value
