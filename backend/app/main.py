from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from . import config, security
from .db import get_engine, session_factory
from .errors import ApiError, api_error_handler
from .migrate import upgrade
from .models import User
from .routers import admin, auth, backup, catalog, finance, reports, sales, users


def ensure_dds_admin() -> None:
    """Create the platform admin once. Password comes from DDS_ADMIN_PASSWORD or is generated and
    written to <data dir>/DDS_ADMIN_CREDENTIALS.txt (readable only by the installing technician)."""
    db = session_factory()
    try:
        if db.execute(select(func.count()).select_from(User).where(User.role == "DDS_ADMIN")).scalar_one():
            return
        import os
        pw = os.environ.get("DDS_ADMIN_PASSWORD") or secrets.token_urlsafe(9)
        db.add(User(role="DDS_ADMIN", name="DDS Admin", username="dds-admin", phone="admin@dds.ml",
                    password_hash=security.hash_secret(pw), active=True))
        db.commit()
        if not os.environ.get("DDS_ADMIN_PASSWORD"):
            f = config.data_dir() / "DDS_ADMIN_CREDENTIALS.txt"
            f.write_text(f"username: dds-admin\npassword: {pw}\n(Delete this file after noting the password.)\n")
            try:
                f.chmod(0o600)
            except OSError:
                pass
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    upgrade()
    ensure_dds_admin()
    yield
    get_engine().dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="Shop Management API", version=config.APP_VERSION, lifespan=lifespan)
    app.add_exception_handler(ApiError, api_error_handler)
    # Only the local app window talks to this server (127.0.0.1); allow Vite dev + file/app origins.
    app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "null", "app://shop"],
                       allow_methods=["*"], allow_headers=["*"])

    @app.get(f"{config.API_PREFIX}/health")
    def health():
        return {"status": "ok", "version": config.APP_VERSION}

    for r in (auth, users, catalog, sales, finance, reports, backup, admin):
        app.include_router(r.router, prefix=config.API_PREFIX)

    # Serve the built React app when packaged (Electron loads http://127.0.0.1:PORT/)
    static = config.resource_dir() / "frontend_dist"
    if static.is_dir():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            f = (static / path).resolve()
            if path and f.is_file() and static.resolve() in f.parents:
                return FileResponse(f)
            return FileResponse(static / "index.html")
    return app


app = create_app()
