// Electron main process: starts the bundled FastAPI+SQLite server on 127.0.0.1,
// waits for /api/v1/health, then opens the React app. 100% offline.
const { app, BrowserWindow, dialog, ipcMain, Menu } = require("electron");
const { spawn, execFile } = require("child_process");
const http = require("http");
const net = require("net");
const path = require("path");
const fs = require("fs");

let backend = null;
let win = null;
let port = 0;

if (!app.requestSingleInstanceLock()) app.quit();
app.on("second-instance", () => {
  if (win) {
    if (win.isMinimized()) win.restore();
    win.focus();
  }
});

function freePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.listen(0, "127.0.0.1", () => {
      const p = srv.address().port;
      srv.close(() => resolve(p));
    });
    srv.on("error", reject);
  });
}

function backendCommand(p) {
  if (app.isPackaged) {
    const exe = process.platform === "win32" ? "shop-server.exe" : "shop-server";
    return {
      cmd: path.join(process.resourcesPath, "backend", exe),
      args: ["--port", String(p)],
      cwd: path.join(process.resourcesPath, "backend"),
    };
  }
  // development: python backend/run_server.py
  const root = path.join(__dirname, "..", "backend");
  const venvPy =
    process.platform === "win32"
      ? path.join(root, ".venv", "Scripts", "python.exe")
      : path.join(root, ".venv", "bin", "python");
  const py = process.env.PYTHON || (fs.existsSync(venvPy) ? venvPy : process.platform === "win32" ? "python" : "python3");
  return { cmd: py, args: [path.join(root, "run_server.py"), "--port", String(p)], cwd: root };
}

function startBackend(p) {
  const { cmd, args, cwd } = backendCommand(p);
  // The SQLite database lives in the OS user-data folder (AppData / Application Support):
  // updating or reinstalling the app never touches shop records.
  const dataDir = app.getPath("userData");
  fs.mkdirSync(dataDir, { recursive: true });
  const logFile = fs.createWriteStream(path.join(dataDir, "server.log"), { flags: "a" });
  backend = spawn(cmd, args, { cwd, env: { ...process.env, SHOP_DATA_DIR: dataDir }, windowsHide: true });
  backend.stdout.pipe(logFile);
  backend.stderr.pipe(logFile);
  backend.on("exit", (code) => {
    backend = null;
    if (!app.isQuitting) {
      dialog.showErrorBox(
        "Serveur local arrêté",
        `Le serveur s'est arrêté (code ${code}). Consultez server.log dans:\n${dataDir}`,
      );
      app.quit();
    }
  });
}

function waitForHealth(p, tries = 120) {
  return new Promise((resolve, reject) => {
    const retry = (n) => (n <= 0 ? reject(new Error("timeout")) : setTimeout(() => attempt(n - 1), 500));
    const attempt = (n) => {
      const req = http.get({ host: "127.0.0.1", port: p, path: "/api/v1/health", timeout: 1000 }, (res) => {
        res.resume();
        if (res.statusCode === 200) return resolve();
        retry(n);
      });
      req.on("error", () => retry(n));
      req.on("timeout", () => req.destroy());
    };
    attempt(tries);
  });
}

function killBackend() {
  if (!backend) return;
  const pid = backend.pid;
  try {
    if (process.platform === "win32") execFile("taskkill", ["/pid", String(pid), "/T", "/F"]);
    else backend.kill("SIGTERM");
  } catch (_) {
    /* ignore */
  }
  backend = null;
}

async function createWindow() {
  win = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 380,
    backgroundColor: "#ffffff",
    title: "Shop Management",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  win.once("ready-to-show", () => win.show());
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" })); // never leave localhost
  win.webContents.on("will-navigate", (e, url) => {
    if (!url.startsWith(`http://127.0.0.1:${port}`)) e.preventDefault();
  });
  await win.loadURL(`http://127.0.0.1:${port}/`);
}

// ---- IPC: folder/file pickers (USB backups) and real printing (58 mm / 80 mm / A4)
ipcMain.handle("choose-folder", async () => {
  const r = await dialog.showOpenDialog(win, {
    title: "Dossier de sauvegarde (clé USB)",
    properties: ["openDirectory", "createDirectory"],
  });
  return r.canceled ? null : r.filePaths[0];
});
ipcMain.handle("choose-backup-file", async () => {
  const r = await dialog.showOpenDialog(win, {
    title: "Choisir une sauvegarde",
    properties: ["openFile"],
    filters: [{ name: "SQLite", extensions: ["db"] }],
  });
  return r.canceled ? null : r.filePaths[0];
});

function paperHeightPx() {
  return win.webContents.executeJavaScript(
    `(() => { const el = document.querySelector('.paper'); return el ? Math.ceil(el.scrollHeight) + 8 : 800; })()`,
  );
}
const MM = { 58: 58, 80: 80 };

ipcMain.handle("print-receipt", async (_e, size) => {
  const opts = { silent: false, printBackground: true, margins: { marginType: "none" } };
  if (size === "A4") opts.pageSize = "A4";
  else {
    const hPx = await paperHeightPx();
    opts.pageSize = { width: MM[size] * 1000, height: Math.round(hPx * 264.583) }; // microns
  }
  return new Promise((resolve) => win.webContents.print(opts, (ok) => resolve(ok)));
});

ipcMain.handle("save-pdf", async (_e, size, name) => {
  const r = await dialog.showSaveDialog(win, {
    defaultPath: `${name || "recu"}.pdf`,
    filters: [{ name: "PDF", extensions: ["pdf"] }],
  });
  if (r.canceled || !r.filePath) return null;
  const opts = { printBackground: true, margins: { marginType: "none" } };
  if (size === "A4") opts.pageSize = "A4";
  else {
    const hPx = await paperHeightPx();
    opts.pageSize = { width: MM[size] / 25.4, height: hPx / 96 }; // inches
  }
  fs.writeFileSync(r.filePath, await win.webContents.printToPDF(opts));
  return r.filePath;
});

app.whenReady().then(async () => {
  Menu.setApplicationMenu(null);
  try {
    port = await freePort();
    startBackend(port);
    await waitForHealth(port);
    await createWindow();
  } catch (e) {
    dialog.showErrorBox(
      "Démarrage impossible",
      "Le serveur local n'a pas démarré. Consultez server.log dans le dossier de données de l'application.\n" + e.message,
    );
    killBackend();
    app.quit();
  }
});

app.on("before-quit", () => {
  app.isQuitting = true;
  killBackend();
});
app.on("window-all-closed", () => app.quit());
