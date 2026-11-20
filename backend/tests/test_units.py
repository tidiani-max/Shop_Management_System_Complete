"""Multi-unit inventory: Carton -> Boîte -> Pièce, packs, Litre. Exact Decimal math."""
from decimal import Decimal

D = Decimal


def sale(shop, pid, unit, qty, token=None, price=None):
    line = {"product_id": pid, "unit_name": unit, "quantity": qty}
    if price is not None:
        line["unit_price"] = price
    return shop.call("POST", "/invoices", token, json={"lines": [line], "payment_method": "cash"})


def test_receive_5_cartons_of_12_packs_then_sell_2_packs(shop):
    p = shop.product("Lait", base="Paquet", price="500", units=[{"name": "Carton", "factor": "12"}])
    r = shop.call("POST", "/stock/receive", json={"product_id": p["id"], "unit_name": "Carton", "quantity": "5"})
    assert r.status_code == 201 and D(r.json()["added_base_qty"]) == 60
    assert shop.stock(p["id"]) == 60
    assert sale(shop, p["id"], "Paquet", "2").status_code == 201
    assert shop.stock(p["id"]) == 58


def test_carton_to_boite_to_piece_chain(shop):
    # base = Pièce ; Boîte = 10 Pièces ; Carton = 12 Boîtes = 120 Pièces
    p = shop.product("Savon", base="Pièce", price="35", units=[
        {"name": "Boîte", "factor": "10"}, {"name": "Carton", "factor": "120"}])
    shop.call("POST", "/stock/receive", json={"product_id": p["id"], "unit_name": "Carton", "quantity": "2"})
    assert shop.stock(p["id"]) == 240
    assert sale(shop, p["id"], "Boîte", "3").status_code == 201      # -30
    assert shop.stock(p["id"]) == 210
    assert sale(shop, p["id"], "Pièce", "5").status_code == 201      # -5
    assert shop.stock(p["id"]) == 205
    shop.call("POST", "/stock/receive", json={"product_id": p["id"], "unit_name": "Boîte", "quantity": "1"})
    assert shop.stock(p["id"]) == 215
    # unit prices default to base price x factor (35 x 10 = 350 per Boîte)
    inv = sale(shop, p["id"], "Boîte", "2").json()
    assert D(inv["lines"][0]["unit_price"]) == 350 and D(inv["total"]) == 700


def test_litre_with_fractions_is_exact(shop):
    p = shop.product("Huile", base="Litre", price="1200", units=[{"name": "Bidon 5L", "factor": "5"}])
    shop.call("POST", "/stock/receive", json={"product_id": p["id"], "unit_name": "Bidon 5L", "quantity": "3"})
    assert shop.stock(p["id"]) == 15
    for _ in range(3):  # 0.1 + 0.1 + 0.1 would drift with floats
        assert sale(shop, p["id"], "Litre", "0.1").status_code == 201
    assert shop.stock(p["id"]) == D("14.700")
    inv = sale(shop, p["id"], "Litre", "0.25").json()
    assert D(inv["total"]) == D("300.00")
    assert shop.stock(p["id"]) == D("14.450")


def test_kg_custom_unit_and_unknown_unit_rejected(shop):
    p = shop.product("Riz", base="Kg", price="750", units=[{"name": "Sac 50kg", "factor": "50"}])
    shop.call("POST", "/stock/receive", json={"product_id": p["id"], "unit_name": "Sac 50kg", "quantity": "1"})
    assert sale(shop, p["id"], "Kg", "2.5").status_code == 201
    assert shop.stock(p["id"]) == D("47.5")
    r = sale(shop, p["id"], "Tonne", "1")
    assert r.status_code == 422 and r.json()["code"] == "UNKNOWN_UNIT"


def test_insufficient_stock_blocks_and_changes_nothing(shop):
    p = shop.product("Sucre", base="Kg", price="650", stock="8")
    r = sale(shop, p["id"], "Kg", "9")
    assert r.status_code == 409 and r.json()["code"] == "INSUFFICIENT_STOCK"
    assert shop.stock(p["id"]) == 8
    assert shop.call("GET", "/invoices").json() == []


def test_invalid_factor_and_too_precise_quantity(shop):
    r = shop.call("POST", "/products", json={"name_fr": "X", "base_unit": "Pièce", "price": "1",
                                              "units": [{"name": "Carton", "factor": "0"}]})
    assert r.status_code == 422
    p = shop.product("Y", base="Pièce", price="10", stock="10")
    assert sale(shop, p["id"], "Pièce", "0.0001").status_code == 422
