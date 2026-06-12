// Pure config helpers for the desktop app (no Electron), so they're testable.

export function isValidUrl(u) {
  try {
    const x = new URL(u);
    return x.protocol === "http:" || x.protocol === "https:";
  } catch {
    return false;
  }
}

// The desktop app wraps the deployed web experience. Resolve which URL to load:
// explicit env wins, else the default local gateway.
export function resolveAppUrl(env = {}, fallback = "http://localhost:8000") {
  const url = env.WB_APP_URL || fallback;
  if (!isValidUrl(url)) {
    throw new Error(`invalid WB_APP_URL: ${url}`);
  }
  return url;
}

export function windowOptions() {
  return {
    width: 1100,
    height: 800,
    title: "Help Me Write Better",
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  };
}
