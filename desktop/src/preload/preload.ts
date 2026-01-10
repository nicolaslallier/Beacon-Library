/**
 * Preload script - Exposes safe IPC methods to renderer
 */

import { contextBridge, ipcRenderer } from 'electron';

// Expose protected methods to renderer
contextBridge.exposeInMainWorld('electronAPI', {
  // Auth
  auth: {
    login: (serverUrl: string) => ipcRenderer.invoke('auth:login', serverUrl),
    logout: () => ipcRenderer.invoke('auth:logout'),
    getStatus: () => ipcRenderer.invoke('auth:getStatus'),
  },

  // Settings
  settings: {
    get: (key: string) => ipcRenderer.invoke('settings:get', key),
    set: (key: string, value: any) => ipcRenderer.invoke('settings:set', key, value),
    selectSyncFolder: () => ipcRenderer.invoke('settings:selectSyncFolder'),
  },

  // Sync
  sync: {
    getStatus: () => ipcRenderer.invoke('sync:getStatus'),
    syncNow: () => ipcRenderer.invoke('sync:syncNow'),
    pause: () => ipcRenderer.invoke('sync:pause'),
    resume: () => ipcRenderer.invoke('sync:resume'),
    getQueue: () => ipcRenderer.invoke('sync:getQueue'),
  },

  // Libraries
  libraries: {
    list: () => ipcRenderer.invoke('libraries:list'),
    sync: (libraryId: string) => ipcRenderer.invoke('libraries:sync', libraryId),
    setEnabled: (libraryId: string, enabled: boolean) =>
      ipcRenderer.invoke('libraries:setEnabled', libraryId, enabled),
  },

  // Conflicts
  conflicts: {
    list: () => ipcRenderer.invoke('conflicts:list'),
    resolve: (conflictId: string, resolution: string) =>
      ipcRenderer.invoke('conflicts:resolve', conflictId, resolution),
  },

  // Navigation events
  onNavigate: (callback: (path: string) => void) => {
    ipcRenderer.on('navigate', (_, path) => callback(path));
  },
});

// Type definitions for renderer
declare global {
  interface Window {
    electronAPI: {
      auth: {
        login: (serverUrl: string) => Promise<boolean>;
        logout: () => Promise<void>;
        getStatus: () => Promise<{
          isAuthenticated: boolean;
          user: { id: string; email: string; name: string } | null;
          serverUrl: string | null;
        }>;
      };
      settings: {
        get: (key: string) => Promise<any>;
        set: (key: string, value: any) => Promise<boolean>;
        selectSyncFolder: () => Promise<string | null>;
      };
      sync: {
        getStatus: () => Promise<{
          isRunning: boolean;
          isPaused: boolean;
          lastSync: number | null;
          pendingItems: number;
          errorItems: number;
          currentItem: string | null;
        }>;
        syncNow: () => Promise<void>;
        pause: () => Promise<boolean>;
        resume: () => Promise<boolean>;
        getQueue: () => Promise<any[]>;
      };
      libraries: {
        list: () => Promise<any[]>;
        sync: (libraryId: string) => Promise<void>;
        setEnabled: (libraryId: string, enabled: boolean) => Promise<boolean>;
      };
      conflicts: {
        list: () => Promise<any[]>;
        resolve: (conflictId: string, resolution: string) => Promise<void>;
      };
      onNavigate: (callback: (path: string) => void) => void;
    };
  }
}
