"""Products (multi-unit), customers, suppliers.
Staff may CREATE products (initial price/cost) and receive stock; changing an existing
product (price, cost, units) is OWNER + admin password only."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import security
from ..db import get_db
from ..errors import ApiError
from ..models import Customer, Product, ProductUnit, Supplier, User
from ..services import audit
from ..services.units import UNIT_PRESETS, D, q2, q3, validate_unit_defs

router = APIRouter(tags=["catalog"])
owner_only = security.require_roles(security.OWNER)
staff = security.require_roles(security.OWNER, security.WORKER)


class UnitIn(BaseModel):
    name: str
    factor: str | int | float
    price: str | int | float | None = None


class ProductIn(BaseModel):
    name_fr: str = Field(min_length=1, max_length=160)
    name_ar: str | None = None
    category: str | None = None
    barcode: str | None = None
    base_unit: str = "Unité"
    price: str | int | float
    cost: str | int | float = 0
    units: list[UnitIn] = []
    initial_stock: str | int | float | None = None
    initial_stock_unit: str | None = (
        None  # e.g. "Carton": 5 cartons -> converted to base units
    )
    low_stock_threshold: str | int | float = 5
    color: str | None = None
    admin_password: str | None = None


class ProductPatch(BaseModel):
    name_fr: str | None = None
    name_ar: str | None = None
    category: str | None = None
    barcode: str | None = None
    price: str | int | float | None = None
    cost: str | int | float | None = None
    units: list[UnitIn] | None = None
    low_stock_threshold: str | int | float | None = None
    active: bool | None = None
    color: str | None = None
    admin_password: str | None = None


def product_out(p: Product, *, show_cost: bool) -> dict:
    out = {
        "id": p.id,
        "name_fr": p.name_fr,
        "name_ar": p.name_ar,
        "category": p.category,
        "barcode": p.barcode,
        "base_unit": p.base_unit,
        "price": str(p.price),
        "stock_qty": str(p.stock_qty),
        "low_stock_threshold": str(p.low_stock_threshold),
        "color": p.color,
        "active": p.active,
        "units": [
            {"name": p.base_unit, "factor": "1", "price": str(p.price), "base": True}
        ]
        + [
            {
                "name": u.name,
                "factor": str(u.factor),
                "price": str(
                    u.price if u.price is not None else q2(p.price * u.factor)
                ),
                "base": False,
            }
            for u in p.units
        ],
    }
    if show_cost:
        out["cost"] = str(p.cost)
    return out


@router.get("/meta/unit-presets")
def unit_presets(user: User = Depends(staff)):
    return {"presets": UNIT_PRESETS, "custom_allowed": True}


@router.get("/products")
def list_products(
    q: str | None = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(staff),
):
    stmt = select(Product).order_by(Product.name_fr)
    if active_only:
        stmt = stmt.where(Product.active == True)  # noqa: E712
    rows = db.execute(stmt).scalars().all()
    if q:
        ql = q.lower()
        rows = [
            p
            for p in rows
            if ql in p.name_fr.lower()
            or ql in (p.name_ar or "").lower()
            or ql == (p.barcode or "")
        ]
    return [product_out(p, show_cost=user.role == "OWNER") for p in rows]


@router.post("/products")
def create_product(
    body: ProductIn, db: Session = Depends(get_db), user: User = Depends(staff)
):
    """Owner AND workers can create a NEW product (with its first price/cost).
    Changing the price of an existing product stays owner + admin password (see update_product)."""
    price = q2(D(body.price, "prix"))
    cost = q2(D(body.cost, "coût"))
    if price < 0 or cost < 0:
        raise ApiError(422, "INVALID_NUMBER", "Prix/coût invalide.")
    has_initial = body.initial_stock not in (None, "", 0, "0")
    if has_initial and user.role == "WORKER" and not user.can_receive_stock:
        raise ApiError(
            403, "WORKER_FORBIDDEN", "Réception de stock non autorisée pour ce compte."
        )
    # anti-fraud: a worker must not bypass the price rule by re-creating an existing product at another price
    name = body.name_fr.strip()
    dup = db.execute(select(Product).where(Product.active == True)).scalars().all()  # noqa: E712
    if any(x.name_fr.strip().lower() == name.lower() for x in dup):
        raise ApiError(409, "DUPLICATE_PRODUCT", "Un produit avec ce nom existe déjà.")
    if body.barcode and any((x.barcode or "") == body.barcode for x in dup):
        raise ApiError(409, "DUPLICATE_BARCODE", "Ce code-barres existe déjà.")
    defs = validate_unit_defs(body.base_unit, [u.model_dump() for u in body.units])
    p = Product(
        name_fr=name,
        name_ar=body.name_ar,
        category=body.category,
        barcode=body.barcode,
        base_unit=body.base_unit.strip(),
        price=price,
        cost=cost,
        stock_qty=Decimal("0"),
        low_stock_threshold=q3(D(body.low_stock_threshold)),
        color=body.color,
    )
    p.units = [ProductUnit(**d) for d in defs]
    db.add(p)
    db.flush()
    audit.log(
        db,
        user,
        "PRODUCT_CREATED",
        "product",
        p.id,
        details={
            "name": p.name_fr,
            "price": str(price),
            "cost": str(cost),
            "by_role": user.role,
        },
    )
    if has_initial:
        from ..services.stock import receive_stock

        receive_stock(
            db,
            user,
            p,
            body.initial_stock_unit or p.base_unit,
            body.initial_stock,
            note="Stock initial",
        )
    return product_out(p, show_cost=user.role == "OWNER")


@router.patch("/products/{pid}")
def update_product(
    pid: int,
    body: ProductPatch,
    db: Session = Depends(get_db),
    user: User = Depends(security.current_user),
):
    data = body.model_dump(exclude_unset=True)
    touches_money = any(k in data for k in ("price", "cost", "units"))
    if user.role != "OWNER":
        raise ApiError(
            403,
            "WORKER_FORBIDDEN",
            "Seul le propriétaire peut modifier les produits et les prix.",
        )
    p = db.get(Product, pid)
    if not p:
        raise ApiError(404, "NOT_FOUND", "Produit introuvable.")
    if (
        touches_money
    ):  # even the owner needs the separate admin password to change prices/costs
        security.verify_admin_password(db, user, data.get("admin_password"))
    changes = {}
    if "price" in data and data["price"] is not None:
        new = q2(D(data["price"], "prix"))
        if new < 0:
            raise ApiError(422, "INVALID_NUMBER", "Prix invalide.")
        if new != p.price:
            changes["price"] = [str(p.price), str(new)]
            p.price = new
    if "cost" in data and data["cost"] is not None:
        new = q2(D(data["cost"], "coût"))
        if new != p.cost:
            changes["cost"] = [str(p.cost), str(new)]
            p.cost = new
    if body.units is not None:
        defs = validate_unit_defs(p.base_unit, [u.model_dump() for u in body.units])
        changes["units"] = [f"{d['name']}={d['factor']}" for d in defs]
        p.units.clear()
        db.flush()
        p.units.extend(ProductUnit(**d) for d in defs)
    for f in ("name_fr", "name_ar", "category", "barcode", "color", "active"):
        if f in data and data[f] is not None:
            setattr(p, f, data[f])
    if "low_stock_threshold" in data and data["low_stock_threshold"] is not None:
        p.low_stock_threshold = q3(D(data["low_stock_threshold"]))
    db.flush()
    if changes:
        audit.log(
            db,
            user,
            "PRODUCT_PRICE_CHANGED"
            if ("price" in changes or "cost" in changes)
            else "PRODUCT_UNITS_CHANGED",
            "product",
            p.id,
            details=changes,
        )
    return product_out(p, show_cost=True)


@router.delete("/products/{pid}")
def delete_product(
    pid: int, db: Session = Depends(get_db), user: User = Depends(owner_only)
):
    p = db.get(Product, pid)
    if not p:
        raise ApiError(404, "NOT_FOUND", "Produit introuvable.")
    p.active = False  # never hard-delete: invoices reference products
    audit.log(db, user, "PRODUCT_DEACTIVATED", "product", p.id)
    return {"ok": True}


class UnitAddIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    factor: str | int | float


@router.post("/products/{pid}/units", status_code=201)
def add_unit(
    pid: int,
    body: UnitAddIn,
    db: Session = Depends(get_db),
    user: User = Depends(staff),
):
    """Staff may ADD a new packaging (e.g. Carton = 200 pieces). No fixed price: the price is always
    base price x factor. Editing or removing existing packagings stays owner + admin password."""
    p = db.get(Product, pid)
    if not p or not p.active:
        raise ApiError(404, "NOT_FOUND", "Produit introuvable.")
    existing = [{"name": u.name, "factor": u.factor, "price": u.price} for u in p.units]
    defs = validate_unit_defs(
        p.base_unit,
        existing + [{"name": body.name, "factor": body.factor, "price": None}],
    )
    new = defs[-1]
    p.units.append(ProductUnit(**new))
    db.flush()
    db.refresh(p)
    audit.log(
        db,
        user,
        "PRODUCT_UNIT_ADDED",
        "product",
        p.id,
        details={
            "unit": new["name"],
            "factor": str(new["factor"]),
            "by_role": user.role,
        },
    )
    return product_out(p, show_cost=user.role == "OWNER")


class UnitAddIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    factor: str | int | float


@router.post("/products/{pid}/units", status_code=201)
def add_unit(
    pid: int,
    body: UnitAddIn,
    db: Session = Depends(get_db),
    user: User = Depends(staff),
):
    """Staff may ADD a new packaging (e.g. Carton = 200 pieces). No fixed price: the price is always
    base price x factor. Editing or removing existing packagings stays owner + admin password."""
    p = db.get(Product, pid)
    if not p or not p.active:
        raise ApiError(404, "NOT_FOUND", "Produit introuvable.")
    existing = [{"name": u.name, "factor": u.factor, "price": u.price} for u in p.units]
    defs = validate_unit_defs(
        p.base_unit,
        existing + [{"name": body.name, "factor": body.factor, "price": None}],
    )
    new = defs[-1]
    p.units.append(ProductUnit(**new))
    db.flush()
    db.refresh(p)
    audit.log(
        db,
        user,
        "PRODUCT_UNIT_ADDED",
        "product",
        p.id,
        details={
            "unit": new["name"],
            "factor": str(new["factor"]),
            "by_role": user.role,
        },
    )
    return product_out(p, show_cost=user.role == "OWNER")


# ------------------------------------------------------- customers / suppliers
class PartyIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str | None = None


@router.get("/customers")
def list_customers(
    q: str | None = None, db: Session = Depends(get_db), user: User = Depends(staff)
):
    rows = (
        db.execute(
            select(Customer).where(Customer.active == True).order_by(Customer.name)
        )
        .scalars()
        .all()
    )  # noqa: E712
    if q:
        rows = [c for c in rows if q.lower() in c.name.lower() or q in (c.phone or "")]
    return [{"id": c.id, "name": c.name, "phone": c.phone} for c in rows]


@router.post("/customers")
def create_customer(
    body: PartyIn, db: Session = Depends(get_db), user: User = Depends(staff)
):
    c = Customer(name=body.name.strip(), phone=body.phone)
    db.add(c)
    db.flush()
    return {"id": c.id, "name": c.name, "phone": c.phone}


@router.get("/suppliers")
def list_suppliers(db: Session = Depends(get_db), user: User = Depends(staff)):
    return [
        {"id": s.id, "name": s.name, "phone": s.phone}
        for s in db.execute(
            select(Supplier).where(Supplier.active == True).order_by(Supplier.name)
        ).scalars()
    ]  # noqa: E712


@router.post("/suppliers")
def create_supplier(
    body: PartyIn, db: Session = Depends(get_db), user: User = Depends(owner_only)
):
    s = Supplier(name=body.name.strip(), phone=body.phone)
    db.add(s)
    db.flush()
    return {"id": s.id, "name": s.name, "phone": s.phone}
