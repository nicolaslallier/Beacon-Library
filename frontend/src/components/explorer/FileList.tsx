/**
 * File List component - displays files and folders in list or grid view
 * WCAG AAA compliant with full keyboard navigation
 */

import { useCallback, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Folder,
  File,
  FileText,
  FileImage,
  FileVideo,
  FileAudio,
  FileArchive,
  FileCode,
  FileSpreadsheet,
  FileType,
  ArrowUp,
  ArrowDown,
} from 'lucide-react';

import { cn, formatBytes, formatDate, getFileIcon } from '../../lib/utils';
import { BrowseItem } from '../../services/files';

interface FileListProps {
  items: BrowseItem[];
  viewMode: 'list' | 'grid';
  selectedItems: Set<string>;
  sortBy: string;
  sortOrder: 'asc' | 'desc';
  onSortChange: (sortBy: string) => void;
  onItemSelect: (item: BrowseItem, event: React.MouseEvent) => void;
  onItemOpen: (item: BrowseItem) => void;
}

// Icon mapping
const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  folder: Folder,
  file: File,
  text: FileText,
  image: FileImage,
  video: FileVideo,
  audio: FileAudio,
  archive: FileArchive,
  code: FileCode,
  spreadsheet: FileSpreadsheet,
  document: FileType,
  pdf: FileType,
  presentation: FileType,
};

function getItemIcon(item: BrowseItem) {
  if (item.type === 'directory') {
    return Folder;
  }
  const iconType = getFileIcon(item.content_type || '', item.name);
  return iconMap[iconType] || File;
}

interface SortHeaderProps {
  label: string;
  sortKey: string;
  currentSortBy: string;
  sortOrder: 'asc' | 'desc';
  onSort: (key: string) => void;
  className?: string;
}

