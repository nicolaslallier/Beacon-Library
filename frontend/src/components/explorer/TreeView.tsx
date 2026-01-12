/**
 * Tree View sidebar component for folder navigation
 * WCAG AAA compliant with full keyboard navigation
 */

import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import {
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  Library,
} from 'lucide-react';

import { cn } from '../../lib/utils';
import { browseLibrary } from '../../services/files';
import type { BrowseItem } from '../../services/files';

interface TreeViewProps {
  libraryId: string;
  libraryName: string;
  currentPath: string;
  onNavigate: (path: string, directoryId?: string) => void;
}

interface TreeNodeProps {
  item: BrowseItem;
  level: number;
  currentPath: string;
  onNavigate: (path: string, directoryId?: string) => void;
  libraryId: string;
}

function TreeNode({
  item,
  level,
  currentPath,
  onNavigate,
  libraryId,
}: TreeNodeProps) {
  const { t } = useTranslation();
  const [isExpanded, setIsExpanded] = useState(false);
  const isSelected = currentPath === item.path;
  const isAncestor = currentPath.startsWith(item.path + '/');

  // Fetch children when expanded
  const { data: children, isLoading } = useQuery({
    queryKey: ['tree', libraryId, item.id],
    queryFn: () =>
      browseLibrary(libraryId, { directoryId: item.id }).then((res) =>
        res.items.filter((i) => i.type === 'directory')
      ),
    enabled: isExpanded,
  });

  const handleToggle = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      setIsExpanded(!isExpanded);
    },
    [isExpanded]
  );

  const handleSelect = useCallback(() => {
    onNavigate(item.path, item.id);
  }, [item, onNavigate]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      switch (e.key) {
        case 'Enter':
        case ' ':
          e.preventDefault();
          handleSelect();
          break;
        case 'ArrowRight':
          e.preventDefault();
          if (!isExpanded) {
            setIsExpanded(true);
          }
          break;
        case 'ArrowLeft':
          e.preventDefault();
          if (isExpanded) {
            setIsExpanded(false);
          }
          break;
      }
    },
    [isExpanded, handleSelect]
  );

  const hasChildren = item.item_count && item.item_count > 0;

  return (
    <li role="treeitem" aria-expanded={hasChildren ? isExpanded : undefined}>
      <div
        className={cn(
          'flex items-center gap-1 px-2 py-1 cursor-pointer rounded-md transition-colors',
          'hover:bg-slate-100 dark:hover:bg-slate-700',
          'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset',
          isSelected && 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300',
          isAncestor && !isSelected && 'bg-slate-100/50 dark:bg-slate-700/50'
        )}
        style={{ paddingLeft: `${level * 16 + 8}px` }}
        onClick={handleSelect}
        onKeyDown={handleKeyDown}
        tabIndex={0}
        role="button"
        aria-label={`${item.name}${hasChildren ? `, ${isExpanded ? t('accessibility.collapseFolder') : t('accessibility.expandFolder')}` : ''}`}
      >
        {/* Expand/collapse button */}
        {hasChildren ? (
          <button
            onClick={handleToggle}
            className="p-0.5 hover:bg-slate-200 dark:hover:bg-slate-600 rounded"
            aria-label={isExpanded ? t('accessibility.collapseFolder') : t('accessibility.expandFolder')}
          >
            {isExpanded ? (
              <ChevronDown className="w-4 h-4 text-slate-500" />
            ) : (
              <ChevronRight className="w-4 h-4 text-slate-500" />
            )}
          </button>
        ) : (
          <span className="w-5" />
        )}

        {/* Folder icon */}
        {isExpanded ? (
          <FolderOpen className="w-4 h-4 text-amber-500 flex-shrink-0" />
        ) : (
          <Folder className="w-4 h-4 text-amber-500 flex-shrink-0" />
        )}

        {/* Name */}
        <span className="truncate text-sm">{item.name}</span>
      </div>

      {/* Children */}
      {isExpanded && hasChildren && (
        <ul role="group" className="ml-2">
          {isLoading ? (
            <li className="px-4 py-1 text-sm text-slate-400">{t('common.loading')}</li>
          ) : (
            children?.map((child) => (
              <TreeNode
                key={child.id}
                item={child}
                level={level + 1}
                currentPath={currentPath}
                onNavigate={onNavigate}
                libraryId={libraryId}
              />
            ))
          )}
        </ul>
      )}
    </li>
  );
}

export function TreeView({
  libraryId,
  libraryName,
  currentPath,
  onNavigate,
}: TreeViewProps) {
  const { t } = useTranslation();

  // Fetch root directories
  const { data: rootItems, isLoading } = useQuery({
    queryKey: ['tree', libraryId, 'root'],
    queryFn: () =>
      browseLibrary(libraryId, { path: '/' }).then((res) =>
        res.items.filter((i) => i.type === 'directory')
      ),
  });

  return (
    <div className="h-full overflow-auto py-2">
      <nav aria-label={t('nav.libraries')}>
        <ul role="tree" className="space-y-1">
          {/* Library root */}
          <li role="treeitem">
            <button
              onClick={() => onNavigate('/')}
              className={cn(
                'flex items-center gap-2 w-full px-3 py-2 text-left rounded-md transition-colors',
                'hover:bg-slate-100 dark:hover:bg-slate-700',
                'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset',
                currentPath === '/' && 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300'
              )}
            >
              <Library className="w-5 h-5 text-blue-500" />
              <span className="font-medium text-sm truncate">{libraryName}</span>
            </button>
          </li>

          {/* Root directories */}
          {isLoading ? (
            <li className="px-4 py-2 text-sm text-slate-400">{t('common.loading')}</li>
          ) : (
            rootItems?.map((item) => (
              <TreeNode
                key={item.id}
                item={item}
                level={1}
                currentPath={currentPath}
                onNavigate={onNavigate}
                libraryId={libraryId}
              />
            ))
          )}
        </ul>
      </nav>
    </div>
  );
}
