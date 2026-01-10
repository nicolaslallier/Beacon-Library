/**
 * Explorer page - File browser for a specific library
 */

import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, RefreshCw } from 'lucide-react';

import { FileExplorer } from '../components/explorer/FileExplorer';
import { getLibrary } from '../services/files';
import { useAuth, RequireAuth } from '../hooks/useAuth';

function ExplorerContent() {
  const { libraryId } = useParams<{ libraryId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();

  // Fetch library details
  const {
    data: library,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['library', libraryId],
    queryFn: () => getLibrary(libraryId!),
    enabled: !!libraryId,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
        <span className="sr-only">{t('common.loading')}</span>
      </div>
    );
  }

  if (error || !library) {
    return (
      <div className="flex flex-col items-center justify-center h-screen">
        <h1 className="text-2xl font-bold text-red-600">{t('error.notFound')}</h1>
        <p className="text-slate-600 dark:text-slate-400 mt-2">
          {t('library.notFound', 'Library not found')}
        </p>
        <button
          onClick={() => navigate('/libraries')}
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          {t('library.backToList', 'Back to Libraries')}
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <header className="flex items-center gap-4 px-6 py-4 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700">
        <button
          onClick={() => navigate('/libraries')}
          className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          aria-label={t('common.back', 'Back')}
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            {library.name}
          </h1>
          {library.description && (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {library.description}
            </p>
          )}
        </div>
      </header>

      {/* File Explorer */}
      <main className="flex-1 overflow-hidden p-4">
        <FileExplorer
          libraryId={library.id}
          libraryName={library.name}
          className="h-full"
        />
      </main>
    </div>
  );
}

export default function Explorer() {
  return (
    <RequireAuth>
      <ExplorerContent />
    </RequireAuth>
  );
}
