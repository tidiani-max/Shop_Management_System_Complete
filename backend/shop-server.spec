# PyInstaller spec: one folder with shop-server(.exe) + alembic scripts + built React app
from PyInstaller.utils.hooks import collect_submodules

hidden = (
    collect_submodules("uvicorn")
    + collect_submodules("app")
    + collect_submodules("argon2")
    + collect_submodules("sqlalchemy.dialects.sqlite")
    + collect_submodules("alembic")
    + ["multipart", "python_multipart", "email.mime.multipart"]
)
a = Analysis(
    ["run_server.py"],
    pathex=["."],
    datas=[("alembic", "alembic"), ("frontend_dist", "frontend_dist")],
    hiddenimports=hidden,
    excludes=["tkinter", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="shop-server", console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="shop-server")
