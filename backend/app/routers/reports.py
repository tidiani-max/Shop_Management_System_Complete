"""Owner dashboard + reports. Revenue = completed invoice totals ONLY
(debt repayments and stock purchases are cash movements, never revenue)."""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import security
from ..db import get_db
from ..models import Debt, Expense, Invoice, InvoiceLine, LedgerEntry, Product, RegisterSession, User
from ..services.finance import balances, local_tz, range_bounds, resolve_period
from ..services.units import ZERO

router = APIRouter(tags=["reports"])
owner_only = security.require_roles(security.OWNER)


def _period(db: Session, d_from: date | None, d_to: date | None) -> dict:
    a, b = range_bounds(d_from, d_to)
    invs = db.execute(select(Invoice).where(Invoice.created_at >= a, Invoice.created_at < b)).scalars().all()
    done = [i for i in invs if i.status == "COMPLETED"]
    revenue = sum((i.total for i in done), ZERO)
    cogs = ZERO
    direct_rev = ZERO
    prod_tot: dict[str, list] = defaultdict(lambda: [ZERO, ZERO])
    for i in done:
        for l in i.lines:
            cogs += l.cost_total
            if l.product_id is None:
                direct_rev += l.line_total
            t = prod_tot[l.label]
            t[0] += l.base_qty
            t[1] += l.line_total
    expenses = sum((e.amount for e in db.execute(select(Expense).where(Expense.created_at >= a, Expense.created_at < b)).scalars()), ZERO)
    led = list(db.execute(select(LedgerEntry).where(LedgerEntry.created_at >= a, LedgerEntry.created_at < b)).scalars())
    sale_cash_in = sum((e.amount for e in led if e.kind == "SALE"), ZERO)
    repay_in = sum((e.amount for e in led if e.kind == "DEBT_REPAYMENT"), ZERO)
    by_worker: dict[str, list] = defaultdict(lambda: [0, ZERO])
    names = {}
    for i in done:
        names.setdefault(i.worker_id, db.get(User, i.worker_id).name)
        by_worker[names[i.worker_id]][0] += 1
        by_worker[names[i.worker_id]][1] += i.total
    by_method: dict[str, object] = defaultdict(lambda: ZERO)
    for i in done:
        by_method[i.payment_method] += i.total
    best = sorted(prod_tot.items(), key=lambda kv: kv[1][1], reverse=True)[:5]
    return {
        "revenue": str(revenue), "invoices": len(done), "voided": len(invs) - len(done),
        "gross_profit_catalog": str(sum((l.line_total - l.cost_total for i in done for l in i.lines if l.product_id), ZERO)),
        "cogs_catalog": str(cogs), "direct_sales_revenue": str(direct_rev), "expenses": str(expenses),
        "cash_in_from_sales": str(sale_cash_in), "cash_in_from_debt_repayments": str(repay_in),
        "net": str(revenue - cogs - expenses),
        "by_worker": [{"worker": k, "invoices": v[0], "revenue": str(v[1])} for k, v in by_worker.items()],
        "by_payment_method": {k: str(v) for k, v in by_method.items()},
        "best_sellers": [{"label": k, "qty": str(v[0]), "revenue": str(v[1])} for k, v in best],
    }


@router.get("/reports/summary")
def summary(date_from: date | None = None, date_to: date | None = None, period: str | None = None,
            db: Session = Depends(get_db), user: User = Depends(owner_only)):
    a, b = resolve_period(period, date_from, date_to)
    return _period(db, a, b)


