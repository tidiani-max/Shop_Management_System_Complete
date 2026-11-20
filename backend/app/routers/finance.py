"""Cash / Mobile Money balances, expenses (OWNER only); customer credit, advances and the daily
register (staff: record only, never edit/delete history)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import security
from ..db import get_db
from ..errors import ApiError
from ..models import (Customer, CustomerBalanceEntry, Debt, DebtPayment, Expense, Invoice, LedgerEntry,
                      RegisterSession, Supplier, User, utcnow)
from ..services import audit
from ..services import invoices as inv_svc
from ..services.finance import METHODS, add_ledger, balances, deposit_balance, range_bounds
from ..services.units import ZERO, D, q2

router = APIRouter(prefix="/finance", tags=["finance"])
owner_only = security.require_roles(security.OWNER)
staff = security.require_roles(security.OWNER, security.WORKER)


@router.get("/balances")
def get_balances(db: Session = Depends(get_db), user: User = Depends(owner_only)):
    b = balances(db)
    by_method = {m: ZERO for m in METHODS}
    for m, a in db.execute(select(LedgerEntry.method, LedgerEntry.amount)):
        by_method[m] += a
    return {"cash": str(b["CASH"]), "mobile": str(b["MOBILE"]), "total": str(b["CASH"] + b["MOBILE"]),
            "by_method": {k: str(v) for k, v in by_method.items()}}


@router.get("/ledger")
def ledger(date_from: date | None = None, date_to: date | None = None, limit: int = Query(200, le=1000),
           db: Session = Depends(get_db), user: User = Depends(owner_only)):
    stmt = select(LedgerEntry).order_by(LedgerEntry.id.desc()).limit(limit)
    if date_from or date_to:
        a, b = range_bounds(date_from, date_to)
        stmt = stmt.where(LedgerEntry.created_at >= a, LedgerEntry.created_at < b)
    return [{"id": e.id, "account": e.account, "method": e.method, "amount": str(e.amount), "kind": e.kind,
             "note": e.note, "created_at": e.created_at.isoformat()} for e in db.execute(stmt).scalars()]


class OpeningIn(BaseModel):
    cash: str | int | float = 0
    mobile: str | int | float = 0
    mobile_method: str = "orange"


@router.post("/opening-balance")
def opening_balance(body: OpeningIn, db: Session = Depends(get_db), user: User = Depends(owner_only)):
    if db.execute(select(LedgerEntry.id).where(LedgerEntry.kind == "OPENING").limit(1)).first():
        raise ApiError(409, "ALREADY_SET", "Le solde d'ouverture est déjà enregistré.")
    add_ledger(db, "cash", q2(D(body.cash)), "OPENING", user, note="Solde initial")
    add_ledger(db, body.mobile_method, q2(D(body.mobile)), "OPENING", user, note="Solde initial")
    audit.log(db, user, "OPENING_BALANCE", "ledger", details={"cash": str(body.cash), "mobile": str(body.mobile)})
    return get_balances(db, user)


# ---------------------------------------------------------------- expenses
class ExpenseIn(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    amount: str | int | float
    method: str = "cash"
    category: str | None = None


@router.post("/expenses", status_code=201)
def add_expense(body: ExpenseIn, db: Session = Depends(get_db), user: User = Depends(owner_only)):
    amt = q2(D(body.amount, "montant"))
    if amt <= 0:
        raise ApiError(422, "INVALID_AMOUNT", "Montant invalide.")
    if body.method not in METHODS:
        raise ApiError(422, "INVALID_METHOD", "Mode de paiement invalide.")
    e = Expense(description=body.description.strip(), category=body.category, amount=amt, method=body.method,
                user_id=user.id)
    db.add(e)
    db.flush()
    add_ledger(db, body.method, -amt, "EXPENSE", user, "expense", e.id, e.description)
    return {"id": e.id, "description": e.description, "amount": str(amt), "method": e.method}


@router.get("/expenses")
def list_expenses(date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db),
                  user: User = Depends(owner_only)):
    stmt = select(Expense).order_by(Expense.id.desc()).limit(300)
    if date_from or date_to:
        a, b = range_bounds(date_from, date_to)
        stmt = stmt.where(Expense.created_at >= a, Expense.created_at < b)
    return [{"id": e.id, "description": e.description, "category": e.category, "amount": str(e.amount),
             "method": e.method, "created_at": e.created_at.isoformat()} for e in db.execute(stmt).scalars()]


# ---------------------------------------------------------------- debts
def _debt_out(db: Session, d: Debt) -> dict:
    party = db.get(Customer, d.customer_id) if d.customer_id else db.get(Supplier, d.supplier_id)
    items: list[str] = []
    recorded_by = None
    if d.invoice_id:
        inv = db.get(Invoice, d.invoice_id)
        if inv:
            items = [f"{l.label} × {l.unit_qty} {l.unit_name}" for l in inv.lines]
            w = db.get(User, inv.worker_id)
            recorded_by = w.name if w else None
    return {"id": d.id, "direction": d.direction, "party_id": party.id if party else None,
            "party_name": party.name if party else "?", "phone": party.phone if party else None,
            "original_amount": str(d.original_amount), "balance": str(d.balance),
            "paid": str(d.original_amount - d.balance), "status": d.status, "invoice_id": d.invoice_id,
            "note": d.note, "created_at": d.created_at.isoformat(), "items": items, "recorded_by": recorded_by,
            "deposit_balance": str(deposit_balance(db, d.customer_id)) if d.customer_id else "0"}


@router.get("/debts")
def list_debts(direction: str | None = None, include_closed: bool = False, db: Session = Depends(get_db),
               user: User = Depends(staff)):
    if user.role != "OWNER":  # workers only ever see what customers owe, never supplier payables
        direction = "RECEIVABLE"
    stmt = select(Debt).order_by(Debt.id.desc())
    if direction:
        stmt = stmt.where(Debt.direction == direction.upper())
    if not include_closed:
        stmt = stmt.where(Debt.status == "OPEN")
    rows = db.execute(stmt).scalars().all()
    recv = sum((d.balance for d in rows if d.direction == "RECEIVABLE" and d.status == "OPEN"), ZERO)
    pay = sum((d.balance for d in rows if d.direction == "PAYABLE" and d.status == "OPEN"), ZERO)
    return {"items": [_debt_out(db, d) for d in rows], "total_receivable": str(recv),
            "total_payable": str(pay if user.role == "OWNER" else ZERO)}


class DebtIn(BaseModel):
    direction: str = "RECEIVABLE"
    party_name: str | None = None
    party_id: int | None = None
    phone: str | None = None
    amount: str | int | float
    note: str | None = None


@router.post("/debts", status_code=201)
def add_debt(body: DebtIn, db: Session = Depends(get_db), user: User = Depends(owner_only)):
    """Manual debt (e.g. old notebook debts). Creating a debt does NOT touch cash or revenue."""
    amt = q2(D(body.amount, "montant"))
    if amt <= 0:
        raise ApiError(422, "INVALID_AMOUNT", "Montant invalide.")
    direction = body.direction.upper()
    if direction not in ("RECEIVABLE", "PAYABLE"):
        raise ApiError(422, "INVALID_DIRECTION", "Type de dette invalide.")
    model = Customer if direction == "RECEIVABLE" else Supplier
    party = db.get(model, body.party_id) if body.party_id else None
    if not party:
        if not body.party_name:
            raise ApiError(422, "PARTY_REQUIRED", "Nom de la personne requis.")
        party = model(name=body.party_name.strip(), phone=body.phone)
        db.add(party)
        db.flush()
    d = Debt(direction=direction, original_amount=amt, balance=amt, note=body.note,
             customer_id=party.id if direction == "RECEIVABLE" else None,
             supplier_id=party.id if direction == "PAYABLE" else None)
    db.add(d)
    db.flush()
    return _debt_out(db, d)


class RepayIn(BaseModel):
    amount: str | int | float
    method: str = "cash"


@router.post("/debts/{did}/payments", status_code=201)
def repay_debt(did: int, body: RepayIn, db: Session = Depends(get_db), user: User = Depends(staff)):
    """Repayment moves money (cash in/out) but is NEVER counted as new revenue.
    Workers can record customer repayments only (supplier payments stay with the owner)."""
    d = db.get(Debt, did)
    if not d or d.status != "OPEN":
        raise ApiError(404, "NOT_FOUND", "Dette introuvable ou déjà soldée.")
    if user.role != "OWNER" and d.direction != "RECEIVABLE":
        raise ApiError(403, "WORKER_FORBIDDEN", "Paiement fournisseur réservé au propriétaire.")
    amt = q2(D(body.amount, "montant"))
    if amt <= 0 or amt > d.balance:
        raise ApiError(422, "INVALID_AMOUNT", f"Montant invalide (reste à payer: {d.balance}).")
    if body.method not in METHODS:
        raise ApiError(422, "INVALID_METHOD", "Mode de paiement invalide.")
    p = DebtPayment(debt_id=d.id, amount=amt, method=body.method, user_id=user.id)
    db.add(p)
    db.flush()
    d.balance = d.balance - amt
    if d.balance == 0:
        d.status = "PAID"
    sign = 1 if d.direction == "RECEIVABLE" else -1
    add_ledger(db, body.method, sign * amt, "DEBT_REPAYMENT" if sign > 0 else "SUPPLIER_PAYMENT", user,
               "debt_payment", p.id, d.note)
    audit.log(db, user, "DEBT_REPAYMENT", "debt", d.id,
              details={"amount": str(amt), "method": body.method, "balance_after": str(d.balance)})
    return _debt_out(db, d)


# ---------------------------------------------------------------- customer credit & advances
class PartyRef(BaseModel):
    customer_id: int | None = None
    customer_name: str | None = None
    customer_phone: str | None = None


def _resolve_customer(db: Session, ref: PartyRef) -> Customer:
    """Pick an existing customer or quickly create one (Name + Phone are both required to create)."""
    if ref.customer_id:
        c = db.get(Customer, ref.customer_id)
        if not c or not c.active:
            raise ApiError(404, "CUSTOMER_NOT_FOUND", "Client introuvable.")
        return c
    name = (ref.customer_name or "").strip()
    phone = (ref.customer_phone or "").strip()
    if not name:
        raise ApiError(422, "CUSTOMER_REQUIRED", "Sélectionnez ou créez un client (nom + téléphone).")
    if not phone:
        raise ApiError(422, "PHONE_REQUIRED", "Le téléphone du client est obligatoire.")
    c = Customer(name=name, phone=phone)
    db.add(c)
    db.flush()
    return c


class CreditLineIn(BaseModel):
    product_id: int | None = None
    label: str | None = None
    unit_name: str | None = None
    quantity: str | int | float
    unit_price: str | int | float | None = None


class CustomerCreditIn(PartyRef):
    lines: list[CreditLineIn]
    paid_amount: str | int | float | None = None  # optional down payment
    paid_method: str = "cash"
    note: str | None = None
    client_ref: str | None = None
    admin_password: str | None = None  # only needed if a line price differs from the catalog
    override_reason: str | None = None


@router.post("/customer-credit", status_code=201)
def customer_credit(body: CustomerCreditIn, db: Session = Depends(get_db), user: User = Depends(staff)):
    """Crédit Client: the customer takes goods now and owes the money. Built on a real credit invoice so the
    items, stock, worker (actor) and timestamp are all recorded and immutable."""
    customer = _resolve_customer(db, body)
    payload = {"payment_method": "credit", "customer_id": customer.id, "paid_method": body.paid_method,
               "paid_amount": body.paid_amount, "note": body.note, "client_ref": body.client_ref,
               "admin_password": body.admin_password, "override_reason": body.override_reason,
               "lines": [l.model_dump() for l in body.lines]}
    inv = inv_svc.create_invoice(db, user, payload)
    if inv.total - inv.paid_amount <= 0:
        raise ApiError(422, "NOT_A_CREDIT", "Le montant payé couvre déjà tout : ce n'est pas un crédit.")
    debt = db.execute(select(Debt).where(Debt.invoice_id == inv.id)).scalar_one()
    audit.log(db, user, "CUSTOMER_CREDIT", "debt", debt.id,
              details={"customer": customer.id, "receipt": inv.receipt_no, "owed": str(debt.original_amount)})
    return {"invoice": inv_svc.serialize(db, inv), "debt": _debt_out(db, debt)}


class DepositIn(PartyRef):
    amount: str | int | float
    method: str = "cash"
    note: str | None = None


@router.post("/customer-deposits", status_code=201)
def customer_deposit(body: DepositIn, db: Session = Depends(get_db), user: User = Depends(staff)):
    """Avance / Dépôt Client: money the shop HOLDS for the customer. It is cash in, but never revenue."""
    amt = q2(D(body.amount, "montant"))
    if amt <= 0:
        raise ApiError(422, "INVALID_AMOUNT", "Montant invalide.")
    if body.method not in METHODS:
        raise ApiError(422, "INVALID_METHOD", "Mode de paiement invalide.")
    c = _resolve_customer(db, body)
    e = CustomerBalanceEntry(customer_id=c.id, kind="DEPOSIT", amount=amt, method=body.method,
                             user_id=user.id, note=body.note)
    db.add(e)
    db.flush()
    add_ledger(db, body.method, amt, "CUSTOMER_DEPOSIT", user, "customer_deposit", e.id, f"Avance {c.name}")
    audit.log(db, user, "CUSTOMER_DEPOSIT", "customer", c.id, details={"amount": str(amt), "method": body.method})
    return {"customer_id": c.id, "name": c.name, "phone": c.phone, "deposited": str(amt),
            "deposit_balance": str(deposit_balance(db, c.id))}


class ApplyIn(BaseModel):
    amount: str | int | float


@router.post("/debts/{did}/apply-deposit", status_code=201)
def apply_deposit(did: int, body: ApplyIn, db: Session = Depends(get_db), user: User = Depends(staff)):
    """Use the customer's advance to pay down a credit. No new cash moves (it was counted at deposit time)."""
    d = db.get(Debt, did)
    if not d or d.status != "OPEN" or d.direction != "RECEIVABLE" or not d.customer_id:
        raise ApiError(404, "NOT_FOUND", "Crédit introuvable ou déjà soldé.")
    amt = q2(D(body.amount, "montant"))
    avail = deposit_balance(db, d.customer_id)
    if amt <= 0 or amt > d.balance:
        raise ApiError(422, "INVALID_AMOUNT", f"Montant invalide (reste à payer: {d.balance}).")
    if amt > avail:
        raise ApiError(422, "INSUFFICIENT_DEPOSIT", f"Avance insuffisante (disponible: {avail}).")
    db.add(DebtPayment(debt_id=d.id, amount=amt, method="deposit", user_id=user.id))
    db.add(CustomerBalanceEntry(customer_id=d.customer_id, kind="APPLY", amount=-amt, debt_id=d.id,
                                user_id=user.id, note=d.note))
    d.balance = d.balance - amt
    if d.balance == 0:
        d.status = "PAID"
    db.flush()
    audit.log(db, user, "DEPOSIT_APPLIED", "debt", d.id, details={"amount": str(amt), "balance_after": str(d.balance)})
    return _debt_out(db, d)


