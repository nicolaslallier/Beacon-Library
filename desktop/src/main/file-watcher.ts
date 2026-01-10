/**
 * File Watcher - Monitors local sync folder for changes
 */

import * as chokidar from 'chokidar';
import * as path from 'path';

interface FileWatcherConfig {
  syncFolder: string;
  onFileChange: (filePath: string, eventType: 'add' | 'change' | 'unlink') => void;
}

export class FileWatcher {
  private config: FileWatcherConfig;
  private watcher: chokidar.FSWatcher | null = null;
  private ignorePatterns = [
    '**/node_modules/**',
    '**/.git/**',
    '**/.DS_Store',
    '**/Thumbs.db',
    '**/*.tmp',
    '**/*.temp',
    '**/*~',
    '**/.beacon-sync/**',
  ];

  constructor(config: FileWatcherConfig) {
    this.config = config;
    this.start();
  }

  start(): void {
    if (!this.config.syncFolder) {
      return;
    }

    this.watcher = chokidar.watch(this.config.syncFolder, {
      ignored: this.ignorePatterns,
      persistent: true,
      ignoreInitial: true,
      awaitWriteFinish: {
        stabilityThreshold: 2000,
        pollInterval: 100,
      },
      depth: 10,
    });

    this.watcher
      .on('add', (filePath) => {
        console.log(`File added: ${filePath}`);
        this.config.onFileChange(filePath, 'add');
      })
      .on('change', (filePath) => {
        console.log(`File changed: ${filePath}`);
        this.config.onFileChange(filePath, 'change');
      })
      .on('unlink', (filePath) => {
        console.log(`File removed: ${filePath}`);
        this.config.onFileChange(filePath, 'unlink');
      })
      .on('error', (error) => {
        console.error('Watcher error:', error);
      });

    console.log(`Started watching: ${this.config.syncFolder}`);
  }

  stop(): void {
    if (this.watcher) {
      this.watcher.close();
      this.watcher = null;
      console.log('Stopped file watcher');
    }
  }

  updateSyncFolder(newFolder: string): void {
    this.stop();
    this.config.syncFolder = newFolder;
    this.start();
  }

  addIgnorePattern(pattern: string): void {
    this.ignorePatterns.push(pattern);
    // Restart watcher with new patterns
    this.stop();
    this.start();
  }
}
