"""Stock receiving / adjustments. All quantities are stored in BASE units."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from ..errors import ApiError
from ..models import Debt, Product, StockMovement, Supplier, User
from . import audit
from .finance import add_ledger
from .units import ZERO, D, q2, q3, to_base


def receive_stock(
    db: Session,
    user: User,
    product: Product,
    unit_name: str | None,
    qty,
    unit_cost=None,
    supplier_id: int | None = None,
    pay_method: str | None = None,
    paid_amount=None,
    note: str | None = None,
) -> StockMovement:
    """5 cartons of 12 packs -> +60 packs (base). Staff may enter the batch buying cost (audited);
    selling prices are never touched here. Supplier payment stays owner-only."""
    base, factor, uname, uqty = to_base(product, unit_name, qty)
    cost_base: Decimal | None = None
    total_cost = ZERO
    if unit_cost not in (None, ""):
        uc = D(unit_cost, "coût")
        if uc < 0:
            raise ApiError(422, "INVALID_NUMBER", "Coût invalide.")
        cost_base = uc / factor
        total_cost = q2(uc * uqty)
        old_stock = product.stock_qty if product.stock_qty > 0 else ZERO
        new_cost = (old_stock * product.cost + base * cost_base) / (old_stock + base)
        if q2(new_cost) != q2(product.cost):
            audit.log(db, user, "PRODUCT_COST_CHANGED", "product", product.id,
                      details={"old": str(product.cost), "new": str(q2(new_cost)), "via": "stock_receive"})
        product.cost = q2(new_cost) if q2(new_cost) == new_cost else new_cost.quantize(Decimal("0.0001"))
        if user.role != "OWNER":  # keep a trail of every cost a worker typed in
            audit.log(db, user, "STOCK_RECEIVED_COST", "product", product.id,
                      details={"unit": uname, "qty": str(uqty), "unit_cost": str(uc), "base_cost": str(cost_base)})
    if (pay_method or paid_amount not in (None, "")) and user.role != "OWNER":
        raise ApiError(403, "WORKER_FORBIDDEN", "Paiement fournisseur réservé au propriétaire.")

    product.stock_qty = q3(product.stock_qty + base)
    mv = StockMovement(
        product_id=product.id, kind="RECEIVE", qty_base=base, unit_name=uname, unit_qty=uqty,
        unit_cost=cost_base, user_id=user.id, note=note, ref_type="supplier" if supplier_id else None,
        ref_id=supplier_id,
    )
    db.add(mv)
    db.flush()

    if total_cost > 0 and pay_method:
        paid = total_cost if pay_method != "credit" else ZERO
        if paid_amount not in (None, ""):
            paid = q2(D(paid_amount, "montant payé"))
        if paid > total_cost or paid < 0:
            raise ApiError(422, "INVALID_AMOUNT", "Montant payé invalide.")
        if paid > 0:
            m = "cash" if pay_method == "credit" else pay_method
            add_ledger(db, m, -paid, "STOCK_PURCHASE", user, "stock_movement", mv.id,
                       f"Achat {product.name_fr}")
        owed = total_cost - paid
        if owed > 0:
            if not supplier_id or not db.get(Supplier, supplier_id):
                raise ApiError(422, "SUPPLIER_REQUIRED", "Fournisseur requis pour un achat à crédit.")
            db.add(Debt(direction="PAYABLE", supplier_id=supplier_id, original_amount=owed,
                        balance=owed, note=f"Achat {product.name_fr}"))
    db.flush()
    return mv


def adjust_stock(db: Session, user: User, product: Product, new_qty_base, reason: str) -> StockMovement:
    if not reason or len(reason.strip()) < 3:
        raise ApiError(422, "REASON_REQUIRED", "Une raison écrite est obligatoire.")
    target = q3(D(new_qty_base, "stock"))
    if target < 0:
        raise ApiError(422, "INVALID_QUANTITY", "Stock négatif impossible.")
    delta = target - product.stock_qty
    old = product.stock_qty
    product.stock_qty = target
    mv = StockMovement(product_id=product.id, kind="ADJUST", qty_base=delta, user_id=user.id, note=reason.strip())
    db.add(mv)
    db.flush()
    audit.log(db, user, "STOCK_ADJUSTED", "product", product.id, reason.strip(),
              {"old": str(old), "new": str(target)})
    return mv
