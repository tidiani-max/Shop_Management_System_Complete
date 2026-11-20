"""SQLite engine: WAL mode, foreign keys, BEGIN IMMEDIATE so that every write
transaction is serialised (no lost updates on stock or receipt counters)."""
from __future__ import annotations

from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from . import config

_engine: Engine | None = None
_Session: sessionmaker | None = None


def _make_engine(path: str) -> Engine:
    eng = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False, "timeout": 30},
        pool_pre_ping=False,
    )

    @event.listens_for(eng, "connect")
    def _on_connect(dbapi_conn, _rec):  # noqa: ANN001
        dbapi_conn.isolation_level = None  # we control BEGIN ourselves
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.close()

    @event.listens_for(eng, "begin")
    def _on_begin(conn):  # noqa: ANN001
        conn.exec_driver_sql("BEGIN IMMEDIATE")

    return eng


def get_engine() -> Engine:
    global _engine, _Session
    if _engine is None:
        _engine = _make_engine(str(config.db_path()))
        _Session = sessionmaker(bind=_engine, expire_on_commit=False, autoflush=True)
    return _engine


def reset_engine() -> None:
    """Dispose the engine (used by tests and by backup restore)."""
    global _engine, _Session
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _Session = None


def get_db() -> Iterator[Session]:
    get_engine()
    assert _Session is not None
    db = _Session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def session_factory() -> Session:
    get_engine()
    assert _Session is not None
    return _Session()
