"""DB-level immutability: invoices, ledger, stock movements and audit log can never be edited/deleted.

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

APPEND_ONLY = ["audit_log", "ledger", "stock_movements", "invoice_lines", "debt_payments"]


def upgrade() -> None:
    for t in APPEND_ONLY:
        op.execute(f"CREATE TRIGGER {t}_no_update BEFORE UPDATE ON {t} BEGIN SELECT RAISE(ABORT, '{t} is append-only'); END;")
        op.execute(f"CREATE TRIGGER {t}_no_delete BEFORE DELETE ON {t} BEGIN SELECT RAISE(ABORT, '{t} is append-only'); END;")
    op.execute("CREATE TRIGGER invoices_no_delete BEFORE DELETE ON invoices BEGIN SELECT RAISE(ABORT, 'invoices cannot be deleted'); END;")
    op.execute(
        """CREATE TRIGGER invoices_guard_update BEFORE UPDATE ON invoices
        WHEN NOT (OLD.status = 'COMPLETED' AND NEW.status = 'VOIDED'
                  AND OLD.receipt_no = NEW.receipt_no AND OLD.total = NEW.total
                  AND OLD.paid_amount = NEW.paid_amount AND OLD.worker_id = NEW.worker_id
                  AND OLD.created_at = NEW.created_at AND OLD.payment_method = NEW.payment_method
                  AND OLD.kind = NEW.kind AND OLD.year = NEW.year AND OLD.seq = NEW.seq)
        BEGIN SELECT RAISE(ABORT, 'completed invoices are immutable (only void is allowed)'); END;"""
    )


def downgrade() -> None:
    for t in APPEND_ONLY:
        op.execute(f"DROP TRIGGER IF EXISTS {t}_no_update")
        op.execute(f"DROP TRIGGER IF EXISTS {t}_no_delete")
    op.execute("DROP TRIGGER IF EXISTS invoices_no_delete")
    op.execute("DROP TRIGGER IF EXISTS invoices_guard_update")