@router.get("/dashboard")
def dashboard(date_from: date | None = None, date_to: date | None = None, period: str | None = None,
              db: Session = Depends(get_db), user: User = Depends(owner_only)):
    date_from, date_to = resolve_period(period, date_from, date_to)
    a, b = range_bounds(date_from, date_to)
    per = _period(db, date_from, date_to)
    recv = _received(db, a, b)
    bal = balances(db)
    debts = list(db.execute(select(Debt).where(Debt.status == "OPEN")).scalars())
    all_products = list(db.execute(select(Product).where(Product.active == True)).scalars())  # noqa: E712
    low = [p for p in all_products if p.stock_qty <= p.low_stock_threshold]
    recv_ops = len([e for e in db.execute(select(LedgerEntry).where(
        LedgerEntry.created_at >= a, LedgerEntry.created_at < b,
        LedgerEntry.kind.in_(("SALE", "DEBT_REPAYMENT")))).scalars() if e.amount > 0])
    exp_count = len(list(db.execute(select(Expense).where(Expense.created_at >= a, Expense.created_at < b)).scalars()))
    recent = []
    for e in db.execute(select(LedgerEntry).where(LedgerEntry.created_at >= a, LedgerEntry.created_at < b)
                        .order_by(LedgerEntry.id.desc()).limit(8)).scalars():
        recent.append({"kind": e.kind, "amount": str(e.amount), "note": e.note, "method": e.method,
                       "created_at": e.created_at.isoformat()})
    return {
        "period": {"key": period or "day", "from": date_from.isoformat(), "to": date_to.isoformat()},
        "received": str(recv),
        "spent": per["expenses"], "available": str(bal["CASH"] + bal["MOBILE"]),
        "cash": str(bal["CASH"]), "mobile": str(bal["MOBILE"]),
        "balance": str(recv - _num(per["expenses"])),
        "receivables": str(sum((d.balance for d in debts if d.direction == "RECEIVABLE"), ZERO)),
        "payables": str(sum((d.balance for d in debts if d.direction == "PAYABLE"), ZERO)),
        "low_stock": [{"id": p.id, "name_fr": p.name_fr, "name_ar": p.name_ar, "stock_qty": str(p.stock_qty),
                       "base_unit": p.base_unit} for p in low],
        "best_sellers": per["best_sellers"], "recent": recent, "summary": per,
        "products_count": len(all_products),
        "low_count": len([p for p in all_products if 0 < p.stock_qty <= p.low_stock_threshold]),
        "out_count": len([p for p in all_products if p.stock_qty <= 0]),
        "receivable_people": len({d.customer_id for d in debts if d.direction == "RECEIVABLE"}),
        "payable_people": len({d.supplier_id for d in debts if d.direction == "PAYABLE"}),
        "received_ops": recv_ops, "expense_count": exp_count,
    }


def _num(s: str):
    from decimal import Decimal
    return Decimal(s)


def _received(db: Session, a, b):
    rows = db.execute(select(LedgerEntry).where(
        LedgerEntry.created_at >= a, LedgerEntry.created_at < b,
        LedgerEntry.kind.in_(("SALE", "DEBT_REPAYMENT")))).scalars()
    return sum((e.amount for e in rows if e.amount > 0), ZERO)


# --------------------------------------------------------------------------- insights
def _pct(profit: Decimal, revenue: Decimal) -> str:
    return str(round(profit * 100 / revenue, 1)) if revenue > 0 else "0"