function SortHeader({
  label,
  sortKey,
  currentSortBy,
  sortOrder,
  onSort,
  className,
}: SortHeaderProps) {
  const isActive = currentSortBy === sortKey;

  return (
    <button
      onClick={() => onSort(sortKey)}
      className={cn(
        'flex items-center gap-1 text-left font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 transition-colors',
        'focus:outline-none focus:underline',
        className
      )}
      aria-sort={isActive ? (sortOrder === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      {label}
      {isActive && (
        sortOrder === 'asc' ? (
          <ArrowUp className="w-3 h-3" />
        ) : (
          <ArrowDown className="w-3 h-3" />
        )
      )}
    </button>
  );
}

export function FileList({
  items,
  viewMode,
  selectedItems,
  sortBy,
  sortOrder,
  onSortChange,
  onItemSelect,
  onItemOpen,
}: FileListProps) {
  const { t } = useTranslation();
  const listRef = useRef<HTMLDivElement>(null);
  const focusedIndex = useRef(0);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent, item: BrowseItem, index: number) => {
      const itemElements = listRef.current?.querySelectorAll('[data-item]');
      if (!itemElements) return;

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          if (index < items.length - 1) {
            (itemElements[index + 1] as HTMLElement)?.focus();
            focusedIndex.current = index + 1;
          }
          break;
        case 'ArrowUp':
          e.preventDefault();
          if (index > 0) {
            (itemElements[index - 1] as HTMLElement)?.focus();
            focusedIndex.current = index - 1;
          }
          break;
        case 'Enter':
          e.preventDefault();
          onItemOpen(item);
          break;
        case ' ':
          e.preventDefault();
          onItemSelect(item, e as unknown as React.MouseEvent);
          break;
        case 'Home':
          e.preventDefault();
          (itemElements[0] as HTMLElement)?.focus();
          focusedIndex.current = 0;
          break;
        case 'End':
          e.preventDefault();
          (itemElements[items.length - 1] as HTMLElement)?.focus();
          focusedIndex.current = items.length - 1;
          break;
      }
    },
    [items, onItemOpen, onItemSelect]
  );

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-slate-500 dark:text-slate-400">
        <Folder className="w-16 h-16 mb-4 opacity-50" />
        <p className="text-lg font-medium">{t('explorer.emptyFolder')}</p>
        <p className="text-sm">{t('explorer.emptyFolderDescription')}</p>
      </div>
    );
  }

  if (viewMode === 'grid') {
    return (
      <div
        ref={listRef}
        className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4 p-4"
        role="grid"
        aria-label={t('explorer.title')}
      >
        {items.map((item, index) => {
          const Icon = getItemIcon(item);
          const isSelected = selectedItems.has(item.id);

          return (
            <div
              key={item.id}
              data-item
              onClick={(e) => onItemSelect(item, e)}
              onDoubleClick={() => onItemOpen(item)}
              onKeyDown={(e) => handleKeyDown(e, item, index)}
              className={cn(
                'flex flex-col items-center gap-2 p-4 rounded-lg cursor-pointer transition-colors',
                'focus:outline-none focus:ring-2 focus:ring-blue-500',
                isSelected
                  ? 'bg-blue-100 dark:bg-blue-900/50'
                  : 'hover:bg-slate-100 dark:hover:bg-slate-700'
              )}
              tabIndex={0}
              role="gridcell"
              aria-selected={isSelected}
            >
              <Icon
                className={cn(
                  'w-12 h-12',
                  item.type === 'directory'
                    ? 'text-amber-500'
                    : 'text-slate-400 dark:text-slate-500'
                )}
              />
              <span className="text-sm text-center truncate w-full" title={item.name}>
                {item.name}
              </span>
            </div>
          );
        })}
      </div>
    );
  }

  // List view
  return (
    <div ref={listRef} className="w-full">
      {/* Header */}
      <div
        className="flex items-center gap-4 px-4 py-2 bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-700 text-sm sticky top-0"
        role="row"
      >
        <SortHeader
          label={t('common.name')}
          sortKey="name"
          currentSortBy={sortBy}
          sortOrder={sortOrder}
          onSort={onSortChange}
          className="flex-1 min-w-0"
        />
        <SortHeader
          label={t('file.modified')}
          sortKey="updated_at"
          currentSortBy={sortBy}
          sortOrder={sortOrder}
          onSort={onSortChange}
          className="w-40 hidden md:block"
        />
        <SortHeader
          label={t('common.type')}
          sortKey="type"
          currentSortBy={sortBy}
          sortOrder={sortOrder}
          onSort={onSortChange}
          className="w-24 hidden lg:block"
        />
        <SortHeader
          label={t('common.size')}
          sortKey="size"
          currentSortBy={sortBy}
          sortOrder={sortOrder}
          onSort={onSortChange}
          className="w-24 text-right"
        />
      </div>

      {/* Items */}
      <div role="rowgroup">
        {items.map((item, index) => {
          const Icon = getItemIcon(item);
          const isSelected = selectedItems.has(item.id);

          return (
            <div
              key={item.id}
              data-item
              onClick={(e) => onItemSelect(item, e)}
              onDoubleClick={() => onItemOpen(item)}
              onKeyDown={(e) => handleKeyDown(e, item, index)}
              className={cn(
                'flex items-center gap-4 px-4 py-2 cursor-pointer transition-colors border-b border-slate-100 dark:border-slate-800',
                'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset',
                isSelected
                  ? 'bg-blue-100 dark:bg-blue-900/50'
                  : 'hover:bg-slate-50 dark:hover:bg-slate-800'
              )}
              tabIndex={0}
              role="row"
              aria-selected={isSelected}
            >
              {/* Name */}
              <div className="flex items-center gap-3 flex-1 min-w-0" role="cell">
                <Icon
                  className={cn(
                    'w-5 h-5 flex-shrink-0',
                    item.type === 'directory'
                      ? 'text-amber-500'
                      : 'text-slate-400 dark:text-slate-500'
                  )}
                />
                <span className="truncate" title={item.name}>
                  {item.name}
                </span>
              </div>

              {/* Modified date */}
              <div className="w-40 text-sm text-slate-500 dark:text-slate-400 hidden md:block" role="cell">
                {formatDate(item.updated_at)}
              </div>

              {/* Type */}
              <div className="w-24 text-sm text-slate-500 dark:text-slate-400 hidden lg:block" role="cell">
                {item.type === 'directory'
                  ? t('common.folder', 'Folder')
                  : item.content_type?.split('/')[1]?.toUpperCase() || 'File'}
              </div>

              {/* Size */}
              <div className="w-24 text-sm text-slate-500 dark:text-slate-400 text-right" role="cell">
                {item.type === 'file' && item.size_bytes !== undefined
                  ? formatBytes(item.size_bytes)
                  : item.item_count !== undefined
                  ? `${item.item_count} items`
                  : '—'}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
