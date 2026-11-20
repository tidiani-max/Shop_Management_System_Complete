"""Ledger (CASH / MOBILE kept separate), balances and local-day helpers."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..errors import ApiError
from ..models import LedgerEntry, User
from .units import ZERO, q2

METHODS = {"cash": "CASH", "orange": "MOBILE", "moov": "MOBILE", "wave": "MOBILE"}
PAY_METHODS = set(METHODS) | {"credit"}


def account_of(method: str) -> str:
    if method not in METHODS:
        raise ApiError(422, "INVALID_METHOD", "Mode de paiement invalide.")
    return METHODS[method]


def add_ledger(
    db: Session,
    method: str,
    amount: Decimal,
    kind: str,
    user: User | None,
    ref_type: str | None = None,
    ref_id: int | None = None,
    note: str | None = None,
) -> LedgerEntry:
    if amount == 0:
        return None  # type: ignore[return-value]
    row = LedgerEntry(
        account=account_of(method),
        method=method,
        amount=q2(amount),
        kind=kind,
        ref_type=ref_type,
        ref_id=ref_id,
        user_id=user.id if user else None,
        note=note,
    )
    db.add(row)
    db.flush()
    return row


def balances(db: Session, until: datetime | None = None) -> dict[str, Decimal]:
    out = {"CASH": ZERO, "MOBILE": ZERO}
    q = select(LedgerEntry.account, LedgerEntry.amount)
    if until is not None:
        q = q.where(LedgerEntry.created_at <= until)
    for acc, amt in db.execute(q):
        out[acc] += amt
    return out


def local_tz():
    return datetime.now().astimezone().tzinfo


def day_bounds(d: date) -> tuple[datetime, datetime]:
    """[start, end) of a LOCAL calendar day, as UTC datetimes."""
    tz = local_tz()
    start = datetime(d.year, d.month, d.day, tzinfo=tz)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def range_bounds(d_from: date | None, d_to: date | None) -> tuple[datetime, datetime]:
    today = datetime.now().astimezone().date()
    d_from = d_from or today
    d_to = d_to or d_from
    if d_to < d_from:
        raise ApiError(422, "INVALID_RANGE", "Période invalide.")
    return day_bounds(d_from)[0], day_bounds(d_to)[1]


def local_year() -> int:
    return datetime.now().astimezone().year


def resolve_period(period: str | None, d_from: date | None, d_to: date | None) -> tuple[date, date]:
    """Local-calendar range. Explicit dates win; else period = day | week (Mon..today) | month (1st..today)."""
    today = datetime.now().astimezone().date()
    if d_from or d_to:
        a = d_from or d_to
        b = d_to or d_from
        return a, b
    if period in (None, "", "day"):
        return today, today
    if period == "week":
        return today - timedelta(days=today.weekday()), today
    if period == "month":
        return today.replace(day=1), today
    raise ApiError(422, "INVALID_PERIOD", "Période invalide (day, week, month).")


def deposit_balance(db: Session, customer_id: int) -> Decimal:
    """Money this customer currently holds WITH the shop (advance / deposit)."""
    from ..models import CustomerBalanceEntry
    rows = db.execute(select(CustomerBalanceEntry.amount).where(CustomerBalanceEntry.customer_id == customer_id))
    return sum((r[0] for r in rows), ZERO)
