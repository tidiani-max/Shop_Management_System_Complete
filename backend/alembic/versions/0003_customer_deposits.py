"""Customer advance/deposit ledger (append-only) + debt guards.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa
import app.models

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_balance_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("amount", app.models.DecText(), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=True),
        sa.Column("debt_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", app.models.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["debt_id"], ["debts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("customer_balance_entries", schema=None) as b:
        b.create_index("ix_customer_balance_entries_customer_id", ["customer_id"], unique=False)
        b.create_index("ix_customer_balance_entries_created_at", ["created_at"], unique=False)
    t = "customer_balance_entries"
    op.execute(f"CREATE TRIGGER {t}_no_update BEFORE UPDATE ON {t} BEGIN SELECT RAISE(ABORT, '{t} is append-only'); END;")
    op.execute(f"CREATE TRIGGER {t}_no_delete BEFORE DELETE ON {t} BEGIN SELECT RAISE(ABORT, '{t} is append-only'); END;")
    # Customer credit records can never be deleted, and their identity/original amount never rewritten.
    op.execute("CREATE TRIGGER debts_no_delete BEFORE DELETE ON debts BEGIN SELECT RAISE(ABORT, 'debts cannot be deleted'); END;")
    op.execute(
        """CREATE TRIGGER debts_guard_update BEFORE UPDATE ON debts
        WHEN NOT (OLD.direction = NEW.direction AND OLD.original_amount = NEW.original_amount
                  AND OLD.customer_id IS NEW.customer_id AND OLD.supplier_id IS NEW.supplier_id
                  AND OLD.invoice_id IS NEW.invoice_id AND OLD.created_at = NEW.created_at)
        BEGIN SELECT RAISE(ABORT, 'debt identity and original amount are immutable'); END;"""
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS debts_guard_update")
    op.execute("DROP TRIGGER IF EXISTS debts_no_delete")
    op.execute("DROP TRIGGER IF EXISTS customer_balance_entries_no_update")
    op.execute("DROP TRIGGER IF EXISTS customer_balance_entries_no_delete")
    op.drop_table("customer_balance_entries")
