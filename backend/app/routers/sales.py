"""Invoices (Catalog + Direct), receipts, stock receiving. Invoices are IMMUTABLE."""

from __future__ import annotations

from datetime import date
from html import escape

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import security
from ..db import get_db
from ..errors import ApiError
from ..models import Invoice, Product, StockMovement, User
from ..services import invoices as inv_svc
from ..services.finance import range_bounds
from ..services.stock import adjust_stock, receive_stock

router = APIRouter(tags=["sales"])
staff = security.require_roles(security.OWNER, security.WORKER)
owner_only = security.require_roles(security.OWNER)


class LineIn(BaseModel):
    product_id: int | None = None  # None => Vente Directe (unregistered item)
    label: str | None = None  # direct sale label, default "Article Divers"
    unit_name: str | None = None
    quantity: str | int | float
    unit_price: str | int | float | None = None


class InvoiceIn(BaseModel):
    lines: list[LineIn] = Field(min_length=1)
    payment_method: str = "cash"  # cash | orange | moov | wave | credit
    paid_method: str | None = None
    paid_amount: str | int | float | None = None
    customer_id: int | None = None
    note: str | None = None
    client_ref: str | None = None
    admin_password: str | None = None  # only needed to override a catalog price
    override_reason: str | None = None


@router.post("/invoices", status_code=201)
def create_invoice(
    body: InvoiceIn, db: Session = Depends(get_db), user: User = Depends(staff)
):
    inv = inv_svc.create_invoice(db, user, body.model_dump())
    return inv_svc.serialize(db, inv)


@router.get("/invoices")
def list_invoices(
    date_from: date | None = None,
    date_to: date | None = None,
    worker_id: int | None = None,
    status: str | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(staff),
):
    stmt = select(Invoice).order_by(Invoice.id.desc())
    if user.role == "WORKER":  # workers only ever see their OWN sales
        stmt = stmt.where(Invoice.worker_id == user.id)
    elif worker_id:
        stmt = stmt.where(Invoice.worker_id == worker_id)
    if date_from or date_to:
        a, b = range_bounds(date_from, date_to)
        stmt = stmt.where(Invoice.created_at >= a, Invoice.created_at < b)
    if status:
        stmt = stmt.where(Invoice.status == status.upper())
    rows = db.execute(stmt.limit(limit).offset(offset)).scalars().all()
    return [inv_svc.serialize(db, i) for i in rows]


def _get_visible(db: Session, user: User, iid: int) -> Invoice:
    inv = db.get(Invoice, iid)
    if not inv or (user.role == "WORKER" and inv.worker_id != user.id):
        raise ApiError(404, "NOT_FOUND", "Facture introuvable.")
    return inv


