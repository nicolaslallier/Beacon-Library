/**
 * Beacon Library Desktop Sync Client - Main Process
 *
 * This Electron application provides:
 * - Background file synchronization with Beacon Library
 * - System tray integration
 * - Selective sync for chosen libraries/folders
 * - Conflict resolution
 * - Offline support with sync queue
 */

import { app, BrowserWindow, ipcMain, Menu, Tray, dialog, shell } from 'electron';
import * as path from 'path';
import Store from 'electron-store';
import { SyncService } from './sync-service';
import { AuthService } from './auth-service';
import { FileWatcher } from './file-watcher';

// Store for persistent settings
const store = new Store({
  defaults: {
    syncFolder: '',
    syncedLibraries: [],
    autoSync: true,
    syncInterval: 300000, // 5 minutes
    startMinimized: false,
    launchAtStartup: false,
  },
});

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let syncService: SyncService | null = null;
let authService: AuthService | null = null;
let fileWatcher: FileWatcher | null = null;

// Prevent multiple instances
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
    minWidth: 600,
    minHeight: 400,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, '../preload/preload.js'),
    },
    icon: path.join(__dirname, '../../resources/icon.png'),
    show: !store.get('startMinimized'),
  });

  // Load the renderer
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
  }

  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow?.hide();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function createTray() {
  const iconPath = path.join(__dirname, '../../resources/tray-icon.png');
  tray = new Tray(iconPath);

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Open Beacon Library Sync',
      click: () => {
        mainWindow?.show();
      },
    },
    {
      label: 'Sync Now',
      click: () => {
        syncService?.syncAll();
      },
    },
    { type: 'separator' },
    {
      label: 'Pause Sync',
      type: 'checkbox',
      checked: false,
      click: (menuItem) => {
        if (menuItem.checked) {
          syncService?.pause();
        } else {
          syncService?.resume();
        }
      },
    },
    { type: 'separator' },
    {
      label: 'Open Sync Folder',
      click: () => {
        const syncFolder = store.get('syncFolder') as string;
        if (syncFolder) {
          shell.openPath(syncFolder);
        }
      },
    },
    {
      label: 'Preferences',
      click: () => {
        mainWindow?.show();
        mainWindow?.webContents.send('navigate', '/settings');
      },
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        app.isQuitting = true;
        app.quit();
      },
    },
  ]);

  tray.setToolTip('Beacon Library Sync');
  tray.setContextMenu(contextMenu);

  tray.on('double-click', () => {
    mainWindow?.show();
  });
}

async function initializeServices() {
  const serverUrl = store.get('serverUrl') as string || 'http://localhost:8181';

  // Initialize auth service
  authService = new AuthService(store);

  // Initialize sync service
  syncService = new SyncService({
    serverUrl,
    syncFolder: store.get('syncFolder') as string,
    authService,
    store,
  });

  // Initialize file watcher
  fileWatcher = new FileWatcher({
    syncFolder: store.get('syncFolder') as string,
    onFileChange: (filePath, eventType) => {
      syncService?.queueSync(filePath, eventType);
    },
  });

  // Start auto-sync if enabled
  if (store.get('autoSync')) {
    syncService.startAutoSync(store.get('syncInterval') as number);
  }
}

// IPC Handlers
function setupIpcHandlers() {
  // Auth
  ipcMain.handle('auth:login', async (_, serverUrl: string) => {
    return authService?.login(serverUrl);
  });

  ipcMain.handle('auth:logout', async () => {
    return authService?.logout();
  });

  ipcMain.handle('auth:getStatus', async () => {
    return authService?.getStatus();
  });

  // Settings
  ipcMain.handle('settings:get', async (_, key: string) => {
    return store.get(key);
  });

  ipcMain.handle('settings:set', async (_, key: string, value: any) => {
    store.set(key, value);
    return true;
  });

  ipcMain.handle('settings:selectSyncFolder', async () => {
    const result = await dialog.showOpenDialog(mainWindow!, {
      properties: ['openDirectory', 'createDirectory'],
      title: 'Select Sync Folder',
    });

    if (!result.canceled && result.filePaths.length > 0) {
      const syncFolder = result.filePaths[0];
      store.set('syncFolder', syncFolder);

      // Update file watcher
      fileWatcher?.updateSyncFolder(syncFolder);

      return syncFolder;
    }
    return null;
  });

  // Sync
  ipcMain.handle('sync:getStatus', async () => {
    return syncService?.getStatus();
  });

  ipcMain.handle('sync:syncNow', async () => {
    return syncService?.syncAll();
  });

  ipcMain.handle('sync:pause', async () => {
    syncService?.pause();
    return true;
  });

  ipcMain.handle('sync:resume', async () => {
    syncService?.resume();
    return true;
  });

  ipcMain.handle('sync:getQueue', async () => {
    return syncService?.getQueue();
  });

  // Libraries
  ipcMain.handle('libraries:list', async () => {
    return syncService?.listLibraries();
  });

  ipcMain.handle('libraries:sync', async (_, libraryId: string) => {
    return syncService?.syncLibrary(libraryId);
  });

  ipcMain.handle('libraries:setEnabled', async (_, libraryId: string, enabled: boolean) => {
    const syncedLibraries = store.get('syncedLibraries') as string[];
    if (enabled) {
      if (!syncedLibraries.includes(libraryId)) {
        store.set('syncedLibraries', [...syncedLibraries, libraryId]);
      }
    } else {
      store.set('syncedLibraries', syncedLibraries.filter(id => id !== libraryId));
    }
    return true;
  });

  // Conflicts
  ipcMain.handle('conflicts:list', async () => {
    return syncService?.getConflicts();
  });

  ipcMain.handle('conflicts:resolve', async (_, conflictId: string, resolution: string) => {
    return syncService?.resolveConflict(conflictId, resolution);
  });
}

// App lifecycle
app.whenReady().then(async () => {
  createWindow();
  createTray();
  setupIpcHandlers();
  await initializeServices();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  // Don't quit on macOS
  if (process.platform !== 'darwin') {
    // Keep running in tray
  }
});

app.on('before-quit', () => {
  app.isQuitting = true;
  syncService?.stop();
  fileWatcher?.stop();
});

// Extend app type
declare module 'electron' {
  interface App {
    isQuitting: boolean;
  }
}

app.isQuitting = false;
