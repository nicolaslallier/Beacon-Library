/**
 * Preview Dialog for viewing file previews
 * WCAG AAA compliant
 */

import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import {
  X,
  Download,
  RefreshCw,
  FileText,
  Image,
  Film,
  Music,
  File,
  AlertCircle,
  Maximize2,
  Minimize2,
} from 'lucide-react';

import { cn, formatBytes, getFileIcon } from '../../lib/utils';
import {
  checkPreviewAvailability,
  getPreviewUrl,
  downloadFile,
} from '../../services/files';
import type { BrowseItem } from '../../services/files';

interface PreviewDialogProps {
  open: boolean;
  onClose: () => void;
  file: BrowseItem | null;
}

function getIconForType(iconType: string) {
  switch (iconType) {
    case 'image':
      return <Image className="w-16 h-16 text-blue-500" />;
    case 'video':
      return <Film className="w-16 h-16 text-purple-500" />;
    case 'audio':
      return <Music className="w-16 h-16 text-pink-500" />;
    case 'text':
    case 'document':
    case 'pdf':
      return <FileText className="w-16 h-16 text-orange-500" />;
    default:
      return <File className="w-16 h-16 text-slate-400" />;
  }
}

export function PreviewDialog({ open, onClose, file }: PreviewDialogProps) {
  const { t } = useTranslation();
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [imageError, setImageError] = useState(false);

  // Check preview availability
  const {
    data: previewInfo,
    isLoading: isCheckingPreview,
    error: previewCheckError,
  } = useQuery({
    queryKey: ['preview-check', file?.id],
    queryFn: () => checkPreviewAvailability(file!.id),
    enabled: !!file && open,
  });

  // Reset state when dialog opens/closes
  useEffect(() => {
    if (!open) {
      setIsFullscreen(false);
      setImageError(false);
    }
  }, [open]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && open) {
        if (isFullscreen) {
          setIsFullscreen(false);
        } else {
          onClose();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose, isFullscreen]);

  // Download handler
  const handleDownload = useCallback(async () => {
    if (!file) return;

    try {
      const blob = await downloadFile(file.id);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = file.name;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Download failed:', error);
    }
  }, [file]);

  if (!open || !file) return null;

  const canPreview = previewInfo?.can_preview && !imageError;
  const previewUrl = getPreviewUrl(file.id);
  const iconType = getFileIcon(file.content_type || '', file.name);

  return (
    <div
      className={cn(
        'fixed inset-0 z-50 flex items-center justify-center bg-black/70',
        isFullscreen && 'bg-black/90'
      )}
      onClick={onClose}
      role="presentation"
    >
      <div
        className={cn(
          'bg-white dark:bg-slate-800 rounded-xl shadow-xl flex flex-col overflow-hidden',
          isFullscreen
            ? 'w-full h-full rounded-none'
            : 'w-full max-w-4xl max-h-[90vh]'
        )}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-labelledby="preview-dialog-title"
        aria-modal="true"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900">
          <div className="flex items-center gap-3 min-w-0">
            <div className="shrink-0">
              {getIconForType(iconType)}
            </div>
            <div className="min-w-0">
              <h2
                id="preview-dialog-title"
                className="text-lg font-semibold text-slate-900 dark:text-slate-100 truncate"
              >
                {file.name}
              </h2>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {file.content_type || t('file.type')} • {formatBytes(file.size_bytes || 0)}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Download button */}
            <button
              onClick={handleDownload}
              className="p-2 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
              aria-label={t('explorer.download')}
              title={t('explorer.download')}
            >
              <Download className="w-5 h-5 text-slate-600 dark:text-slate-300" />
            </button>

            {/* Fullscreen toggle */}
            <button
              onClick={() => setIsFullscreen(!isFullscreen)}
              className="p-2 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
              aria-label={isFullscreen ? t('common.minimize', 'Minimize') : t('common.maximize', 'Maximize')}
              title={isFullscreen ? t('common.minimize', 'Minimize') : t('common.maximize', 'Maximize')}
            >
              {isFullscreen ? (
                <Minimize2 className="w-5 h-5 text-slate-600 dark:text-slate-300" />
              ) : (
                <Maximize2 className="w-5 h-5 text-slate-600 dark:text-slate-300" />
              )}
            </button>

            {/* Close button */}
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
              aria-label={t('common.close')}
            >
              <X className="w-5 h-5 text-slate-600 dark:text-slate-300" />
            </button>
          </div>
        </div>

        {/* Preview content */}
        <div
          className={cn(
            'flex-1 overflow-auto flex items-center justify-center p-4',
            isFullscreen ? 'bg-black' : 'bg-slate-100 dark:bg-slate-900'
          )}
        >
          {isCheckingPreview ? (
            <div className="flex flex-col items-center gap-4 text-slate-500">
              <RefreshCw className="w-8 h-8 animate-spin" />
              <p>{t('common.loading')}</p>
            </div>
          ) : previewCheckError ? (
            <div className="flex flex-col items-center gap-4 text-slate-500">
              <AlertCircle className="w-12 h-12 text-amber-500" />
              <p>{t('common.error')}</p>
            </div>
          ) : canPreview ? (
            // Render preview based on file type
            iconType === 'image' ? (
              <img
                src={previewUrl}
                alt={file.name}
                className={cn(
                  'max-w-full max-h-full object-contain',
                  isFullscreen && 'w-full h-full'
                )}
                onError={() => setImageError(true)}
              />
            ) : iconType === 'video' ? (
              <video
                src={previewUrl}
                controls
                className="max-w-full max-h-full"
                aria-label={file.name}
              >
                {t('file.noPreview')}
              </video>
            ) : iconType === 'audio' ? (
              <div className="flex flex-col items-center gap-6">
                {getIconForType(iconType)}
                <audio
                  src={previewUrl}
                  controls
                  className="w-full max-w-md"
                  aria-label={file.name}
                >
                  {t('file.noPreview')}
                </audio>
              </div>
            ) : iconType === 'pdf' ? (
              <iframe
                src={previewUrl}
                className="w-full h-full min-h-[500px] border-0"
                title={file.name}
              />
            ) : (
              // For text/code files, show in iframe or embed
              <iframe
                src={previewUrl}
                className="w-full h-full min-h-[500px] bg-white border-0"
                title={file.name}
              />
            )
          ) : (
            // No preview available
            <div className="flex flex-col items-center gap-4 text-center">
              {getIconForType(iconType)}
              <div>
                <p className="text-lg font-medium text-slate-700 dark:text-slate-300">
                  {t('file.noPreview')}
                </p>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                  {previewInfo?.mime_type || file.content_type || t('file.type')}
                </p>
                {!previewInfo?.size_ok && (
                  <p className="text-sm text-amber-600 dark:text-amber-400 mt-2">
                    {t('preview.fileTooLarge', 'File is too large for preview')}
                  </p>
                )}
              </div>
              <button
                onClick={handleDownload}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
              >
                <Download className="w-4 h-4" />
                {t('explorer.download')}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
