"""One invoice engine for BOTH Catalog sales and Direct sales (Vente Directe)."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..errors import ApiError
from ..models import (Customer, CustomerBalanceEntry, Debt, DebtPayment, Invoice, InvoiceLine, LedgerEntry, Product,
                      StockMovement, User, utcnow)
from .. import security
from . import audit
from .finance import PAY_METHODS, add_ledger, local_year
from .units import ZERO, D, catalog_unit_price, q2, q3, to_base

DEFAULT_LABEL = "Article Divers"


def _receipt_no(db: Session) -> tuple[str, int, int]:
    year = local_year()
    seq = audit.next_counter(db, f"receipt:{year}")
    return f"REC-{year}-{seq:05d}", year, seq


def create_invoice(db: Session, user: User, payload: dict) -> Invoice:
    # idempotency: same client_ref returns the already-created invoice
    ref = payload.get("client_ref")
    if ref:
        existing = db.execute(select(Invoice).where(Invoice.client_ref == ref)).scalar_one_or_none()
        if existing:
            return existing

    raw_lines = payload.get("lines") or []
    if not raw_lines:
        raise ApiError(422, "EMPTY_INVOICE", "Ajoutez au moins un article.")

    method = payload.get("payment_method", "cash")
    if method not in PAY_METHODS:
        raise ApiError(422, "INVALID_METHOD", "Mode de paiement invalide.")

    # --- 1. resolve lines (read-only) ---
    resolved: list[dict] = []
    override_needed = False
    for i, ln in enumerate(raw_lines, 1):
        pid = ln.get("product_id")
        if pid:  # ---------- CATALOG line
            prod = db.get(Product, pid)
            if not prod or not prod.active:
                raise ApiError(404, "PRODUCT_NOT_FOUND", f"Ligne {i}: produit introuvable.")
            base, factor, uname, uqty = to_base(prod, ln.get("unit_name"), ln.get("quantity"))
            cat_price = catalog_unit_price(prod, ln.get("unit_name"))
            price, overridden = cat_price, False
            if ln.get("unit_price") not in (None, ""):
                p = q2(D(ln["unit_price"], "prix"))
                if p < 0:
                    raise ApiError(422, "INVALID_NUMBER", "Prix invalide.")
                if p != cat_price:
                    price, overridden, override_needed = p, True, True
            resolved.append(dict(prod=prod, label=prod.name_fr, unit=uname, uqty=uqty, factor=factor,
                                 base=base, price=price, overridden=overridden))
        else:  # ---------- DIRECT sale line (unregistered item, no stock effect)
            uqty = D(ln.get("quantity"), "quantité")
            if uqty <= 0 or q3(uqty) != uqty:
                raise ApiError(422, "INVALID_QUANTITY", f"Ligne {i}: quantité invalide.")
            if ln.get("unit_price") in (None, ""):
                raise ApiError(422, "PRICE_REQUIRED", f"Ligne {i}: prix requis pour une vente directe.")
            price = q2(D(ln["unit_price"], "prix"))
            if price < 0:
                raise ApiError(422, "INVALID_NUMBER", "Prix invalide.")
            resolved.append(dict(prod=None, label=(ln.get("label") or "").strip() or DEFAULT_LABEL,
                                 unit=(ln.get("unit_name") or "pièce").strip(), uqty=uqty,
                                 factor=Decimal("1"), base=uqty, price=price, overridden=False))

    # --- 2. price override needs the Owner Admin Password (verified BEFORE any write) ---
    if override_needed:
        security.verify_admin_password(db, user, payload.get("admin_password"))

    # --- 3. stock check (aggregate per product) ---
    need: dict[int, Decimal] = defaultdict(lambda: ZERO)
    for r in resolved:
        if r["prod"]:
            need[r["prod"].id] += r["base"]
    for pid, qty in need.items():
        prod = db.get(Product, pid)
        if prod.stock_qty < qty:
            raise ApiError(409, "INSUFFICIENT_STOCK",
                           f"Stock insuffisant: {prod.name_fr} (disponible {prod.stock_qty} {prod.base_unit}).",
                           {"product_id": pid, "available": str(prod.stock_qty)})

    total = q2(sum((q2(r["uqty"] * r["price"]) for r in resolved), ZERO))

    # --- 4. payment split / credit rules ---
    customer = None
    if payload.get("customer_id"):
        customer = db.get(Customer, payload["customer_id"])
        if not customer:
            raise ApiError(404, "CUSTOMER_NOT_FOUND", "Client introuvable.")
    paid_method = method
    if method == "credit":
        paid_method = payload.get("paid_method") or "cash"
        if paid_method not in ("cash", "orange", "moov", "wave"):
            raise ApiError(422, "INVALID_METHOD", "Mode de paiement invalide.")
        pa = payload.get("paid_amount")
        paid = q2(D(0 if pa in (None, "") else pa, "montant payé"))
    else:
        paid = total if payload.get("paid_amount") in (None, "") else q2(D(payload["paid_amount"], "montant payé"))
    if paid < 0 or paid > total:
        raise ApiError(422, "INVALID_AMOUNT", "Montant payé invalide.")
    owed = total - paid
    if owed > 0:
        if not customer:
            raise ApiError(422, "CUSTOMER_REQUIRED", "Sélectionnez un client pour une vente à crédit.")
        if user.role == "WORKER" and not user.can_sell_credit:
            raise ApiError(403, "CREDIT_NOT_ALLOWED", "Ventes à crédit non autorisées pour ce compte.")

    # --- 5. write everything ---
    kinds = {bool(r["prod"]) for r in resolved}
    kind = "MIXED" if len(kinds) == 2 else ("CATALOG" if True in kinds else "DIRECT")
    receipt_no, year, seq = _receipt_no(db)
    inv = Invoice(receipt_no=receipt_no, year=year, seq=seq, kind=kind, status="COMPLETED",
                  worker_id=user.id, customer_id=customer.id if customer else None, total=total,
                  paid_amount=paid, payment_method=method, paid_method=paid_method if paid > 0 else None,
                  client_ref=ref, note=(payload.get("note") or None))
    db.add(inv)
    db.flush()
    for r in resolved:
        prod: Product | None = r["prod"]
        cost = q2(r["base"] * prod.cost) if prod else ZERO
        db.add(InvoiceLine(invoice_id=inv.id, product_id=prod.id if prod else None, label=r["label"],
                           unit_name=r["unit"], unit_qty=r["uqty"], factor=r["factor"], base_qty=r["base"],
                           unit_price=r["price"], line_total=q2(r["uqty"] * r["price"]), cost_total=cost,
                           price_overridden=r["overridden"]))
        if prod:
            prod.stock_qty = q3(prod.stock_qty - r["base"])
            db.add(StockMovement(product_id=prod.id, kind="SALE", qty_base=-r["base"], unit_name=r["unit"],
                                 unit_qty=r["uqty"], ref_type="invoice", ref_id=inv.id, user_id=user.id))
        if r["overridden"]:
            audit.log(db, user, "PRICE_OVERRIDE", "invoice", inv.id, payload.get("override_reason"),
                      {"receipt": receipt_no, "product": prod.id if prod else None,
                       "catalog_price": str(catalog_unit_price(prod, r["unit"])), "sold_price": str(r["price"])})
    db.flush()
    if paid > 0:
        add_ledger(db, paid_method, paid, "SALE", user, "invoice", inv.id, receipt_no)
    if owed > 0:
        db.add(Debt(direction="RECEIVABLE", customer_id=customer.id, invoice_id=inv.id,
                    original_amount=owed, balance=owed, note=receipt_no))
    db.flush()
    return inv


def void_invoice(db: Session, user: User, inv: Invoice, reason: str, admin_password: str | None) -> Invoice:
    if inv.status != "COMPLETED":
        raise ApiError(409, "ALREADY_VOIDED", "Cette facture est déjà annulée.")
    if not reason or len(reason.strip()) < 3:
        raise ApiError(422, "REASON_REQUIRED", "Une raison écrite est obligatoire.")
    security.verify_admin_password(db, user, admin_password)  # before any write

    reversed_money = ZERO
    # 1. stock back
    for ln in inv.lines:
        if ln.product_id:
            prod = db.get(Product, ln.product_id)
            prod.stock_qty = q3(prod.stock_qty + ln.base_qty)
            db.add(StockMovement(product_id=prod.id, kind="VOID_REVERSAL", qty_base=ln.base_qty,
                                 unit_name=ln.unit_name, unit_qty=ln.unit_qty, ref_type="invoice",
                                 ref_id=inv.id, user_id=user.id, note=reason.strip()))
    # 2. money back: the original payment + any later debt repayments
    entries = list(db.execute(select(LedgerEntry).where(
        LedgerEntry.ref_type == "invoice", LedgerEntry.ref_id == inv.id, LedgerEntry.kind == "SALE")).scalars())
    debt = db.execute(select(Debt).where(Debt.invoice_id == inv.id)).scalar_one_or_none()
    if debt:
        pays = list(db.execute(select(DebtPayment).where(DebtPayment.debt_id == debt.id)).scalars())
        pay_ids = [p.id for p in pays]
        for pay in pays:  # advance used to pay this credit goes back to the customer's balance
            if pay.method == "deposit":
                db.add(CustomerBalanceEntry(customer_id=debt.customer_id, kind="VOID_RETURN", amount=pay.amount,
                                            debt_id=debt.id, user_id=user.id, note=f"Annulation {inv.receipt_no}"))
        entries += list(db.execute(select(LedgerEntry).where(
            LedgerEntry.ref_type == "debt_payment", LedgerEntry.ref_id.in_(pay_ids or [-1]))).scalars())
        debt.status, debt.balance = "CANCELLED", ZERO
    for e in entries:
        add_ledger(db, e.method, -e.amount, "VOID_REVERSAL", user, "invoice", inv.id,
                   f"Annulation {inv.receipt_no}")
        reversed_money += e.amount
    # 3. mark void (the only change a completed invoice may ever receive)
    inv.status, inv.voided_at, inv.voided_by, inv.void_reason = "VOIDED", utcnow(), user.id, reason.strip()
    db.flush()
    audit.log(db, user, "INVOICE_VOIDED", "invoice", inv.id, reason.strip(),
              {"receipt": inv.receipt_no, "total": str(inv.total), "money_reversed": str(reversed_money)})
    return inv


def serialize(db: Session, inv: Invoice) -> dict:
    worker = db.get(User, inv.worker_id)
    cust = db.get(Customer, inv.customer_id) if inv.customer_id else None
    voider = db.get(User, inv.voided_by) if inv.voided_by else None
    return {
        "id": inv.id, "receipt_no": inv.receipt_no, "kind": inv.kind, "status": inv.status,
        "created_at": inv.created_at.isoformat(), "worker": {"id": worker.id, "name": worker.name},
        "customer": {"id": cust.id, "name": cust.name, "phone": cust.phone} if cust else None,
        "payment_method": inv.payment_method, "paid_method": inv.paid_method,
        "total": str(inv.total), "paid_amount": str(inv.paid_amount),
        "balance_due": str(inv.total - inv.paid_amount), "note": inv.note,
        "voided_at": inv.voided_at.isoformat() if inv.voided_at else None,
        "voided_by": voider.name if voider else None, "void_reason": inv.void_reason,
        "lines": [{"id": l.id, "product_id": l.product_id, "label": l.label, "unit_name": l.unit_name,
                   "quantity": str(l.unit_qty), "unit_price": str(l.unit_price), "line_total": str(l.line_total),
                   "price_overridden": l.price_overridden, "direct": l.product_id is None} for l in inv.lines],
        "shop": {"name": audit.get_setting(db, "shop_name"), "phone": audit.get_setting(db, "shop_phone"),
                 "city": audit.get_setting(db, "shop_city")},
    }
