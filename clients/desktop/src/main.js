// Electron main process. Wraps the deployed web experience (the gateway's web
// UI), so all auth + plan-cap enforcement happens server-side — the desktop app
// is a thin shell. Set WB_APP_URL to your deployment.
import { app, BrowserWindow, shell } from "electron";
import { resolveAppUrl, windowOptions } from "./config.js";

function createWindow() {
  const win = new BrowserWindow(windowOptions());
  win.loadURL(resolveAppUrl(process.env));
  // Open external links in the user's browser, not inside the app shell.
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