@router.get("/reports/insights")
def insights(
    period: str | None = None, date_from: date | None = None, date_to: date | None = None,
    top: int = Query(20, ge=1, le=50), low_margin_pct: int = Query(10, ge=0, le=100),
    dead_days: int = Query(30, ge=0, le=365), overdue_days: int = Query(30, ge=0, le=365),
    velocity_days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db), user: User = Depends(owner_only),
):
    """Top sellers, peak hours and 'what is wrong / what to do' alerts. Uses the same invoice-line cost
    snapshots as the profit report, so numbers always match the rest of the app."""
    d_from, d_to = resolve_period(period, date_from, date_to)
    a, b = range_bounds(d_from, d_to)
    tz = local_tz()
    now = datetime.now(timezone.utc)
    products = {p.id: p for p in db.execute(select(Product)).scalars()}

    invs = [i for i in db.execute(select(Invoice).where(Invoice.created_at >= a, Invoice.created_at < b,
                                                        Invoice.status == "COMPLETED")).scalars()]
    # ---- per product totals + hourly buckets (catalog lines only: direct sales have no cost)
    agg: dict[int, dict] = {}
    hours = {h: {"hour": h, "invoices": 0, "revenue": ZERO} for h in range(24)}
    hour_prod: dict[int, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: ZERO))
    hour_cat: dict[int, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: ZERO))
    for i in invs:
        h = i.created_at.astimezone(tz).hour
        hours[h]["invoices"] += 1
        hours[h]["revenue"] += i.total
        for l in i.lines:
            if not l.product_id:
                continue
            t = agg.setdefault(l.product_id, {"qty": ZERO, "revenue": ZERO, "cost": ZERO, "loss_lines": ZERO})
            t["qty"] += l.base_qty
            t["revenue"] += l.line_total
            t["cost"] += l.cost_total
            if l.cost_total > l.line_total:
                t["loss_lines"] += l.cost_total - l.line_total
            p = products.get(l.product_id)
            hour_prod[h][l.label] += l.base_qty
            hour_cat[h][(p.category if p and p.category else "—")] += l.base_qty

    def row(pid: int, t: dict) -> dict:
        p = products.get(pid)
        profit = t["revenue"] - t["cost"]
        return {"product_id": pid, "label": p.name_fr if p else "?", "name_ar": p.name_ar if p else None,
                "base_unit": p.base_unit if p else "", "qty": str(t["qty"]), "revenue": str(t["revenue"]),
                "cost": str(t["cost"]), "profit": str(profit), "margin_pct": _pct(profit, t["revenue"])}

    rows = [row(pid, t) for pid, t in agg.items()]
    top_qty = sorted(rows, key=lambda r: (Decimal(r["qty"]), Decimal(r["profit"])), reverse=True)[:top]
    top_profit = sorted(rows, key=lambda r: (Decimal(r["profit"]), Decimal(r["qty"])), reverse=True)[:top]

    # ---- peak hours
    hour_list = [{"hour": h["hour"], "invoices": h["invoices"], "revenue": str(h["revenue"])} for h in hours.values()]
    ranked = sorted((h for h in hours.values() if h["invoices"] > 0),
                    key=lambda h: (h["revenue"], h["invoices"]), reverse=True)[:3]
    peak = []
    for h in ranked:
        hp = sorted(hour_prod[h["hour"]].items(), key=lambda kv: kv[1], reverse=True)[:3]
        hc = sorted(hour_cat[h["hour"]].items(), key=lambda kv: kv[1], reverse=True)[:3]
        peak.append({"hour": h["hour"], "invoices": h["invoices"], "revenue": str(h["revenue"]),
                     "top_products": [{"label": k, "qty": str(v)} for k, v in hp],
                     "top_categories": [{"category": k, "qty": str(v)} for k, v in hc]})

    # ---- diagnostics -------------------------------------------------------------
    alerts: list[dict] = []

    def add(kind: str, severity: str, items: list[dict], **extra):
        if items:
            alerts.append({"type": kind, "severity": severity, "count": len(items), "items": items, **extra})

    # 1. sold at a loss in the period
    add("LOSS_SALES", "high", [
        {**row(pid, t), "loss": str(t["loss_lines"])} for pid, t in agg.items() if t["loss_lines"] > 0])
    # 2. catalog price currently below cost
    add("PRICE_BELOW_COST", "high", [
        {"product_id": p.id, "label": p.name_fr, "price": str(p.price), "cost": str(p.cost)}
        for p in products.values() if p.active and p.cost > 0 and p.price < p.cost])
    # 3. abnormally low margin (still positive)
    lm = []
    for pid, t in agg.items():
        if t["revenue"] > 0 and t["loss_lines"] == 0 and t["cost"] > 0:
            pr = t["revenue"] - t["cost"]
            if pr * 100 / t["revenue"] < low_margin_pct:
                lm.append(row(pid, t))
    add("LOW_MARGIN", "medium", lm, threshold_pct=low_margin_pct)

    # 4. fast movers running low  (velocity over the last N days, independent of the selected period)
    v_start = now - timedelta(days=velocity_days)
    sold: dict[int, Decimal] = defaultdict(lambda: ZERO)
    last_sale: dict[int, datetime] = {}
    for l, created in db.execute(select(InvoiceLine, Invoice.created_at).join(Invoice, Invoice.id == InvoiceLine.invoice_id)
                                 .where(Invoice.status == "COMPLETED", InvoiceLine.product_id.is_not(None))):
        if created >= v_start:
            sold[l.product_id] += l.base_qty
        if l.product_id not in last_sale or created > last_sale[l.product_id]:
            last_sale[l.product_id] = created
    restock = []
    for pid, qty in sold.items():
        p = products.get(pid)
        if not p or not p.active or qty <= 0:
            continue
        per_day = qty / velocity_days
        days_left = (p.stock_qty / per_day) if p.stock_qty > 0 else Decimal(0)
        if days_left < 7 or p.stock_qty <= p.low_stock_threshold:
            need = max(Decimal(1), Decimal(math.ceil(per_day * 14 - p.stock_qty)))
            restock.append({"product_id": pid, "label": p.name_fr, "name_ar": p.name_ar, "base_unit": p.base_unit,
                            "stock_qty": str(p.stock_qty), "sold_per_day": str(round(per_day, 2)),
                            "days_left": str(round(days_left, 1)), "suggested_qty": str(need)})
    restock.sort(key=lambda r: Decimal(r["days_left"]))
    add("RESTOCK", "high" if any(Decimal(r["stock_qty"]) <= 0 for r in restock) else "medium", restock,
        cover_days=14)

    # 5. dead stock: on the shelf, old enough, nothing sold for `dead_days`
    cutoff = now - timedelta(days=dead_days)
    dead = []
    for p in products.values():
        if not p.active or p.stock_qty <= 0 or p.created_at > cutoff:
            continue
        ls = last_sale.get(p.id)
        if ls is None or ls <= cutoff:
            dead.append({"product_id": p.id, "label": p.name_fr, "name_ar": p.name_ar, "base_unit": p.base_unit,
                         "stock_qty": str(p.stock_qty), "stock_value": str(p.stock_qty * p.cost),
                         "days_since_sale": (now - ls).days if ls else None})
    dead.sort(key=lambda r: Decimal(r["stock_value"]), reverse=True)
    add("DEAD_STOCK", "low", dead, days=dead_days)

    # 6. unpaid customer credits older than `overdue_days`
    od_cut = now - timedelta(days=overdue_days)
    od = []
    from ..models import Customer
    for d in db.execute(select(Debt).where(Debt.direction == "RECEIVABLE", Debt.status == "OPEN")).scalars():
        if d.created_at <= od_cut:
            c = db.get(Customer, d.customer_id) if d.customer_id else None
            od.append({"debt_id": d.id, "party_name": c.name if c else "?", "phone": c.phone if c else None,
                       "balance": str(d.balance), "days": (now - d.created_at).days})
    od.sort(key=lambda r: r["days"], reverse=True)
    add("OVERDUE_CREDIT", "high" if any(r["days"] > 60 for r in od) else "medium", od, days=overdue_days,
        total=str(sum((Decimal(r["balance"]) for r in od), ZERO)))

    # 7. register open/close discrepancies (last 30 days)
    reg = []
    for r in db.execute(select(RegisterSession).where(RegisterSession.status == "CLOSED",
                                                      RegisterSession.closed_at >= now - timedelta(days=30))
                        .order_by(RegisterSession.id.desc())).scalars():
        if (r.diff_cash or ZERO) != 0 or (r.diff_mobile or ZERO) != 0:
            w = db.get(User, r.closed_by) if r.closed_by else None
            reg.append({"register_id": r.id, "closed_at": r.closed_at.isoformat(), "closed_by": w.name if w else None,
                        "diff_cash": str(r.diff_cash or ZERO), "diff_mobile": str(r.diff_mobile or ZERO)})
    add("REGISTER_DIFF", "high", reg)

    order = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(key=lambda x: order[x["severity"]])
    return {"period": {"key": period or "day", "from": d_from.isoformat(), "to": d_to.isoformat()},
            "top_by_qty": top_qty, "top_by_profit": top_profit,
            "hours": hour_list, "peak_hours": peak, "diagnostics": alerts}
