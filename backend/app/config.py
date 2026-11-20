"""Runtime configuration. The database lives in the OS user-data folder so that
application updates / re-installs never wipe the shop records."""
import os
import sys
from pathlib import Path

APP_NAME = "ShopManagement"
APP_VERSION = "1.0.0"
API_PREFIX = "/api/v1"
SESSION_HOURS = 24
ADMIN_MAX_FAILS = 5
ADMIN_LOCK_MINUTES = 5


def data_dir() -> Path:
    env = os.environ.get("SHOP_DATA_DIR")
    if env:
        p = Path(env)
    elif sys.platform == "win32":
        p = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / APP_NAME
    elif sys.platform == "darwin":
        p = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        p = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    return data_dir() / "shop.db"


def backups_dir() -> Path:
    p = data_dir() / "backups"
    p.mkdir(parents=True, exist_ok=True)
    return p


def resource_dir() -> Path:
    """Folder holding bundled resources (alembic scripts) - works in PyInstaller too."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent
