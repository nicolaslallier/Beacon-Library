/**
 * Sync Service - Handles file synchronization with Beacon Library server
 */

import * as fs from 'fs';
import * as path from 'path';
import axios, { AxiosInstance } from 'axios';
import Store from 'electron-store';
import { AuthService } from './auth-service';

interface SyncConfig {
  serverUrl: string;
  syncFolder: string;
  authService: AuthService;
  store: Store;
}

interface SyncQueueItem {
  id: string;
  filePath: string;
  eventType: 'add' | 'change' | 'unlink';
  timestamp: number;
  retries: number;
  status: 'pending' | 'syncing' | 'error' | 'completed';
  error?: string;
}

interface Conflict {
  id: string;
  localPath: string;
  remotePath: string;
  localModified: number;
  remoteModified: number;
  type: 'both_modified' | 'deleted_modified' | 'modified_deleted';
}

interface SyncStatus {
  isRunning: boolean;
  isPaused: boolean;
  lastSync: number | null;
  pendingItems: number;
  errorItems: number;
  currentItem: string | null;
}

export class SyncService {
  private config: SyncConfig;
  private api: AxiosInstance;
  private queue: SyncQueueItem[] = [];
  private conflicts: Conflict[] = [];
  private status: SyncStatus = {
    isRunning: false,
    isPaused: false,
    lastSync: null,
    pendingItems: 0,
    errorItems: 0,
    currentItem: null,
  };
  private syncInterval: NodeJS.Timeout | null = null;
  private isProcessing = false;

  constructor(config: SyncConfig) {
    this.config = config;
    this.api = axios.create({
      baseURL: config.serverUrl,
      timeout: 30000,
    });

    // Add auth interceptor
    this.api.interceptors.request.use(async (axiosConfig) => {
      const token = await config.authService.getToken();
      if (token) {
        axiosConfig.headers.Authorization = `Bearer ${token}`;
      }
      return axiosConfig;
    });

    // Load queue from store
    this.queue = config.store.get('syncQueue', []) as SyncQueueItem[];
    this.conflicts = config.store.get('syncConflicts', []) as Conflict[];
  }

  async syncAll(): Promise<void> {
    if (this.status.isPaused || this.isProcessing) {
      return;
    }

    this.status.isRunning = true;
    const syncedLibraries = this.config.store.get('syncedLibraries', []) as string[];

    for (const libraryId of syncedLibraries) {
      await this.syncLibrary(libraryId);
    }

    // Process queue
    await this.processQueue();

    this.status.lastSync = Date.now();
    this.status.isRunning = false;
  }

  async syncLibrary(libraryId: string): Promise<void> {
    try {
      // Get remote file list
      const response = await this.api.get(`/api/libraries/${libraryId}/browse`);
      const remoteFiles = response.data;

      // Get local file list
      const libraryPath = path.join(this.config.syncFolder, libraryId);
      if (!fs.existsSync(libraryPath)) {
        fs.mkdirSync(libraryPath, { recursive: true });
      }

      const localFiles = this.getLocalFiles(libraryPath);

      // Compare and sync
      await this.syncFiles(libraryId, libraryPath, remoteFiles, localFiles);

    } catch (error) {
      console.error(`Failed to sync library ${libraryId}:`, error);
    }
  }

  private async syncFiles(
    libraryId: string,
    libraryPath: string,
    remoteFiles: any[],
    localFiles: Map<string, fs.Stats>
  ): Promise<void> {
    // Download new/updated remote files
    for (const remoteFile of remoteFiles) {
      const localPath = path.join(libraryPath, remoteFile.path || remoteFile.name);
      const localStat = localFiles.get(localPath);

      if (!localStat) {
        // File doesn't exist locally - download
        await this.downloadFile(libraryId, remoteFile.id, localPath);
      } else {
        // Check for conflicts
        const remoteModified = new Date(remoteFile.updated_at).getTime();
        const localModified = localStat.mtimeMs;

        if (Math.abs(remoteModified - localModified) > 1000) {
          // Potential conflict
          this.addConflict({
            id: `${libraryId}-${remoteFile.id}`,
            localPath,
            remotePath: remoteFile.path,
            localModified,
            remoteModified,
            type: 'both_modified',
          });
        }
      }

      localFiles.delete(localPath);
    }

    // Upload local-only files
    for (const [localPath] of localFiles) {
      const relativePath = path.relative(libraryPath, localPath);
      await this.uploadFile(libraryId, localPath, relativePath);
    }
  }

  private async downloadFile(
    libraryId: string,
    fileId: string,
    localPath: string
  ): Promise<void> {
    try {
      const response = await this.api.get(`/api/files/${fileId}/download`, {
        responseType: 'arraybuffer',
      });

      // Ensure directory exists
      const dir = path.dirname(localPath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }

      fs.writeFileSync(localPath, Buffer.from(response.data));
      console.log(`Downloaded: ${localPath}`);

    } catch (error) {
      console.error(`Failed to download file ${fileId}:`, error);
      throw error;
    }
  }

