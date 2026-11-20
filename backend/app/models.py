"""Database models. Money and quantities are exact Decimals stored as TEXT
(SQLite has no native decimal; floats are never used)."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

ZERO = Decimal("0")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DecText(TypeDecorator):
    """Exact decimal persisted as TEXT."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):  # noqa: ANN001
        if value is None:
            return None
        if isinstance(value, float):
            raise TypeError("floats are not allowed for money/quantities")
        return format(Decimal(value), "f")

    def process_result_value(self, value, dialect):  # noqa: ANN001
        return None if value is None else Decimal(value)


class UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):  # noqa: ANN001
        if value is None:
            return None
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):  # noqa: ANN001
        return None if value is None else value.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------- users
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String(12))  # DDS_ADMIN | OWNER | WORKER
    name: Mapped[str] = mapped_column(String(120))
    username: Mapped[str] = mapped_column(String(60), unique=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recovery_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    can_receive_stock: Mapped[bool] = mapped_column(Boolean, default=True)
    can_sell_credit: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)


class LockoutCounter(Base):
    """Brute-force protection for logins and the owner admin password."""

    __tablename__ = "lockouts"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    fails: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class Counter(Base):
    __tablename__ = "counters"
    name: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=0)


# ------------------------------------------------------------- catalog
class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name_fr: Mapped[str] = mapped_column(String(160))
    name_ar: Mapped[str | None] = mapped_column(String(160), nullable=True)
    category: Mapped[str | None] = mapped_column(String(60), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(60), nullable=True)
    base_unit: Mapped[str] = mapped_column(String(40))
    price: Mapped[Decimal] = mapped_column(DecText)  # per BASE unit
    cost: Mapped[Decimal] = mapped_column(DecText, default=ZERO)  # per BASE unit
    stock_qty: Mapped[Decimal] = mapped_column(DecText, default=ZERO)  # in BASE units
    low_stock_threshold: Mapped[Decimal] = mapped_column(DecText, default=Decimal("5"))
    color: Mapped[str | None] = mapped_column(String(12), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    units: Mapped[list["ProductUnit"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductUnit.factor"
    )


class ProductUnit(Base):
    """A way to buy/sell a product. factor = how many BASE units in one of this unit."""

    __tablename__ = "product_units"
    __table_args__ = (UniqueConstraint("product_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    name: Mapped[str] = mapped_column(String(40))
    factor: Mapped[Decimal] = mapped_column(DecText)
    price: Mapped[Decimal | None] = mapped_column(DecText, nullable=True)  # optional fixed price
    product: Mapped[Product] = relationship(back_populates="units")


class StockMovement(Base):
    __tablename__ = "stock_movements"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # RECEIVE|SALE|VOID_REVERSAL|ADJUST
    qty_base: Mapped[Decimal] = mapped_column(DecText)  # signed
    unit_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    unit_qty: Mapped[Decimal | None] = mapped_column(DecText, nullable=True)
    unit_cost: Mapped[Decimal | None] = mapped_column(DecText, nullable=True)  # per base
    ref_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)


# ------------------------------------------------------------- parties
class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


# ------------------------------------------------------------ invoices
class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_no: Mapped[str] = mapped_column(String(24), unique=True)
    year: Mapped[int] = mapped_column(Integer)
    seq: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(10))  # CATALOG | DIRECT | MIXED
    status: Mapped[str] = mapped_column(String(10), default="COMPLETED")  # COMPLETED | VOIDED
    worker_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    total: Mapped[Decimal] = mapped_column(DecText)
    paid_amount: Mapped[Decimal] = mapped_column(DecText)
    payment_method: Mapped[str] = mapped_column(String(10))  # cash|orange|moov|wave|credit
    paid_method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    client_ref: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    voided_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    voided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice", order_by="InvoiceLine.id"
    )
    __table_args__ = (UniqueConstraint("year", "seq"),)


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    label: Mapped[str] = mapped_column(String(160))
    unit_name: Mapped[str] = mapped_column(String(40))
    unit_qty: Mapped[Decimal] = mapped_column(DecText)
    factor: Mapped[Decimal] = mapped_column(DecText, default=Decimal("1"))
    base_qty: Mapped[Decimal] = mapped_column(DecText)
    unit_price: Mapped[Decimal] = mapped_column(DecText)
    line_total: Mapped[Decimal] = mapped_column(DecText)
    cost_total: Mapped[Decimal] = mapped_column(DecText, default=ZERO)  # snapshot for profit
    price_overridden: Mapped[bool] = mapped_column(Boolean, default=False)
    invoice: Mapped[Invoice] = relationship(back_populates="lines")


# ------------------------------------------------------------- finance
class LedgerEntry(Base):
    """Every movement of money. account CASH or MOBILE; amount is signed."""

    __tablename__ = "ledger"
    id: Mapped[int] = mapped_column(primary_key=True)
    account: Mapped[str] = mapped_column(String(8))  # CASH | MOBILE
    method: Mapped[str] = mapped_column(String(10))  # cash|orange|moov|wave
    amount: Mapped[Decimal] = mapped_column(DecText)
    kind: Mapped[str] = mapped_column(String(20))
    # SALE|DEBT_REPAYMENT|EXPENSE|SUPPLIER_PAYMENT|STOCK_PURCHASE|VOID_REVERSAL|OPENING|ADJUSTMENT
    ref_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)

    __table_args__ = (Index("ix_ledger_ref", "ref_type", "ref_id"),)


