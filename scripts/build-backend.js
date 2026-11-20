// Builds the React app into the backend bundle, then freezes FastAPI with PyInstaller.
// Run on the TARGET OS (Windows -> shop-server.exe, macOS -> mac server binary).
const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
const backend = path.join(root, "backend");
const dist = path.join(root, "frontend", "dist");
if (!fs.existsSync(dist)) {
  console.error("frontend/dist missing: run `npm run build:frontend` first");
  process.exit(1);
}
fs.rmSync(path.join(backend, "frontend_dist"), { recursive: true, force: true });
fs.cpSync(dist, path.join(backend, "frontend_dist"), { recursive: true });

const bin = process.platform === "win32" ? path.join(backend, ".venv", "Scripts") : path.join(backend, ".venv", "bin");
const venvPy = path.join(bin, process.platform === "win32" ? "python.exe" : "python");
const py = process.env.PYTHON || (fs.existsSync(venvPy) ? venvPy : process.platform === "win32" ? "python" : "python3");
const r = spawnSync(py, ["-m", "PyInstaller", "--noconfirm", "--clean", "shop-server.spec"], {
  cwd: backend,
  stdio: "inherit",
});
process.exit(r.status === null ? 1 : r.status);