class RefundIn(BaseModel):
    customer_id: int
    amount: str | int | float
    method: str = "cash"
    admin_password: str | None = None


@router.post("/customer-deposits/refund")
def refund_deposit(body: RefundIn, db: Session = Depends(get_db), user: User = Depends(owner_only)):
    """Handing a customer's advance back is a cash-out: OWNER + admin password only."""
    security.verify_admin_password(db, user, body.admin_password)
    amt = q2(D(body.amount, "montant"))
    c = db.get(Customer, body.customer_id)
    if not c:
        raise ApiError(404, "CUSTOMER_NOT_FOUND", "Client introuvable.")
    if body.method not in METHODS:
        raise ApiError(422, "INVALID_METHOD", "Mode de paiement invalide.")
    if amt <= 0 or amt > deposit_balance(db, c.id):
        raise ApiError(422, "INVALID_AMOUNT", "Montant invalide ou supérieur à l'avance.")
    e = CustomerBalanceEntry(customer_id=c.id, kind="REFUND", amount=-amt, method=body.method, user_id=user.id)
    db.add(e)
    db.flush()
    add_ledger(db, body.method, -amt, "DEPOSIT_REFUND", user, "customer_deposit", e.id, f"Remboursement avance {c.name}")
    audit.log(db, user, "DEPOSIT_REFUNDED", "customer", c.id, details={"amount": str(amt)})
    return {"customer_id": c.id, "deposit_balance": str(deposit_balance(db, c.id))}


