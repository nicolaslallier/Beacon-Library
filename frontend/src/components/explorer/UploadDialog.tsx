/**
 * Upload Dialog with drag-and-drop and chunked upload support
 * WCAG AAA compliant
 */

import { useState, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useDropzone } from 'react-dropzone';
import {
  Upload,
  X,
  File,
  CheckCircle,
  XCircle,
  AlertCircle,
  Loader2,
} from 'lucide-react';

import { cn, formatBytes } from '../../lib/utils';
import {
  uploadFile,
  UploadProgress,
  DuplicateConflict,
} from '../../services/files';

interface UploadDialogProps {
  open: boolean;
  onClose: () => void;
  libraryId: string;
  directoryId?: string;
  onUploadComplete: () => void;
}

interface FileUpload {
  file: File;
  id: string;
  status: 'pending' | 'uploading' | 'complete' | 'error' | 'conflict';
  progress: number;
  error?: string;
  conflict?: DuplicateConflict;
}

export function UploadDialog({
  open,
  onClose,
  libraryId,
  directoryId,
  onUploadComplete,
}: UploadDialogProps) {
  const { t } = useTranslation();
  const [uploads, setUploads] = useState<FileUpload[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const abortController = useRef<AbortController | null>(null);

  // Handle file drop
  const onDrop = useCallback((acceptedFiles: File[]) => {
    const newUploads: FileUpload[] = acceptedFiles.map((file) => ({
      file,
      id: `${file.name}-${Date.now()}-${Math.random()}`,
      status: 'pending',
      progress: 0,
    }));
    setUploads((prev) => [...prev, ...newUploads]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: true,
  });

  // Remove a file from the queue
  const removeFile = useCallback((id: string) => {
    setUploads((prev) => prev.filter((u) => u.id !== id));
  }, []);

  // Handle duplicate conflict resolution
  const handleConflictResolution = useCallback(
    async (upload: FileUpload, action: 'overwrite' | 'rename' | 'cancel') => {
      if (action === 'cancel') {
        removeFile(upload.id);
        return;
      }

      // Retry upload with the chosen action
      setUploads((prev) =>
        prev.map((u) =>
          u.id === upload.id ? { ...u, status: 'uploading', conflict: undefined } : u
        )
      );

      try {
        await uploadFile(libraryId, upload.file, {
          directoryId,
          onDuplicate: action,
          onProgress: (progress: UploadProgress) => {
            setUploads((prev) =>
              prev.map((u) =>
                u.id === upload.id ? { ...u, progress: progress.percent } : u
              )
            );
          },
        });

        setUploads((prev) =>
          prev.map((u) =>
            u.id === upload.id ? { ...u, status: 'complete', progress: 100 } : u
          )
        );
      } catch (error) {
        setUploads((prev) =>
          prev.map((u) =>
            u.id === upload.id
              ? { ...u, status: 'error', error: String(error) }
              : u
          )
        );
      }
    },
    [libraryId, directoryId, removeFile]
  );

  // Start uploading all files
  const startUpload = useCallback(async () => {
    setIsUploading(true);
    abortController.current = new AbortController();

    const pendingUploads = uploads.filter((u) => u.status === 'pending');

    for (const upload of pendingUploads) {
      if (abortController.current.signal.aborted) break;

      setUploads((prev) =>
        prev.map((u) =>
          u.id === upload.id ? { ...u, status: 'uploading' } : u
        )
      );

      try {
        const result = await uploadFile(libraryId, upload.file, {
          directoryId,
          onDuplicate: 'ask',
          onProgress: (progress: UploadProgress) => {
            setUploads((prev) =>
              prev.map((u) =>
                u.id === upload.id ? { ...u, progress: progress.percent } : u
              )
            );
          },
          onConflict: async (conflict: DuplicateConflict) => {
            // Show conflict in UI
            setUploads((prev) =>
              prev.map((u) =>
                u.id === upload.id ? { ...u, status: 'conflict', conflict } : u
              )
            );
            // Wait for user decision (handled by UI)
            return 'cancel'; // Default to cancel, user will retry with action
          },
        });

        if (result) {
          setUploads((prev) =>
            prev.map((u) =>
              u.id === upload.id ? { ...u, status: 'complete', progress: 100 } : u
            )
          );
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        if (errorMessage !== 'Duplicate file conflict') {
          setUploads((prev) =>
            prev.map((u) =>
              u.id === upload.id
                ? { ...u, status: 'error', error: errorMessage }
                : u
            )
          );
        }
      }
    }

    setIsUploading(false);
    onUploadComplete();
  }, [uploads, libraryId, directoryId, onUploadComplete]);

  // Cancel all uploads
  const cancelUpload = useCallback(() => {
    abortController.current?.abort();
    setIsUploading(false);
  }, []);

  // Close dialog
  const handleClose = useCallback(() => {
    if (isUploading) {
      if (confirm(t('upload.cancelConfirm', 'Cancel uploads?'))) {
        cancelUpload();
        onClose();
      }
    } else {
      setUploads([]);
      onClose();
    }
  }, [isUploading, cancelUpload, onClose, t]);

  // Stats
  const completedCount = uploads.filter((u) => u.status === 'complete').length;
  const errorCount = uploads.filter((u) => u.status === 'error').length;
  const conflictCount = uploads.filter((u) => u.status === 'conflict').length;
  const pendingCount = uploads.filter(
    (u) => u.status === 'pending' || u.status === 'uploading'
  ).length;

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={handleClose}
    >
      <div
        className="bg-white dark:bg-slate-800 rounded-xl shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-labelledby="upload-dialog-title"
        aria-modal="true"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-700">
          <h2
            id="upload-dialog-title"
            className="text-xl font-semibold text-slate-900 dark:text-slate-100"
          >
            {t('upload.title')}
          </h2>
          <button
            onClick={handleClose}
            className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700"
            aria-label={t('common.close')}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Drop zone */}
        <div
          {...getRootProps()}
          className={cn(
            'mx-6 mt-4 p-8 border-2 border-dashed rounded-lg text-center cursor-pointer transition-colors',
            isDragActive
              ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
              : 'border-slate-300 dark:border-slate-600 hover:border-blue-400 dark:hover:border-blue-500'
          )}
        >
          <input {...getInputProps()} aria-label={t('upload.browse')} />
          <Upload
            className={cn(
              'w-12 h-12 mx-auto mb-4',
              isDragActive ? 'text-blue-500' : 'text-slate-400'
            )}
          />
          <p className="text-lg font-medium text-slate-700 dark:text-slate-300">
            {isDragActive ? t('explorer.dropzone') : t('upload.dragDrop')}
          </p>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            {t('upload.or')} <span className="text-blue-600 underline">{t('upload.browse')}</span>
          </p>
        </div>

        {/* File list */}
        {uploads.length > 0 && (
          <div className="flex-1 overflow-auto px-6 py-4">
            <ul className="space-y-2" role="list" aria-label={t('upload.fileList', 'Files to upload')}>
              {uploads.map((upload) => (
                <li
                  key={upload.id}
                  className="flex items-center gap-3 p-3 bg-slate-50 dark:bg-slate-700/50 rounded-lg"
                >
                  {/* Status icon */}
                  {upload.status === 'complete' && (
                    <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0" />
                  )}
                  {upload.status === 'error' && (
                    <XCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
                  )}
                  {upload.status === 'conflict' && (
                    <AlertCircle className="w-5 h-5 text-amber-500 flex-shrink-0" />
                  )}
                  {upload.status === 'uploading' && (
                    <Loader2 className="w-5 h-5 text-blue-500 animate-spin flex-shrink-0" />
                  )}
                  {upload.status === 'pending' && (
                    <File className="w-5 h-5 text-slate-400 flex-shrink-0" />
                  )}

                  {/* File info */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
                      {upload.file.name}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {formatBytes(upload.file.size)}
                      {upload.status === 'uploading' && ` • ${upload.progress}%`}
                      {upload.status === 'error' && ` • ${upload.error}`}
                    </p>

                    {/* Progress bar */}
                    {upload.status === 'uploading' && (
                      <div className="mt-1 h-1 bg-slate-200 dark:bg-slate-600 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-500 transition-all duration-300"
                          style={{ width: `${upload.progress}%` }}
                          role="progressbar"
                          aria-valuenow={upload.progress}
                          aria-valuemin={0}
                          aria-valuemax={100}
                        />
                      </div>
                    )}

                    {/* Conflict resolution */}
                    {upload.status === 'conflict' && upload.conflict && (
                      <div className="mt-2 flex items-center gap-2">
                        <span className="text-xs text-amber-600 dark:text-amber-400">
                          {t('upload.duplicate.message', { filename: upload.file.name })}
                        </span>
                        <div className="flex gap-1">
                          <button
                            onClick={() => handleConflictResolution(upload, 'overwrite')}
                            className="px-2 py-1 text-xs bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 rounded"
                          >
                            {t('upload.duplicate.overwrite')}
                          </button>
                          <button
                            onClick={() => handleConflictResolution(upload, 'rename')}
                            className="px-2 py-1 text-xs bg-slate-100 dark:bg-slate-600 text-slate-700 dark:text-slate-300 rounded"
                          >
                            {t('upload.duplicate.rename')}
                          </button>
                          <button
                            onClick={() => handleConflictResolution(upload, 'cancel')}
                            className="px-2 py-1 text-xs bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300 rounded"
                          >
                            {t('upload.duplicate.skip')}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Remove button */}
                  {(upload.status === 'pending' || upload.status === 'error') && (
                    <button
                      onClick={() => removeFile(upload.id)}
                      className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-600"
                      aria-label={t('common.remove', 'Remove')}
                    >
                      <X className="w-4 h-4 text-slate-400" />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-200 dark:border-slate-700">
          <div className="text-sm text-slate-500 dark:text-slate-400">
            {uploads.length > 0 && (
              <>
                {completedCount > 0 && (
                  <span className="text-green-600 dark:text-green-400">
                    {completedCount} {t('upload.complete')}
                  </span>
                )}
                {errorCount > 0 && (
                  <span className="text-red-600 dark:text-red-400 ml-2">
                    {errorCount} {t('upload.failed')}
                  </span>
                )}
                {conflictCount > 0 && (
                  <span className="text-amber-600 dark:text-amber-400 ml-2">
                    {conflictCount} {t('upload.conflicts', 'conflicts')}
                  </span>
                )}
              </>
            )}
          </div>
          <div className="flex gap-3">
            <button
              onClick={handleClose}
              className="px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg"
            >
              {t('common.close')}
            </button>
            {isUploading ? (
              <button
                onClick={cancelUpload}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg"
              >
                {t('upload.cancel')}
              </button>
            ) : (
              <button
                onClick={startUpload}
                disabled={pendingCount === 0}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {t('explorer.upload')} ({pendingCount})
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
