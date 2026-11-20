"""One invoice engine: Catalog + Direct sales share sequential receipt numbers."""
from datetime import datetime
from decimal import Decimal

D = Decimal
YEAR = datetime.now().astimezone().year


def direct(shop, token=None, label=None, qty="1", unit="pièce", price="500"):
    line = {"quantity": qty, "unit_name": unit, "unit_price": price}
    if label:
        line["label"] = label
    return shop.call("POST", "/invoices", token, json={"lines": [line], "payment_method": "cash"})


def catalog(shop, pid, token=None, qty="1"):
    return shop.call("POST", "/invoices", token, json={"lines": [{"product_id": pid, "quantity": qty}]})


def test_sequential_numbers_across_direct_and_catalog(shop):
    p = shop.product("Riz", base="Kg", price="750", stock="100")
    wtok, _ = shop.worker()
    nums = [
        direct(shop, wtok).json()["receipt_no"],
        catalog(shop, p["id"], wtok, "2").json()["receipt_no"],
        direct(shop, shop.owner, "Pain").json()["receipt_no"],
        catalog(shop, p["id"], shop.owner).json()["receipt_no"],
        direct(shop, wtok).json()["receipt_no"],
    ]
    assert nums == [f"REC-{YEAR}-{i:05d}" for i in range(1, 6)]


def test_direct_sale_needs_no_product_and_touches_no_stock(shop):
    p = shop.product("Riz", base="Kg", price="750", stock="10")
    r = direct(shop, label=None, qty="2.5", unit="litre", price="400")
    assert r.status_code == 201
    inv = r.json()
    assert inv["kind"] == "DIRECT" and inv["lines"][0]["label"] == "Article Divers"
    assert inv["lines"][0]["unit_name"] == "litre" and D(inv["total"]) == 1000
    assert inv["lines"][0]["direct"] is True
    assert shop.stock(p["id"]) == 10  # no fake stock deduction


def test_direct_sale_requires_price(shop):
    r = shop.call("POST", "/invoices", json={"lines": [{"quantity": "1", "label": "Pain"}]})
    assert r.status_code == 422 and r.json()["code"] == "PRICE_REQUIRED"


def test_mixed_invoice_and_receipt_fields(shop):
    p = shop.product("Riz", base="Kg", price="750", stock="10")
    wtok, w = shop.worker()
    r = shop.call("POST", "/invoices", wtok, json={"lines": [
        {"product_id": p["id"], "quantity": "2"}, {"label": "Pain", "quantity": "3", "unit_price": "100", "unit_name": "pièce"}]})
    inv = r.json()
    assert inv["kind"] == "MIXED" and D(inv["total"]) == 1800
    assert inv["worker"]["name"] == w["name"] and inv["created_at"] and inv["shop"]["name"] == "Alimentation Diawara"


def test_idempotent_client_ref_no_duplicate(shop):
    body = {"lines": [{"quantity": "1", "unit_price": "100"}], "client_ref": "abc-123"}
    a = shop.call("POST", "/invoices", json=body).json()
    b = shop.call("POST", "/invoices", json=body).json()
    assert a["id"] == b["id"] and len(shop.call("GET", "/invoices").json()) == 1


def test_void_keeps_numbering_gapless_forward(shop):
    a = direct(shop).json()
    shop.call("POST", f"/invoices/{a['id']}/void", json={"reason": "erreur", "admin_password": "admin-secret-9"})
    b = direct(shop).json()
    assert b["receipt_no"] == f"REC-{YEAR}-00002"


def test_printable_receipt_sizes(shop):
    inv = direct(shop, label="Pain").json()
    for size in ("58", "80", "A4"):
        r = shop.c.get(f"/api/v1/invoices/{inv['id']}/receipt.html", params={"size": size, "access_token": shop.owner})
        assert r.status_code == 200 and inv["receipt_no"] in r.text and "Pain" in r.text
    assert "@page{size:58mm auto" in shop.c.get(f"/api/v1/invoices/{inv['id']}/receipt.html",
                                               params={"size": "58", "access_token": shop.owner}).text