class Expense(Base):
    __tablename__ = "expenses"
    id: Mapped[int] = mapped_column(primary_key=True)
    description: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(60), nullable=True)
    amount: Mapped[Decimal] = mapped_column(DecText)
    method: Mapped[str] = mapped_column(String(10))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)


class Debt(Base):
    """RECEIVABLE = a customer owes the shop. PAYABLE = the shop owes a supplier."""

    __tablename__ = "debts"
    id: Mapped[int] = mapped_column(primary_key=True)
    direction: Mapped[str] = mapped_column(String(10))  # RECEIVABLE | PAYABLE
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    original_amount: Mapped[Decimal] = mapped_column(DecText)
    balance: Mapped[Decimal] = mapped_column(DecText)
    status: Mapped[str] = mapped_column(String(10), default="OPEN")  # OPEN|PAID|CANCELLED
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class DebtPayment(Base):
    __tablename__ = "debt_payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    debt_id: Mapped[int] = mapped_column(ForeignKey("debts.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(DecText)
    method: Mapped[str] = mapped_column(String(10))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class RegisterSession(Base):
    __tablename__ = "register_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(8), default="OPEN")  # OPEN | CLOSED
    opened_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    opened_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    opening_cash: Mapped[Decimal] = mapped_column(DecText)
    opening_mobile: Mapped[Decimal] = mapped_column(DecText, default=ZERO)
    closed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    expected_cash: Mapped[Decimal | None] = mapped_column(DecText, nullable=True)
    expected_mobile: Mapped[Decimal | None] = mapped_column(DecText, nullable=True)
    counted_cash: Mapped[Decimal | None] = mapped_column(DecText, nullable=True)
    counted_mobile: Mapped[Decimal | None] = mapped_column(DecText, nullable=True)
    diff_cash: Mapped[Decimal | None] = mapped_column(DecText, nullable=True)
    diff_mobile: Mapped[Decimal | None] = mapped_column(DecText, nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)


class AuditLog(Base):
    """Append-only, hash-chained. UPDATE/DELETE are blocked by SQLite triggers."""

    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    action: Mapped[str] = mapped_column(String(40), index=True)
    entity: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


class CustomerBalanceEntry(Base):
    """Append-only ledger of money a customer holds WITH the shop (advance / deposit).
    amount is signed: DEPOSIT +, APPLY -, REFUND -, VOID_RETURN +. Balance = SUM(amount)."""

    __tablename__ = "customer_balance_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    kind: Mapped[str] = mapped_column(String(12))  # DEPOSIT | APPLY | REFUND | VOID_RETURN
    amount: Mapped[Decimal] = mapped_column(DecText)
    method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    debt_id: Mapped[int | None] = mapped_column(ForeignKey("debts.id"), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