  private async uploadFile(
    libraryId: string,
    localPath: string,
    remotePath: string
  ): Promise<void> {
    try {
      const fileContent = fs.readFileSync(localPath);
      const fileName = path.basename(localPath);

      const formData = new FormData();
      formData.append('file', new Blob([fileContent]), fileName);
      formData.append('path', remotePath);

      await this.api.post(`/api/libraries/${libraryId}/files`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      console.log(`Uploaded: ${localPath}`);

    } catch (error) {
      console.error(`Failed to upload file ${localPath}:`, error);
      throw error;
    }
  }

  private getLocalFiles(dirPath: string): Map<string, fs.Stats> {
    const files = new Map<string, fs.Stats>();

    const walk = (dir: string) => {
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          walk(fullPath);
        } else {
          files.set(fullPath, fs.statSync(fullPath));
        }
      }
    };

    if (fs.existsSync(dirPath)) {
      walk(dirPath);
    }

    return files;
  }

  queueSync(filePath: string, eventType: 'add' | 'change' | 'unlink'): void {
    const item: SyncQueueItem = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      filePath,
      eventType,
      timestamp: Date.now(),
      retries: 0,
      status: 'pending',
    };

    this.queue.push(item);
    this.saveQueue();
    this.updateStatus();

    // Process queue if not already processing
    if (!this.isProcessing) {
      this.processQueue();
    }
  }

  private async processQueue(): Promise<void> {
    if (this.isProcessing || this.status.isPaused) {
      return;
    }

    this.isProcessing = true;

    while (this.queue.length > 0) {
      const item = this.queue.find(i => i.status === 'pending');
      if (!item) break;

      item.status = 'syncing';
      this.status.currentItem = item.filePath;
      this.updateStatus();

      try {
        await this.processSyncItem(item);
        item.status = 'completed';
        this.queue = this.queue.filter(i => i.id !== item.id);
      } catch (error) {
        item.status = 'error';
        item.error = (error as Error).message;
        item.retries++;

        if (item.retries >= 3) {
          // Move to error state
          this.status.errorItems++;
        } else {
          // Retry later
          item.status = 'pending';
        }
      }

      this.saveQueue();
      this.updateStatus();
    }

    this.status.currentItem = null;
    this.isProcessing = false;
  }

  private async processSyncItem(item: SyncQueueItem): Promise<void> {
    const relativePath = path.relative(this.config.syncFolder, item.filePath);
    const parts = relativePath.split(path.sep);
    const libraryId = parts[0];

    switch (item.eventType) {
      case 'add':
      case 'change':
        await this.uploadFile(libraryId, item.filePath, relativePath);
        break;
      case 'unlink':
        // TODO: Implement remote delete
        break;
    }
  }

  private saveQueue(): void {
    this.config.store.set('syncQueue', this.queue);
  }

  private updateStatus(): void {
    this.status.pendingItems = this.queue.filter(i => i.status === 'pending').length;
  }

  private addConflict(conflict: Conflict): void {
    if (!this.conflicts.find(c => c.id === conflict.id)) {
      this.conflicts.push(conflict);
      this.config.store.set('syncConflicts', this.conflicts);
    }
  }

  async resolveConflict(conflictId: string, resolution: string): Promise<void> {
    const conflict = this.conflicts.find(c => c.id === conflictId);
    if (!conflict) return;

    switch (resolution) {
      case 'keep_local':
        // Upload local version
        const parts = conflictId.split('-');
        await this.uploadFile(parts[0], conflict.localPath, conflict.remotePath);
        break;
      case 'keep_remote':
        // Download remote version
        await this.downloadFile(parts[0], parts[1], conflict.localPath);
        break;
      case 'keep_both':
        // Rename local and download remote
        const ext = path.extname(conflict.localPath);
        const base = conflict.localPath.slice(0, -ext.length);
        const newLocal = `${base}_local_${Date.now()}${ext}`;
        fs.renameSync(conflict.localPath, newLocal);
        await this.downloadFile(parts[0], parts[1], conflict.localPath);
        break;
    }

    this.conflicts = this.conflicts.filter(c => c.id !== conflictId);
    this.config.store.set('syncConflicts', this.conflicts);
  }

  startAutoSync(interval: number): void {
    this.stopAutoSync();
    this.syncInterval = setInterval(() => {
      this.syncAll();
    }, interval);
  }

  stopAutoSync(): void {
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
      this.syncInterval = null;
    }
  }

  pause(): void {
    this.status.isPaused = true;
  }

  resume(): void {
    this.status.isPaused = false;
    this.processQueue();
  }

  stop(): void {
    this.stopAutoSync();
    this.saveQueue();
  }

  getStatus(): SyncStatus {
    return { ...this.status };
  }

  getQueue(): SyncQueueItem[] {
    return [...this.queue];
  }

  getConflicts(): Conflict[] {
    return [...this.conflicts];
  }

  async listLibraries(): Promise<any[]> {
    try {
      const response = await this.api.get('/api/libraries');
      return response.data;
    } catch (error) {
      console.error('Failed to list libraries:', error);
      return [];
    }
  }
}
