/**
 * Duplicate file conflict resolution dialog
 * WCAG AAA compliant
 */

import { useTranslation } from 'react-i18next';
import { AlertTriangle, File, ArrowRight } from 'lucide-react';

import { cn, formatBytes, formatDate } from '../../lib/utils';
import type { DuplicateConflict } from '../../services/files';

interface DuplicateDialogProps {
  open: boolean;
  conflict: DuplicateConflict | null;
  newFile: { name: string; size: number } | null;
  onResolve: (action: 'overwrite' | 'rename' | 'cancel') => void;
}

export function DuplicateDialog({
  open,
  conflict,
  newFile,
  onResolve,
}: DuplicateDialogProps) {
  const { t } = useTranslation();

  if (!open || !conflict || !newFile) return null;

  const existingFile = conflict.existing_file;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={() => onResolve('cancel')}
    >
      <div
        className="bg-white dark:bg-slate-800 rounded-xl shadow-xl w-full max-w-lg p-6"
        onClick={(e) => e.stopPropagation()}
        role="alertdialog"
        aria-labelledby="duplicate-dialog-title"
        aria-describedby="duplicate-dialog-description"
      >
        {/* Header */}
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-amber-100 dark:bg-amber-900/50 rounded-full">
            <AlertTriangle className="w-6 h-6 text-amber-600 dark:text-amber-400" />
          </div>
          <h2
            id="duplicate-dialog-title"
            className="text-xl font-semibold text-slate-900 dark:text-slate-100"
          >
            {t('upload.duplicate.title')}
          </h2>
        </div>

        {/* Description */}
        <p
          id="duplicate-dialog-description"
          className="text-slate-600 dark:text-slate-400 mb-6"
        >
          {t('upload.duplicate.message', { filename: newFile.name })}
        </p>

        {/* File comparison */}
        <div className="flex items-center gap-4 p-4 bg-slate-50 dark:bg-slate-700/50 rounded-lg mb-6">
          {/* Existing file */}
          <div className="flex-1">
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-1">
              {t('upload.duplicate.existing', 'Existing file')}
            </p>
            <div className="flex items-center gap-2">
              <File className="w-8 h-8 text-slate-400" />
              <div>
                <p className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
                  {existingFile.filename}
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {formatBytes(existingFile.size_bytes)} •{' '}
                  {formatDate(existingFile.updated_at)}
                </p>
              </div>
            </div>
          </div>

          <ArrowRight className="w-5 h-5 text-slate-400 flex-shrink-0" />

          {/* New file */}
          <div className="flex-1">
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-1">
              {t('upload.duplicate.new', 'New file')}
            </p>
            <div className="flex items-center gap-2">
              <File className="w-8 h-8 text-blue-500" />
              <div>
                <p className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
                  {newFile.name}
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {formatBytes(newFile.size)}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-2">
          <button
            onClick={() => onResolve('overwrite')}
            className={cn(
              'flex items-center justify-between w-full px-4 py-3 rounded-lg transition-colors',
              'bg-blue-50 dark:bg-blue-900/30 hover:bg-blue-100 dark:hover:bg-blue-900/50',
              'text-blue-700 dark:text-blue-300',
              'focus:outline-none focus:ring-2 focus:ring-blue-500'
            )}
          >
            <div className="text-left">
              <p className="font-medium">{t('upload.duplicate.overwrite')}</p>
              <p className="text-sm opacity-80">
                {t('upload.duplicate.overwriteDesc', 'Replace the existing file with the new one')}
              </p>
            </div>
          </button>

          <button
            onClick={() => onResolve('rename')}
            className={cn(
              'flex items-center justify-between w-full px-4 py-3 rounded-lg transition-colors',
              'bg-slate-50 dark:bg-slate-700/50 hover:bg-slate-100 dark:hover:bg-slate-700',
              'text-slate-700 dark:text-slate-300',
              'focus:outline-none focus:ring-2 focus:ring-slate-500'
            )}
          >
            <div className="text-left">
              <p className="font-medium">{t('upload.duplicate.rename')}</p>
              <p className="text-sm opacity-80">
                {conflict.suggested_name
                  ? t('upload.duplicate.renameDesc', { name: conflict.suggested_name })
                  : t('upload.duplicate.renameDescGeneric', 'Save with a different name')}
              </p>
            </div>
          </button>

          <button
            onClick={() => onResolve('cancel')}
            className={cn(
              'flex items-center justify-between w-full px-4 py-3 rounded-lg transition-colors',
              'hover:bg-slate-100 dark:hover:bg-slate-700',
              'text-slate-500 dark:text-slate-400',
              'focus:outline-none focus:ring-2 focus:ring-slate-500'
            )}
          >
            <div className="text-left">
              <p className="font-medium">{t('upload.duplicate.skip')}</p>
              <p className="text-sm opacity-80">
                {t('upload.duplicate.skipDesc', 'Don\'t upload this file')}
              </p>
            </div>
          </button>
        </div>
      </div>
    </div>
  );
}
