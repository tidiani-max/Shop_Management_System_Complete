from alembic import context
from sqlalchemy import create_engine

from app.models import Base

target_metadata = Base.metadata


def run_migrations_online() -> None:
    url = context.config.get_main_option("sqlalchemy.url")
    engine = create_engine(url, connect_args={"timeout": 30})
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        context.configure(connection=conn, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
        conn.commit()  # SQLAlchemy 2.x: persist alembic_version (otherwise migrations re-run on every start)
    engine.dispose()


run_migrations_online()
