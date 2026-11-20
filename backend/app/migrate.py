"""Run Alembic migrations programmatically (works inside the PyInstaller bundle)."""
from __future__ import annotations

from alembic import command
from alembic.config import Config

from . import config
from .db import get_engine


def alembic_config() -> Config:
    root = config.resource_dir()
    cfg = Config()
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{config.db_path()}")
    return cfg


def upgrade() -> None:
    get_engine().dispose()
    command.upgrade(alembic_config(), "head")