@router.get("/invoices/{iid}")
def get_invoice(iid: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    return inv_svc.serialize(db, _get_visible(db, user, iid))


class VoidIn(BaseModel):
    reason: str = Field(min_length=3, max_length=255)
    admin_password: str


@router.post("/invoices/{iid}/void")
def void_invoice(
    iid: int, body: VoidIn, db: Session = Depends(get_db), user: User = Depends(staff)
):
    inv = _get_visible(db, user, iid)
    inv_svc.void_invoice(db, user, inv, body.reason, body.admin_password)
    return inv_svc.serialize(db, inv)


# Deleting / editing a completed invoice is never possible through the API.
@router.delete("/invoices/{iid}")
@router.put("/invoices/{iid}")
@router.patch("/invoices/{iid}")
def forbid_invoice_mutation(iid: int, user: User = Depends(security.current_user)):
    if user.role == "WORKER":
        raise ApiError(
            403,
            "WORKER_FORBIDDEN",
            "Les ventes terminées ne peuvent être ni modifiées ni supprimées.",
        )
    raise ApiError(
        409,
        "INVOICE_IMMUTABLE",
        "Facture non modifiable. Utilisez l'annulation (avec mot de passe administrateur).",
    )


# --------------------------------------------------------------- printable receipt
SIZES = {"58": ("58mm", "9.5pt"), "80": ("80mm", "10.5pt"), "A4": ("210mm", "12pt")}


@router.get("/invoices/{iid}/receipt.html", response_class=HTMLResponse)
def receipt_html(
    iid: int,
    size: str = "80",
    db: Session = Depends(get_db),
    user: User = Depends(security.current_user_or_query),
):
    if size not in SIZES:
        raise ApiError(422, "INVALID_SIZE", "Format: 58, 80 ou A4.")
    inv = _get_visible(db, user, iid)
    d = inv_svc.serialize(db, inv)
    width, font = SIZES[size]
    page = "A4" if size == "A4" else f"{width} auto"
    rows = "".join(
        f"<tr><td>{escape(l['label'])}<br><small>{l['quantity']} {escape(l['unit_name'])} × {l['unit_price']}</small></td>"
        f"<td class=r>{l['line_total']}</td></tr>"
        for l in d["lines"]
    )
    void = (
        f"<p class=void>ANNULÉE {escape(d['void_reason'] or '')}</p>"
        if d["status"] == "VOIDED"
        else ""
    )
    return HTMLResponse(f"""<!doctype html><html><head><meta charset=utf-8><title>{d["receipt_no"]}</title>
<style>@page{{size:{page};margin:3mm}}body{{font:{font}/1.35 monospace;width:{width};margin:0 auto;padding:2mm}}
h1{{font-size:1.2em;text-align:center;margin:0}}table{{width:100%;border-collapse:collapse}}td{{vertical-align:top;padding:2px 0}}
.r{{text-align:right;white-space:nowrap}}hr{{border:0;border-top:1px dashed #000}}.void{{border:2px solid #000;text-align:center;font-weight:bold}}
.c{{text-align:center}}</style></head><body onload="window.print()">
<h1>{escape(d["shop"]["name"])}</h1><p class=c>{escape(d["shop"]["phone"])} {escape(d["shop"]["city"])}</p><hr>
<p>{d["receipt_no"]}<br>{d["created_at"]}<br>Vendeur: {escape(d["worker"]["name"])}</p>{void}<hr>
<table>{rows}</table><hr><table><tr><td><b>TOTAL</b></td><td class=r><b>{d["total"]} FCFA</b></td></tr>
<tr><td>Payé ({d["payment_method"]})</td><td class=r>{d["paid_amount"]}</td></tr>
<tr><td>Reste</td><td class=r>{d["balance_due"]}</td></tr></table><hr><p class=c>Merci / شكراً</p></body></html>""")


# --------------------------------------------------------------- stock
class ReceiveIn(BaseModel):
    product_id: int
    unit_name: str | None = None
    quantity: str | int | float
    unit_cost: str | int | float | None = None
    supplier_id: int | None = None
    pay_method: str | None = None
    paid_amount: str | int | float | None = None
    note: str | None = None


@router.post("/stock/receive", status_code=201)
def stock_receive(
    body: ReceiveIn, db: Session = Depends(get_db), user: User = Depends(staff)
):
    if user.role == "WORKER" and not user.can_receive_stock:
        raise ApiError(
            403, "WORKER_FORBIDDEN", "Réception de stock non autorisée pour ce compte."
        )
    p = db.get(Product, body.product_id)
    if not p:
        raise ApiError(404, "NOT_FOUND", "Produit introuvable.")
    mv = receive_stock(
        db,
        user,
        p,
        body.unit_name,
        body.quantity,
        body.unit_cost,
        body.supplier_id,
        body.pay_method,
        body.paid_amount,
        body.note,
    )
    return {
        "movement_id": mv.id,
        "added_base_qty": str(mv.qty_base),
        "stock_qty": str(p.stock_qty),
        "base_unit": p.base_unit,
    }


class AdjustIn(BaseModel):
    product_id: int
    new_qty_base: str | int | float
    reason: str


@router.post("/stock/adjust")
def stock_adjust(
    body: AdjustIn, db: Session = Depends(get_db), user: User = Depends(owner_only)
):
    p = db.get(Product, body.product_id)
    if not p:
        raise ApiError(404, "NOT_FOUND", "Produit introuvable.")
    adjust_stock(db, user, p, body.new_qty_base, body.reason)
    return {"stock_qty": str(p.stock_qty)}


@router.get("/stock/movements")
def stock_movements(
    product_id: int | None = None,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(owner_only),
):
    stmt = select(StockMovement).order_by(StockMovement.id.desc()).limit(limit)
    if product_id:
        stmt = stmt.where(StockMovement.product_id == product_id)
    return [
        {
            "id": m.id,
            "product_id": m.product_id,
            "kind": m.kind,
            "qty_base": str(m.qty_base),
            "unit_name": m.unit_name,
            "unit_qty": str(m.unit_qty) if m.unit_qty is not None else None,
            "note": m.note,
            "created_at": m.created_at.isoformat(),
        }
        for m in db.execute(stmt).scalars()
    ]
