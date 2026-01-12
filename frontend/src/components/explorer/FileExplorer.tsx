/**
 * Main File Explorer component - Windows Explorer-like interface
 * WCAG AAA compliant with full keyboard navigation
 */

import { useState, useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { RefreshCw, ChevronRight } from 'lucide-react';

import { cn } from '../../lib/utils';
import { browseLibrary, downloadFile, deleteFile, deleteDirectory } from '../../services/files';
import type { BrowseItem } from '../../services/files';
import { TreeView } from './TreeView';
import { FileList } from './FileList';
import { Toolbar } from './Toolbar';
import { Breadcrumb } from './Breadcrumb';
import { UploadDialog } from './UploadDialog';
import { NewFolderDialog } from './NewFolderDialog';
import { PreviewDialog } from './PreviewDialog';
import { ShareDialog } from './ShareDialog';

interface FileExplorerProps {
  libraryId: string;
  libraryName: string;
  className?: string;
}

export function FileExplorer({ libraryId, libraryName, className }: FileExplorerProps) {
  const { t } = useTranslation();

  // State
  const [currentPath, setCurrentPath] = useState('/');
  const [currentDirectoryId, setCurrentDirectoryId] = useState<string | undefined>();
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');
  const [sortBy, setSortBy] = useState('name');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [newFolderDialogOpen, setNewFolderDialogOpen] = useState(false);
  const [previewDialogOpen, setPreviewDialogOpen] = useState(false);
  const [previewFile, setPreviewFile] = useState<BrowseItem | null>(null);
  const [shareDialogOpen, setShareDialogOpen] = useState(false);
  const [shareItem, setShareItem] = useState<BrowseItem | null>(null);

  // Fetch directory contents
  const {
    data: browseData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['browse', libraryId, currentPath, currentDirectoryId, sortBy, sortOrder],
    queryFn: () =>
      browseLibrary(libraryId, {
        path: currentPath,
        directoryId: currentDirectoryId,
        sortBy,
        sortOrder,
      }),
  });

  // Navigation handlers
  const navigateTo = useCallback((path: string, directoryId?: string) => {
    setCurrentPath(path);
    setCurrentDirectoryId(directoryId);
    setSelectedItems(new Set());
  }, []);

  const navigateUp = useCallback(() => {
    if (currentPath === '/') return;

    const parts = currentPath.split('/').filter(Boolean);
    parts.pop();
    const newPath = parts.length > 0 ? '/' + parts.join('/') : '/';
    navigateTo(newPath);
  }, [currentPath, navigateTo]);

  // Item selection
  const handleItemSelect = useCallback((item: BrowseItem, event: React.MouseEvent) => {
    if (event.ctrlKey || event.metaKey) {
      // Multi-select
      setSelectedItems((prev) => {
        const next = new Set(prev);
        if (next.has(item.id)) {
          next.delete(item.id);
        } else {
          next.add(item.id);
        }
        return next;
      });
    } else if (event.shiftKey && selectedItems.size > 0) {
      // Range select (simplified)
      setSelectedItems(new Set([...selectedItems, item.id]));
    } else {
      // Single select
      setSelectedItems(new Set([item.id]));
    }
  }, [selectedItems]);

  const handleItemOpen = useCallback((item: BrowseItem) => {
    if (item.type === 'directory') {
      navigateTo(item.path, item.id);
    } else {
      // Open file preview dialog
      setPreviewFile(item);
      setPreviewDialogOpen(true);
    }
  }, [navigateTo]);

  // Download handler
  const handleDownload = useCallback(async () => {
    if (selectedItems.size === 0 || !browseData?.items) return;

    // Get selected file items (not directories)
    const selectedFiles = browseData.items.filter(
      (item) => selectedItems.has(item.id) && item.type === 'file'
    );

    if (selectedFiles.length === 0) {
      // No files selected (only directories), nothing to download
      return;
    }

    // Download each file
    for (const file of selectedFiles) {
      try {
        const blob = await downloadFile(file.id);
        
        // Create a download link and trigger it
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = file.name;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
      } catch (error) {
        console.error('Download failed for file:', file.name, error);
      }
    }
  }, [selectedItems, browseData?.items]);

  // Share handler
  const handleShare = useCallback(() => {
    if (selectedItems.size === 0 || !browseData?.items) return;

    // Get the first selected item for sharing
    const selectedItem = browseData.items.find((item) => selectedItems.has(item.id));
    if (selectedItem) {
      setShareItem(selectedItem);
      setShareDialogOpen(true);
    }
  }, [selectedItems, browseData?.items]);

  // Delete handler
  const handleDelete = useCallback(async () => {
    if (selectedItems.size === 0 || !browseData?.items) return;

    // Get selected items
    const itemsToDelete = browseData.items.filter((item) => selectedItems.has(item.id));
    if (itemsToDelete.length === 0) return;

    // Confirm deletion
    const itemNames = itemsToDelete.map((i) => i.name).join(', ');
    const confirmed = window.confirm(
      `Are you sure you want to delete ${itemsToDelete.length} item(s)?\n\n${itemNames}`
    );
    if (!confirmed) return;

    // Delete each item
    for (const item of itemsToDelete) {
      try {
        if (item.type === 'directory') {
          await deleteDirectory(libraryId, item.id);
        } else {
          await deleteFile(item.id);
        }
      } catch (error) {
        console.error('Delete failed for:', item.name, error);
      }
    }

    // Clear selection and refresh
    setSelectedItems(new Set());
    refetch();
  }, [selectedItems, browseData?.items, libraryId, refetch]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Backspace' && !['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement).tagName)) {
        e.preventDefault();
        navigateUp();
      }
      if (e.key === 'F5') {
        e.preventDefault();
        refetch();
      }
      if (e.key === 'Escape') {
        setSelectedItems(new Set());
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [navigateUp, refetch]);

  return (
    <div
      className={cn(
        'flex flex-col h-full bg-slate-50 dark:bg-slate-900 rounded-lg overflow-hidden border border-slate-200 dark:border-slate-700',
        className
      )}
      role="application"
      aria-label={t('explorer.title')}
    >
      {/* Skip link for accessibility */}
      <a
        href="#file-list"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:p-2 focus:bg-blue-600 focus:text-white"
      >
        {t('accessibility.skipToMain')}
      </a>

      {/* Toolbar */}
      <Toolbar
        libraryId={libraryId}
        currentPath={currentPath}
        currentDirectoryId={currentDirectoryId}
        selectedItems={selectedItems}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        onRefresh={() => refetch()}
        onNavigateUp={navigateUp}
        onUploadClick={() => setUploadDialogOpen(true)}
        onNewFolderClick={() => setNewFolderDialogOpen(true)}
        onDownloadClick={handleDownload}
        onShareClick={handleShare}
        onDeleteClick={handleDelete}
      />

      {/* Breadcrumb */}
      <Breadcrumb
        breadcrumb={browseData?.breadcrumb || [{ name: t('explorer.breadcrumb.root'), path: '/' }]}
        onNavigate={navigateTo}
      />

      {/* Main content area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar - Tree View */}
        <aside
          className={cn(
            'border-r border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 transition-all duration-200',
            sidebarCollapsed ? 'w-0' : 'w-64'
          )}
          aria-label={t('nav.libraries')}
        >
          {!sidebarCollapsed && (
            <TreeView
              libraryId={libraryId}
              libraryName={libraryName}
              currentPath={currentPath}
              onNavigate={navigateTo}
            />
          )}
        </aside>

        {/* Toggle sidebar button */}
        <button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          className="flex items-center justify-center w-4 bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 border-r border-slate-200 dark:border-slate-700 transition-colors"
          aria-label={sidebarCollapsed ? t('accessibility.openMenu') : t('accessibility.closeMenu')}
          aria-expanded={!sidebarCollapsed}
        >
          <ChevronRight
            className={cn(
              'w-3 h-3 text-slate-500 transition-transform',
              !sidebarCollapsed && 'rotate-180'
            )}
          />
        </button>

        {/* File list */}
        <main
          id="file-list"
          className="flex-1 overflow-auto bg-white dark:bg-slate-800"
          role="main"
          aria-label={t('explorer.title')}
        >
          {isLoading ? (
            <div className="flex items-center justify-center h-full">
              <RefreshCw className="w-8 h-8 animate-spin text-slate-400" />
              <span className="sr-only">{t('common.loading')}</span>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center h-full text-red-500">
              <p>{t('common.error')}</p>
              <button
                onClick={() => refetch()}
                className="mt-2 px-4 py-2 bg-red-100 dark:bg-red-900 rounded hover:bg-red-200 dark:hover:bg-red-800"
              >
                {t('common.retry')}
              </button>
            </div>
          ) : (
            <FileList
              items={browseData?.items || []}
              viewMode={viewMode}
              selectedItems={selectedItems}
              sortBy={sortBy}
              sortOrder={sortOrder}
              onSortChange={(newSortBy) => {
                if (newSortBy === sortBy) {
                  setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
                } else {
                  setSortBy(newSortBy);
                  setSortOrder('asc');
                }
              }}
              onItemSelect={handleItemSelect}
              onItemOpen={handleItemOpen}
            />
          )}
        </main>
      </div>

      {/* Status bar */}
      <footer className="flex items-center justify-between px-4 py-1 text-xs text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 border-t border-slate-200 dark:border-slate-700">
        <span>
          {browseData?.total || 0} {t('common.items', { count: browseData?.total || 0 })}
        </span>
        {selectedItems.size > 0 && (
          <span>
            {t('accessibility.selectedItems', { count: selectedItems.size })}
          </span>
        )}
      </footer>

      {/* Upload Dialog */}
      <UploadDialog
        open={uploadDialogOpen}
        onClose={() => setUploadDialogOpen(false)}
        libraryId={libraryId}
        directoryId={currentDirectoryId}
        onUploadComplete={() => {
          refetch();
        }}
      />

      {/* New Folder Dialog */}
      <NewFolderDialog
        open={newFolderDialogOpen}
        onClose={() => setNewFolderDialogOpen(false)}
        libraryId={libraryId}
        parentDirectoryId={currentDirectoryId}
        onFolderCreated={() => {
          refetch();
        }}
      />

      {/* Preview Dialog */}
      <PreviewDialog
        open={previewDialogOpen}
        onClose={() => {
          setPreviewDialogOpen(false);
          setPreviewFile(null);
        }}
        file={previewFile}
      />

      {/* Share Dialog */}
      <ShareDialog
        isOpen={shareDialogOpen}
        onClose={() => {
          setShareDialogOpen(false);
          setShareItem(null);
        }}
        targetType={shareItem?.type === 'directory' ? 'directory' : 'file'}
        targetId={shareItem?.id || ''}
        targetName={shareItem?.name || ''}
      />
    </div>
  );
}
