"""Exact Decimal helpers and multi-unit conversion (Carton -> Boîte -> Pièce, Litre, Kg...)."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from ..errors import ApiError
from ..models import Product

Q2 = Decimal("0.01")
Q3 = Decimal("0.001")
ZERO = Decimal("0")

UNIT_PRESETS = ["Unité", "Carton", "Boîte", "Paquet", "Pièce", "Litre", "Kg"]  # + any custom name


def D(value, field: str = "valeur") -> Decimal:
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, bool) or value is None:
        raise ApiError(422, "INVALID_NUMBER", f"{field}: nombre invalide.")
    else:
        try:
            d = Decimal(str(value).strip().replace(",", "."))
        except (InvalidOperation, ValueError):
            raise ApiError(422, "INVALID_NUMBER", f"{field}: nombre invalide.")
    if not d.is_finite():
        raise ApiError(422, "INVALID_NUMBER", f"{field}: nombre invalide.")
    return d


def q2(d: Decimal) -> Decimal:
    return d.quantize(Q2, rounding=ROUND_HALF_UP)


def q3(d: Decimal) -> Decimal:
    return d.quantize(Q3, rounding=ROUND_HALF_UP)


def _norm(name: str) -> str:
    return name.strip().casefold()


def validate_unit_defs(base_unit: str, units: list[dict]) -> list[dict]:
    """units = [{name, factor, price?}] where factor = base units per 1 of this unit."""
    seen = {_norm(base_unit)}
    out = []
    for u in units:
        name = (u.get("name") or "").strip()
        if not name:
            raise ApiError(422, "INVALID_UNIT", "Nom d'unité manquant.")
        if _norm(name) in seen:
            raise ApiError(422, "DUPLICATE_UNIT", f"Unité en double: {name}.")
        seen.add(_norm(name))
        factor = D(u.get("factor"), "facteur")
        if factor <= 0 or q3(factor) != factor:
            raise ApiError(422, "INVALID_FACTOR", f"Facteur invalide pour {name} (max 3 décimales, > 0).")
        price = u.get("price")
        out.append({"name": name, "factor": factor, "price": None if price in (None, "") else q2(D(price, "prix"))})
    return out


def find_unit(product: Product, unit_name: str | None) -> tuple[str, Decimal, Decimal | None]:
    """Returns (canonical name, factor to base, fixed price or None)."""
    if unit_name is None or _norm(unit_name) in ("", _norm(product.base_unit)):
        return product.base_unit, Decimal("1"), None
    for u in product.units:
        if _norm(u.name) == _norm(unit_name):
            return u.name, u.factor, u.price
    raise ApiError(422, "UNKNOWN_UNIT", f"Unité « {unit_name} » inconnue pour {product.name_fr}.")


def to_base(product: Product, unit_name: str | None, qty) -> tuple[Decimal, Decimal, str, Decimal]:
    """Convert a quantity in `unit_name` to base units. Returns (base_qty, factor, unit, qty)."""
    qty = D(qty, "quantité")
    if qty <= 0:
        raise ApiError(422, "INVALID_QUANTITY", "La quantité doit être supérieure à zéro.")
    name, factor, _ = find_unit(product, unit_name)
    base = qty * factor
    if q3(base) != base:
        raise ApiError(422, "INVALID_QUANTITY", "Quantité trop précise (3 décimales maximum en unité de base).")
    return base, factor, name, qty


def catalog_unit_price(product: Product, unit_name: str | None) -> Decimal:
    _, factor, fixed = find_unit(product, unit_name)
    return fixed if fixed is not None else q2(product.price * factor)
