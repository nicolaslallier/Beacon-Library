/**
 * New Folder Dialog for creating directories
 * WCAG AAA compliant
 */

import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { FolderPlus, X, Loader2 } from 'lucide-react';

import { cn } from '../../lib/utils';
import { createDirectory } from '../../services/files';

interface NewFolderDialogProps {
  open: boolean;
  onClose: () => void;
  libraryId: string;
  parentDirectoryId?: string;
  onFolderCreated?: () => void;
}

export function NewFolderDialog({
  open,
  onClose,
  libraryId,
  parentDirectoryId,
  onFolderCreated,
}: NewFolderDialogProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Focus input when dialog opens
  useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus();
    }
  }, [open]);

  // Reset state when dialog closes
  useEffect(() => {
    if (!open) {
      setName('');
      setError(null);
    }
  }, [open]);

  const createMutation = useMutation({
    mutationFn: () =>
      createDirectory(libraryId, {
        name: name.trim(),
        parent_id: parentDirectoryId,
      }),
    onSuccess: () => {
      // Invalidate the browse query to refresh the file list
      queryClient.invalidateQueries({ queryKey: ['browse', libraryId] });
      onFolderCreated?.();
      onClose();
    },
    onError: (err: any) => {
      // Handle specific error cases
      if (err?.response?.status === 409) {
        setError(t('folder.nameExists'));
      } else {
        setError(err?.response?.data?.detail || t('common.error'));
      }
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const trimmedName = name.trim();

    if (!trimmedName) {
      setError(t('folder.nameRequired'));
      return;
    }

    // Basic validation for folder names
    if (/[<>:"/\\|?*]/.test(trimmedName)) {
      setError(t('folder.invalidCharacters', 'Folder name contains invalid characters'));
      return;
    }

    setError(null);
    createMutation.mutate();
  };

  const handleClose = () => {
    if (!createMutation.isPending) {
      onClose();
    }
  };

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && open && !createMutation.isPending) {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose, createMutation.isPending]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={handleClose}
      role="presentation"
    >
      <div
        className="bg-white dark:bg-slate-800 rounded-xl shadow-xl w-full max-w-md"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-labelledby="new-folder-dialog-title"
        aria-modal="true"
        aria-describedby="new-folder-dialog-description"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-700">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 dark:bg-blue-900/50 rounded-lg">
              <FolderPlus className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            </div>
            <h2
              id="new-folder-dialog-title"
              className="text-xl font-semibold text-slate-900 dark:text-slate-100"
            >
              {t('folder.createTitle')}
            </h2>
          </div>
          <button
            onClick={handleClose}
            disabled={createMutation.isPending}
            className={cn(
              'p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors',
              createMutation.isPending && 'opacity-50 cursor-not-allowed'
            )}
            aria-label={t('common.close')}
          >
            <X className="w-5 h-5 text-slate-500" />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-6">
          <p
            id="new-folder-dialog-description"
            className="sr-only"
          >
            {t('folder.createTitle')}
          </p>

          <div className="space-y-4">
            <div>
              <label
                htmlFor="folder-name"
                className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2"
              >
                {t('folder.name')}
              </label>
              <input
                ref={inputRef}
                id="folder-name"
                type="text"
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  setError(null);
                }}
                placeholder={t('folder.namePlaceholder')}
                disabled={createMutation.isPending}
                autoComplete="off"
                className={cn(
                  'w-full px-4 py-2.5 rounded-lg border transition-colors',
                  'bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100',
                  'placeholder-slate-400 dark:placeholder-slate-500',
                  'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                  error
                    ? 'border-red-500 dark:border-red-400'
                    : 'border-slate-300 dark:border-slate-600',
                  createMutation.isPending && 'opacity-50 cursor-not-allowed'
                )}
                aria-invalid={!!error}
                aria-describedby={error ? 'folder-name-error' : undefined}
              />
              {error && (
                <p
                  id="folder-name-error"
                  className="mt-2 text-sm text-red-600 dark:text-red-400"
                  role="alert"
                >
                  {error}
                </p>
              )}
            </div>
          </div>

          {/* Footer */}
          <div className="flex justify-end gap-3 mt-6">
            <button
              type="button"
              onClick={handleClose}
              disabled={createMutation.isPending}
              className={cn(
                'px-4 py-2 text-sm font-medium rounded-lg transition-colors',
                'text-slate-700 dark:text-slate-300',
                'hover:bg-slate-100 dark:hover:bg-slate-700',
                createMutation.isPending && 'opacity-50 cursor-not-allowed'
              )}
            >
              {t('common.cancel')}
            </button>
            <button
              type="submit"
              disabled={!name.trim() || createMutation.isPending}
              className={cn(
                'flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors',
                'text-white bg-blue-600 hover:bg-blue-700',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              {createMutation.isPending && (
                <Loader2 className="w-4 h-4 animate-spin" />
              )}
              {createMutation.isPending ? t('common.creating') : t('common.create')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
