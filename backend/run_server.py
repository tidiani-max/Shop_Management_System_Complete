"""Entry point used by Electron / PyInstaller:  run_server.py --port 8765"""
import argparse
import multiprocessing

import uvicorn

from app.main import app

if __name__ == "__main__":
    multiprocessing.freeze_support()
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning")
