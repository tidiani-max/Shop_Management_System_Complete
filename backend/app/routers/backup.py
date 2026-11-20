"""One-click backup / restore of the SQLite database (USB friendly)."""
from __future__ import annotations

import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from .. import config, security
from ..db import get_db, reset_engine
from ..errors import ApiError
from ..models import User
from ..services import audit

router = APIRouter(prefix="/backup", tags=["backup"])
owner_only = security.require_roles(security.OWNER)
owner_or_admin = security.require_roles(security.OWNER, security.DDS)


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def make_backup_file(dest: Path) -> Path:
    """Consistent online copy using SQLite's backup API (safe while the app is running)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(config.db_path()))
    out = sqlite3.connect(str(dest))
    try:
        src.backup(out)
    finally:
        out.close()
        src.close()
    return dest


class ExportIn(BaseModel):
    target_dir: str | None = None  # e.g. the USB drive folder chosen in the native dialog


@router.post("/export")
def export_backup(body: ExportIn, db: Session = Depends(get_db), user: User = Depends(owner_or_admin)):
    name = f"shop-backup-{_stamp()}.db"
    target = Path(body.target_dir).expanduser() if body.target_dir else config.backups_dir()
    if not target.exists() or not target.is_dir():
        raise ApiError(422, "BAD_TARGET", "Dossier de destination introuvable (clé USB branchée ?).")
    try:
        path = make_backup_file(target / name)
    except OSError as e:
        raise ApiError(500, "BACKUP_FAILED", f"Impossible d'écrire la sauvegarde: {e}")
    audit.log(db, user, "BACKUP_CREATED", "backup", name, details={"dir": str(target)})
    return {"file": str(path), "name": name, "size": path.stat().st_size}


@router.get("/download")
def download_backup(db: Session = Depends(get_db), user: User = Depends(owner_or_admin)):
    tmp = Path(tempfile.mkdtemp()) / f"shop-backup-{_stamp()}.db"
    make_backup_file(tmp)
    audit.log(db, user, "BACKUP_DOWNLOADED", "backup", tmp.name)
    db.commit()
    return FileResponse(tmp, filename=tmp.name, media_type="application/octet-stream",
                        background=BackgroundTask(shutil.rmtree, tmp.parent, True))


@router.get("/list")
def list_backups(user: User = Depends(owner_or_admin)):
    return [{"name": p.name, "size": p.stat().st_size, "path": str(p)}
            for p in sorted(config.backups_dir().glob("shop-backup-*.db"), reverse=True)]


def validate_backup(path: Path) -> None:
    try:
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            if c.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ApiError(422, "BAD_BACKUP", "Fichier de sauvegarde corrompu.")
            tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            c.close()
    except sqlite3.DatabaseError:
        raise ApiError(422, "BAD_BACKUP", "Ce fichier n'est pas une sauvegarde valide.")
    if not {"users", "invoices", "ledger", "audit_log", "alembic_version"} <= tables:
        raise ApiError(422, "BAD_BACKUP", "Ce fichier n'est pas une sauvegarde de cette application.")


def restore_from(path: Path) -> None:
    """Copy `path` INTO the live database with the backup API (no file swap while open)."""
    validate_backup(path)
    safety = config.backups_dir() / f"pre-restore-{_stamp()}.db"
    make_backup_file(safety)
    reset_engine()
    src = sqlite3.connect(str(path))
    dst = sqlite3.connect(str(config.db_path()))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    reset_engine()


@router.post("/restore")
async def restore_backup(admin_password: str, file: UploadFile = File(...), db: Session = Depends(get_db),
                         user: User = Depends(owner_only)):
    security.verify_admin_password(db, user, admin_password)
    tmp = Path(tempfile.mkdtemp()) / "upload.db"
    with open(tmp, "wb") as f:
        shutil.copyfileobj(file.file, f)
    validate_backup(tmp)
    audit.log(db, user, "BACKUP_RESTORE_STARTED", "backup", file.filename)
    db.commit()
    db.close()
    restore_from(tmp)
    shutil.rmtree(tmp.parent, ignore_errors=True)
    from ..migrate import upgrade
    upgrade()
    return {"ok": True, "message": "Sauvegarde restaurée. Veuillez vous reconnecter."}


class RestorePath(BaseModel):
    path: str
    admin_password: str


@router.post("/restore-path")
def restore_backup_path(body: RestorePath, db: Session = Depends(get_db), user: User = Depends(owner_only)):
    """Restore from a file path chosen in the native dialog (USB stick)."""
    security.verify_admin_password(db, user, body.admin_password)
    p = Path(body.path).expanduser()
    if not p.is_file():
        raise ApiError(422, "BAD_TARGET", "Fichier introuvable.")
    validate_backup(p)
    audit.log(db, user, "BACKUP_RESTORE_STARTED", "backup", p.name)
    db.commit()
    db.close()
    restore_from(p)
    from ..migrate import upgrade
    upgrade()
    return {"ok": True, "message": "Sauvegarde restaurée. Veuillez vous reconnecter."}
