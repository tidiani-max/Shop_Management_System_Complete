"""Cash vs Mobile Money, credit sales/debts without double counting, register, backup/restore."""
from decimal import Decimal
from pathlib import Path

D = Decimal
ADMIN = "admin-secret-9"


def sale(shop, total="1000", method="cash", token=None, **extra):
    return shop.call("POST", "/invoices", token, json={"lines": [{"quantity": "1", "unit_price": total}],
                                                       "payment_method": method, **extra})


def test_cash_and_mobile_money_tracked_separately(shop):
    sale(shop, "1000", "cash")
    sale(shop, "2500", "orange")
    sale(shop, "700", "moov")
    sale(shop, "300", "wave")
    cash, mobile = shop.balances()
    assert cash == 1000 and mobile == 3500
    b = shop.call("GET", "/finance/balances").json()["by_method"]
    assert D(b["orange"]) == 2500 and D(b["moov"]) == 700 and D(b["wave"]) == 300
    shop.call("POST", "/finance/expenses", json={"description": "Transport", "amount": "400", "method": "cash"})
    assert shop.balances() == (600, 3500)
    shop.call("POST", "/finance/expenses", json={"description": "Recharge", "amount": "500", "method": "orange"})
    assert shop.balances() == (600, 3000)


def test_credit_sale_and_repayment_are_not_double_counted_as_revenue(shop):
    c = shop.call("POST", "/customers", json={"name": "Fatou Traoré"}).json()
    r = sale(shop, "10000", "credit", customer_id=c["id"], paid_amount="2000", paid_method="cash")
    assert r.status_code == 201 and D(r.json()["balance_due"]) == 8000
    assert shop.balances() == (2000, 0)                       # only the cash really received
    debts = shop.call("GET", "/finance/debts").json()
    assert D(debts["total_receivable"]) == 8000
    did = debts["items"][0]["id"]
    assert shop.call("POST", f"/finance/debts/{did}/payments", json={"amount": "3000", "method": "orange"}).status_code == 201
    assert shop.balances() == (2000, 3000)                    # repayment = money in ...
    s = shop.call("GET", "/reports/summary").json()
    assert D(s["revenue"]) == 10000                           # ... but revenue stays 10 000 (counted once)
    assert D(s["cash_in_from_debt_repayments"]) == 3000 and D(s["cash_in_from_sales"]) == 2000
    assert D(shop.call("GET", "/finance/debts").json()["total_receivable"]) == 5000
    over = shop.call("POST", f"/finance/debts/{did}/payments", json={"amount": "9999"})
    assert over.status_code == 422
    shop.call("POST", f"/finance/debts/{did}/payments", json={"amount": "5000"})
    assert shop.call("GET", "/finance/debts").json()["items"] == []  # settled


def test_credit_sale_requires_customer(shop):
    r = sale(shop, "500", "credit")
    assert r.status_code == 422 and r.json()["code"] == "CUSTOMER_REQUIRED"


def test_voiding_credit_sale_cancels_debt_and_refunds_repayments(shop):
    c = shop.call("POST", "/customers", json={"name": "Moussa"}).json()
    inv = sale(shop, "10000", "credit", customer_id=c["id"], paid_amount="1000").json()
    did = shop.call("GET", "/finance/debts").json()["items"][0]["id"]
    shop.call("POST", f"/finance/debts/{did}/payments", json={"amount": "4000", "method": "cash"})
    assert shop.balances()[0] == 5000
    r = shop.call("POST", f"/invoices/{inv['id']}/void", json={"reason": "retour client", "admin_password": ADMIN})
    assert r.status_code == 200
    assert shop.balances() == (0, 0)
    assert shop.call("GET", "/finance/debts").json()["items"] == []
    assert D(shop.call("GET", "/reports/summary").json()["revenue"]) == 0


