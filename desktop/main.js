const { app, BrowserWindow } = require('electron');
const path = require('path');

function createOverlayWindow() {
  const win = new BrowserWindow({
    width: 420,
    height: 640,
    minWidth: 340,
    minHeight: 480,
    alwaysOnTop: true,       // stays visible over the call app
    frame: true,              // set to false later for a borderless look
    resizable: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true, // security: renderer can't touch Node directly
      nodeIntegration: false,
    },
  });

  win.loadFile(path.join(__dirname, 'renderer', 'index.html'));
}

app.whenReady().then(() => {
  createOverlayWindow();

  // Auto-approve microphone permission requests — Electron blocks
  // getUserMedia by default unless explicitly allowed like this.
  const { session } = require('electron');
  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    if (permission === 'media') {
      callback(true);
    } else {
      callback(false);
    }
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createOverlayWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});