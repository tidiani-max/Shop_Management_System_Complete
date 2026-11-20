const { contextBridge, ipcRenderer } = require("electron");
contextBridge.exposeInMainWorld("shopDesktop", {
  chooseFolder: () => ipcRenderer.invoke("choose-folder"),
  chooseBackupFile: () => ipcRenderer.invoke("choose-backup-file"),
  printReceipt: (size) => ipcRenderer.invoke("print-receipt", size),
  savePdf: (size, name) => ipcRenderer.invoke("save-pdf", size, name),
});
