const { app, BrowserWindow, shell, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow;
let backendProcess;

function resolveBackendDir() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'backend');
  }
  return path.join(__dirname, '..', 'backend');
}

function resolveWebDist() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'web', 'dist', 'index.html');
  }
  return path.join(__dirname, '..', 'web', 'dist', 'index.html');
}

function startBackend() {
  const backendDir = resolveBackendDir();
  backendProcess = spawn('python', ['main.py'], {
    cwd: backendDir,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env },
  });

  backendProcess.stdout.on('data', d => process.stdout.write('[backend] ' + d));
  backendProcess.stderr.on('data', d => process.stderr.write('[backend] ' + d));

  backendProcess.on('exit', (code) => {
    if (code !== 0 && code !== null) {
      console.error(`Backend exited with code ${code}`);
    }
  });
}

function pollBackend(retries, resolve, reject) {
  if (retries <= 0) return reject(new Error('Backend did not start in time'));
  http.get('http://localhost:8000/sessions', res => {
    res.resume(); // consume body to free socket
    if (res.statusCode === 200) return resolve();
    setTimeout(() => pollBackend(retries - 1, resolve, reject), 1000);
  }).on('error', () => {
    setTimeout(() => pollBackend(retries - 1, resolve, reject), 1000);
  });
}

function waitForBackend() {
  return new Promise((resolve, reject) => pollBackend(30, resolve, reject));
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    backgroundColor: '#0f0c29',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
    },
    titleBarStyle: 'default',
    title: 'Zeus',
  });

  mainWindow.loadFile(resolveWebDist());

  // Open external links in default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

app.whenReady().then(async () => {
  startBackend();
  try {
    await waitForBackend();
    createWindow();
  } catch (e) {
    console.error('Backend failed to start:', e.message);
    dialog.showErrorBox(
      'Zeus — Backend Error',
      'Could not start the Zeus backend. Make sure Python is installed and accessible on PATH.'
    );
    app.quit();
  }
});

app.on('window-all-closed', () => {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
  app.quit();
});

app.on('will-quit', () => {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
});
