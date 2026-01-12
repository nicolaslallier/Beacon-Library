/**
 * File Explorer Toolbar with actions
 * WCAG AAA compliant
 */

import { useTranslation } from 'react-i18next';
import {
  FolderPlus,
  Upload,
  Download,
  Trash2,
  Grid,
  List,
  RefreshCw,
  ArrowUp,
  Share2,
  Scissors,
  Copy,
  Clipboard,
} from 'lucide-react';

import { cn } from '../../lib/utils';

interface ToolbarProps {
  libraryId: string;
  currentPath: string;
  currentDirectoryId?: string;
  selectedItems: Set<string>;
  viewMode: 'list' | 'grid';
  onViewModeChange: (mode: 'list' | 'grid') => void;
  onRefresh: () => void;
  onNavigateUp: () => void;
  onUploadClick: () => void;
  onNewFolderClick: () => void;
  onDownloadClick: () => void;
  onShareClick: () => void;
  onDeleteClick: () => void;
}

interface ToolbarButtonProps {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  disabled?: boolean;
  variant?: 'default' | 'primary' | 'danger';
}

function ToolbarButton({
  icon,
  label,
  onClick,
  disabled = false,
  variant = 'default',
}: ToolbarButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md transition-colors',
        'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1',
        disabled && 'opacity-50 cursor-not-allowed',
        variant === 'default' &&
          'text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700',
        variant === 'primary' &&
          'text-white bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600',
        variant === 'danger' &&
          'text-red-700 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/30'
      )}
      aria-label={label}
      title={label}
    >
      {icon}
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}

function ToolbarSeparator() {
  return (
    <div
      className="w-px h-6 bg-slate-200 dark:bg-slate-700 mx-1"
      role="separator"
      aria-orientation="vertical"
    />
  );
}

export function Toolbar({
  libraryId: _libraryId, // Reserved for future actions
  currentPath,
  currentDirectoryId: _currentDirectoryId, // Reserved for future actions
  selectedItems,
  viewMode,
  onViewModeChange,
  onRefresh,
  onNavigateUp,
  onUploadClick,
  onNewFolderClick,
  onDownloadClick,
  onShareClick,
  onDeleteClick,
}: ToolbarProps) {
  const { t } = useTranslation();
  const hasSelection = selectedItems.size > 0;
  const isRoot = currentPath === '/';

  return (
    <div
      className="flex items-center gap-1 px-2 py-1.5 bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700"
      role="toolbar"
      aria-label={t('common.actions')}
    >
      {/* Navigation */}
      <ToolbarButton
        icon={<ArrowUp className="w-4 h-4" />}
        label={t('explorer.navigateUp', 'Up')}
        onClick={onNavigateUp}
        disabled={isRoot}
      />

      <ToolbarButton
        icon={<RefreshCw className="w-4 h-4" />}
        label={t('common.refresh', 'Refresh')}
        onClick={onRefresh}
      />

      <ToolbarSeparator />

      {/* Create actions */}
      <ToolbarButton
        icon={<FolderPlus className="w-4 h-4" />}
        label={t('explorer.newFolder')}
        onClick={onNewFolderClick}
      />

      <ToolbarButton
        icon={<Upload className="w-4 h-4" />}
        label={t('explorer.upload')}
        onClick={onUploadClick}
        variant="primary"
      />

      <ToolbarSeparator />

      {/* Selection actions */}
      <ToolbarButton
        icon={<Download className="w-4 h-4" />}
        label={t('explorer.download')}
        onClick={onDownloadClick}
        disabled={!hasSelection}
      />

      <ToolbarButton
        icon={<Share2 className="w-4 h-4" />}
        label={t('explorer.share')}
        onClick={onShareClick}
        disabled={!hasSelection}
      />

      <ToolbarSeparator />

      <ToolbarButton
        icon={<Scissors className="w-4 h-4" />}
        label={t('explorer.cut', 'Cut')}
        onClick={() => {
          // TODO: Cut to clipboard
          console.log('Cut', selectedItems);
        }}
        disabled={!hasSelection}
      />

      <ToolbarButton
        icon={<Copy className="w-4 h-4" />}
        label={t('explorer.copy')}
        onClick={() => {
          // TODO: Copy to clipboard
          console.log('Copy', selectedItems);
        }}
        disabled={!hasSelection}
      />

      <ToolbarButton
        icon={<Clipboard className="w-4 h-4" />}
        label={t('explorer.paste', 'Paste')}
        onClick={() => {
          // TODO: Paste from clipboard
          console.log('Paste');
        }}
        disabled={false} // Check clipboard state
      />

      <ToolbarSeparator />

      <ToolbarButton
        icon={<Trash2 className="w-4 h-4" />}
        label={t('explorer.delete')}
        onClick={onDeleteClick}
        disabled={!hasSelection}
        variant="danger"
      />

      {/* Spacer */}
      <div className="flex-1" />

      {/* View mode toggle */}
      <div className="flex items-center border border-slate-200 dark:border-slate-700 rounded-md overflow-hidden">
        <button
          onClick={() => onViewModeChange('list')}
          className={cn(
            'p-1.5 transition-colors',
            'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset',
            viewMode === 'list'
              ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300'
              : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700'
          )}
          aria-label={t('explorer.view.list')}
          aria-pressed={viewMode === 'list'}
        >
          <List className="w-4 h-4" />
        </button>
        <button
          onClick={() => onViewModeChange('grid')}
          className={cn(
            'p-1.5 transition-colors',
            'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset',
            viewMode === 'grid'
              ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300'
              : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700'
          )}
          aria-label={t('explorer.view.grid')}
          aria-pressed={viewMode === 'grid'}
        >
          <Grid className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
