/**
 * Libraries page - List and manage document libraries
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Plus,
  Library,
  Folder,
  MoreVertical,
  Trash2,
  Settings,
  RefreshCw,
} from 'lucide-react';

import { cn, formatBytes, formatDate } from '../lib/utils';
import {
  listLibraries,
  createLibrary,
  deleteLibrary,
  Library as LibraryType,
} from '../services/files';
import { useAuth, RequireAuth } from '../hooks/useAuth';

function LibraryCard({ library }: { library: LibraryType }) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [showMenu, setShowMenu] = useState(false);

  const deleteMutation = useMutation({
    mutationFn: () => deleteLibrary(library.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['libraries'] });
    },
  });

  const handleDelete = () => {
    if (confirm(t('library.deleteConfirm'))) {
      deleteMutation.mutate();
    }
  };

  return (
    <div
      className={cn(
        'relative bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700',
        'hover:shadow-lg hover:border-blue-300 dark:hover:border-blue-600 transition-all cursor-pointer',
        'focus-within:ring-2 focus-within:ring-blue-500'
      )}
    >
      <button
        onClick={() => navigate(`/libraries/${library.id}`)}
        className="w-full p-6 text-left focus:outline-none"
        aria-label={`${t('accessibility.openLibrary', 'Open')} ${library.name}`}
      >
        <div className="flex items-start gap-4">
          <div className="p-3 bg-blue-100 dark:bg-blue-900/50 rounded-lg">
            <Library className="w-8 h-8 text-blue-600 dark:text-blue-400" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-slate-900 dark:text-slate-100 truncate">
              {library.name}
            </h3>
            {library.description && (
              <p className="text-sm text-slate-500 dark:text-slate-400 line-clamp-2 mt-1">
                {library.description}
              </p>
            )}
            <div className="flex items-center gap-4 mt-3 text-xs text-slate-400 dark:text-slate-500">
              <span className="flex items-center gap-1">
                <Folder className="w-3 h-3" />
                {library.file_count} {t('common.files', 'files')}
              </span>
              <span>{formatBytes(library.total_size_bytes)}</span>
            </div>
          </div>
        </div>
      </button>

      {/* Menu button */}
      <div className="absolute top-4 right-4">
        <button
          onClick={(e) => {
            e.stopPropagation();
            setShowMenu(!showMenu);
          }}
          className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
          aria-label={t('common.actions')}
          aria-expanded={showMenu}
        >
          <MoreVertical className="w-4 h-4 text-slate-400" />
        </button>

        {showMenu && (
          <div className="absolute right-0 mt-1 w-48 bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 py-1 z-10">
            <button
              onClick={() => {
                setShowMenu(false);
                navigate(`/libraries/${library.id}/settings`);
              }}
              className="flex items-center gap-2 w-full px-4 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700"
            >
              <Settings className="w-4 h-4" />
              {t('nav.settings')}
            </button>
            <button
              onClick={() => {
                setShowMenu(false);
                handleDelete();
              }}
              className="flex items-center gap-2 w-full px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
            >
              <Trash2 className="w-4 h-4" />
              {t('common.delete')}
            </button>
          </div>
        )}
      </div>

      {/* MCP badge */}
      {library.mcp_write_enabled && (
        <div className="absolute bottom-4 right-4">
          <span className="px-2 py-1 text-xs font-medium bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300 rounded">
            MCP
          </span>
        </div>
      )}
    </div>
  );
}

function CreateLibraryDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [mcpEnabled, setMcpEnabled] = useState(false);

  const createMutation = useMutation({
    mutationFn: () =>
      createLibrary({
        name,
        description: description || undefined,
        mcp_write_enabled: mcpEnabled,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['libraries'] });
      onClose();
      setName('');
      setDescription('');
      setMcpEnabled(false);
    },
  });

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-slate-800 rounded-xl shadow-xl w-full max-w-md p-6"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-labelledby="create-library-title"
      >
        <h2
          id="create-library-title"
          className="text-xl font-semibold text-slate-900 dark:text-slate-100 mb-4"
        >
          {t('library.createTitle')}
        </h2>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate();
          }}
        >
          <div className="space-y-4">
            <div>
              <label
                htmlFor="library-name"
                className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1"
              >
                {t('library.name')}
              </label>
              <input
                id="library-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t('library.namePlaceholder')}
                required
                className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div>
              <label
                htmlFor="library-description"
                className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1"
              >
                {t('library.description')}
              </label>
              <textarea
                id="library-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={t('library.descriptionPlaceholder')}
                rows={3}
                className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div className="flex items-center gap-3">
              <input
                id="mcp-enabled"
                type="checkbox"
                checked={mcpEnabled}
                onChange={(e) => setMcpEnabled(e.target.checked)}
                className="w-4 h-4 text-blue-600 border-slate-300 rounded focus:ring-blue-500"
              />
              <div>
                <label
                  htmlFor="mcp-enabled"
                  className="text-sm font-medium text-slate-700 dark:text-slate-300"
                >
                  {t('library.mcpWriteEnabled')}
                </label>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {t('library.mcpWriteEnabledHelp')}
                </p>
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-3 mt-6">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg"
            >
              {t('common.cancel')}
            </button>
            <button
              type="submit"
              disabled={!name || createMutation.isPending}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {createMutation.isPending ? t('common.loading') : t('common.create')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function LibrariesContent() {
  const { t } = useTranslation();
  const [showCreateDialog, setShowCreateDialog] = useState(false);

  const {
    data: librariesData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['libraries'],
    queryFn: () => listLibraries(),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64">
        <p className="text-red-500">{t('common.error')}</p>
        <button
          onClick={() => refetch()}
          className="mt-2 px-4 py-2 bg-red-100 dark:bg-red-900 rounded hover:bg-red-200 dark:hover:bg-red-800"
        >
          {t('common.retry')}
        </button>
      </div>
    );
  }

  const libraries = librariesData?.items || [];

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100">
              {t('library.title')}
            </h1>
            <p className="text-slate-500 dark:text-slate-400 mt-1">
              {t('library.subtitle', 'Manage your document libraries')}
            </p>
          </div>
          <button
            onClick={() => setShowCreateDialog(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors"
          >
            <Plus className="w-5 h-5" />
            {t('library.create')}
          </button>
        </div>

        {/* Libraries grid */}
        {libraries.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Library className="w-16 h-16 text-slate-300 dark:text-slate-600 mb-4" />
            <h2 className="text-xl font-semibold text-slate-700 dark:text-slate-300">
              {t('library.empty')}
            </h2>
            <p className="text-slate-500 dark:text-slate-400 mt-2 max-w-md">
              {t('library.emptyDescription')}
            </p>
            <button
              onClick={() => setShowCreateDialog(true)}
              className="mt-6 flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg"
            >
              <Plus className="w-5 h-5" />
              {t('library.create')}
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {libraries.map((library) => (
              <LibraryCard key={library.id} library={library} />
            ))}
          </div>
        )}
      </div>

      <CreateLibraryDialog
        open={showCreateDialog}
        onClose={() => setShowCreateDialog(false)}
      />
    </div>
  );
}

export default function Libraries() {
  return (
    <RequireAuth>
      <LibrariesContent />
    </RequireAuth>
  );
}