@router.get("/customer-accounts")
def customer_accounts(db: Session = Depends(get_db), user: User = Depends(staff)):
    """Per customer: what they owe the shop and what the shop holds for them."""
    owed: dict[int, Decimal] = {}
    for d in db.execute(select(Debt).where(Debt.direction == "RECEIVABLE", Debt.status == "OPEN")).scalars():
        owed[d.customer_id] = owed.get(d.customer_id, ZERO) + d.balance
    held: dict[int, Decimal] = {}
    for cid, amt in db.execute(select(CustomerBalanceEntry.customer_id, CustomerBalanceEntry.amount)):
        held[cid] = held.get(cid, ZERO) + amt
    out = []
    for cid in sorted(set(owed) | {k for k, v in held.items() if v != 0}):
        c = db.get(Customer, cid)
        out.append({"customer_id": cid, "name": c.name, "phone": c.phone,
                    "owed": str(owed.get(cid, ZERO)), "deposit_balance": str(held.get(cid, ZERO))})
    return out


@router.get("/customers/{cid}/history")
def customer_history(cid: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    c = db.get(Customer, cid)
    if not c:
        raise ApiError(404, "CUSTOMER_NOT_FOUND", "Client introuvable.")
    names: dict[int, str] = {}

    def who(uid: int) -> str:
        if uid not in names:
            u = db.get(User, uid)
            names[uid] = u.name if u else "?"
        return names[uid]

    entries = db.execute(select(CustomerBalanceEntry).where(CustomerBalanceEntry.customer_id == cid)
                         .order_by(CustomerBalanceEntry.id.desc()).limit(100)).scalars()
    debts = db.execute(select(Debt).where(Debt.customer_id == cid).order_by(Debt.id.desc()).limit(100)).scalars()
    return {"customer": {"id": c.id, "name": c.name, "phone": c.phone},
            "deposit_balance": str(deposit_balance(db, cid)),
            "deposits": [{"id": e.id, "kind": e.kind, "amount": str(e.amount), "by": who(e.user_id),
                          "created_at": e.created_at.isoformat(), "note": e.note} for e in entries],
            "credits": [_debt_out(db, d) for d in debts]}


# ---------------------------------------------------------------- register
def _reg_out(r: RegisterSession) -> dict:
    f = lambda v: None if v is None else str(v)  # noqa: E731
    return {"id": r.id, "status": r.status, "opened_at": r.opened_at.isoformat(), "opening_cash": str(r.opening_cash),
            "opening_mobile": str(r.opening_mobile), "closed_at": r.closed_at.isoformat() if r.closed_at else None,
            "expected_cash": f(r.expected_cash), "expected_mobile": f(r.expected_mobile),
            "counted_cash": f(r.counted_cash), "counted_mobile": f(r.counted_mobile),
            "diff_cash": f(r.diff_cash), "diff_mobile": f(r.diff_mobile), "note": r.note}


@router.get("/register/current")
def register_current(db: Session = Depends(get_db), user: User = Depends(staff)):
    r = db.execute(select(RegisterSession).where(RegisterSession.status == "OPEN")).scalars().first()
    return _reg_out(r) if r else None


class OpenIn(BaseModel):
    opening_cash: str | int | float
    opening_mobile: str | int | float = 0


@router.post("/register/open", status_code=201)
def register_open(body: OpenIn, db: Session = Depends(get_db), user: User = Depends(staff)):
    if db.execute(select(RegisterSession).where(RegisterSession.status == "OPEN")).scalars().first():
        raise ApiError(409, "REGISTER_OPEN", "Une caisse est déjà ouverte.")
    r = RegisterSession(opened_by=user.id, opening_cash=q2(D(body.opening_cash)),
                        opening_mobile=q2(D(body.opening_mobile)))
    db.add(r)
    db.flush()
    return _reg_out(r)


class CloseIn(BaseModel):
    counted_cash: str | int | float
    counted_mobile: str | int | float = 0
    note: str | None = None
    post_adjustment: bool = False  # owner may book the difference into the ledger


@router.post("/register/close")
def register_close(body: CloseIn, db: Session = Depends(get_db), user: User = Depends(staff)):
    r = db.execute(select(RegisterSession).where(RegisterSession.status == "OPEN")).scalars().first()
    if not r:
        raise ApiError(409, "NO_REGISTER", "Aucune caisse ouverte.")
    b = balances(db)
    cc, cm = q2(D(body.counted_cash)), q2(D(body.counted_mobile))
    r.status, r.closed_by, r.closed_at = "CLOSED", user.id, utcnow()
    r.expected_cash, r.expected_mobile = b["CASH"], b["MOBILE"]
    r.counted_cash, r.counted_mobile = cc, cm
    r.diff_cash, r.diff_mobile = cc - b["CASH"], cm - b["MOBILE"]
    r.note = body.note
    db.flush()
    audit.log(db, user, "REGISTER_CLOSED", "register", r.id, body.note,
              {"diff_cash": str(r.diff_cash), "diff_mobile": str(r.diff_mobile)})
    if body.post_adjustment:
        if user.role != "OWNER":
            raise ApiError(403, "WORKER_FORBIDDEN", "Seul le propriétaire peut ajuster les soldes.")
        add_ledger(db, "cash", r.diff_cash, "ADJUSTMENT", user, "register", r.id, "Écart de caisse")
        add_ledger(db, "orange", r.diff_mobile, "ADJUSTMENT", user, "register", r.id, "Écart mobile money")
    return _reg_out(r)


@router.get("/register/history")
def register_history(db: Session = Depends(get_db), user: User = Depends(owner_only)):
    return [_reg_out(r) for r in db.execute(select(RegisterSession).order_by(RegisterSession.id.desc()).limit(60)).scalars()]