def test_manual_debt_and_supplier_payable(shop):
    d = shop.call("POST", "/finance/debts", json={"party_name": "Awa Diallo", "amount": "45000"}).json()
    assert d["direction"] == "RECEIVABLE" and shop.balances() == (0, 0)   # no cash / revenue effect
    sup = shop.call("POST", "/suppliers", json={"name": "Grossiste Sogoniko"}).json()
    p = shop.product("Riz", base="Kg", price="750")
    r = shop.call("POST", "/stock/receive", json={"product_id": p["id"], "quantity": "10", "unit_cost": "500",
                                                  "supplier_id": sup["id"], "pay_method": "credit"})
    assert r.status_code == 201
    debts = shop.call("GET", "/finance/debts?direction=PAYABLE").json()
    assert D(debts["total_payable"]) == 5000 and shop.balances() == (0, 0)
    shop.call("POST", f"/finance/debts/{debts['items'][0]['id']}/payments", json={"amount": "2000", "method": "cash"})
    assert shop.balances()[0] == -2000


def test_weighted_average_cost_and_profit(shop):
    p = shop.product("Riz", base="Kg", price="750", units=[{"name": "Sac", "factor": "50"}])
    shop.call("POST", "/stock/receive", json={"product_id": p["id"], "unit_name": "Sac", "quantity": "1", "unit_cost": "25000"})
    prods = shop.call("GET", "/products").json()
    assert D(prods[0]["cost"]) == 500
    sale_ = shop.call("POST", "/invoices", json={"lines": [{"product_id": p["id"], "quantity": "10"}]}).json()
    s = shop.call("GET", "/reports/summary").json()
    assert D(s["gross_profit_catalog"]) == 7500 - 5000 and D(sale_["total"]) == 7500


def test_daily_register_open_close_reconciliation(shop):
    assert shop.call("GET", "/finance/register/current").json() is None
    wtok, _ = shop.worker()
    r = shop.call("POST", "/finance/register/open", wtok, json={"opening_cash": "5000"})
    assert r.status_code == 201
    assert shop.call("POST", "/finance/register/open", json={"opening_cash": "1"}).status_code == 409
    sale(shop, "2000", "cash", token=wtok)
    r = shop.call("POST", "/finance/register/close", wtok, json={"counted_cash": "1900", "counted_mobile": "0"})
    reg = r.json()
    assert reg["status"] == "CLOSED" and D(reg["expected_cash"]) == 2000 and D(reg["diff_cash"]) == -100
    assert shop.call("POST", "/finance/register/close", json={"counted_cash": "0"}).status_code == 409


def test_backup_export_and_restore_roundtrip(shop, tmp_path):
    usb = tmp_path / "usb"
    usb.mkdir()
    sale(shop, "1000")
    r = shop.call("POST", "/backup/export", json={"target_dir": str(usb)})
    assert r.status_code == 200
    f = Path(r.json()["file"])
    assert f.exists() and f.parent == usb and f.stat().st_size > 0
    sale(shop, "5000")
    assert len(shop.call("GET", "/invoices").json()) == 2
    # wrong / missing admin password
    bad = shop.call("POST", "/backup/restore-path", json={"path": str(f), "admin_password": "wrong-pass"})
    assert bad.status_code == 403
    ok = shop.call("POST", "/backup/restore-path", json={"path": str(f), "admin_password": ADMIN})
    assert ok.status_code == 200, ok.text
    again = shop.c.post("/api/v1/auth/login", json={"identifier": shop.owner_user["username"], "password": "owner-pass-1"}).json()
    inv = shop.call("GET", "/invoices", again["token"]).json()
    assert len(inv) == 1 and D(inv[0]["total"]) == 1000
    # next receipt continues after the restored counter (no duplicates)
    nxt = sale(shop, "10", token=again["token"]).json()
    assert nxt["receipt_no"].endswith("00002")


def test_restore_rejects_non_backup_file(shop, tmp_path):
    junk = tmp_path / "junk.db"
    junk.write_bytes(b"not a database at all")
    r = shop.call("POST", "/backup/restore-path", json={"path": str(junk), "admin_password": ADMIN})
    assert r.status_code == 422 and r.json()["code"] == "BAD_BACKUP"
    assert shop.call("GET", "/finance/balances").status_code == 200  # live DB untouched


def test_backup_download_and_worker_blocked(shop):
    r = shop.call("GET", "/backup/download")
    assert r.status_code == 200 and r.content[:15] == b"SQLite format 3"
