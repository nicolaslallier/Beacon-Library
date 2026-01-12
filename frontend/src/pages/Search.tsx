/**
 * Search page with semantic search functionality
 * Uses ChromaDB vector database for intelligent document search
 */

import { useState, useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Search as SearchIcon,
  FileText,
  Image,
  Video,
  Music,
  FileSpreadsheet,
  Presentation,
  FileArchive,
  File,
  Loader2,
  AlertCircle,
  FolderOpen,
  Filter,
  X,
  Sparkles,
} from 'lucide-react';

import { searchApi, formatFileSize, highlightSearchTerms, getFileTypeFromMime } from '../services/search';
import type { SearchResult, SearchResponse } from '../services/search';
import { listLibraries } from '../services/files';
import type { Library, BrowseItem } from '../services/files';
import { PreviewDialog } from '../components/explorer/PreviewDialog';
import { cn } from '../lib/utils';

// File type icon mapping
const fileTypeIcons: Record<string, React.ElementType> = {
  image: Image,
  video: Video,
  audio: Music,
  pdf: FileText,
  document: FileText,
  spreadsheet: FileSpreadsheet,
  presentation: Presentation,
  text: FileText,
  archive: FileArchive,
  file: File,
};

function getFileIcon(mimeType: string): React.ElementType {
  const fileType = getFileTypeFromMime(mimeType);
  return fileTypeIcons[fileType] || File;
}

// Search result item component
function SearchResultItem({
  result,
  query,
  onPreview,
  onNavigate,
}: {
  result: SearchResult;
  query: string;
  onPreview: (result: SearchResult) => void;
  onNavigate: (libraryId: string, path: string) => void;
}) {
  const { t } = useTranslation();
  const FileIcon = getFileIcon(result.mime_type);
  const relevancePercent = Math.round(result.relevance_score * 100);

  return (
    <div
      className={cn(
        'group p-4 bg-white rounded-xl border border-slate-200',
        'hover:border-indigo-300 hover:shadow-lg hover:shadow-indigo-100/50',
        'transition-all duration-200 cursor-pointer'
      )}
      onClick={() => onPreview(result)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          onPreview(result);
        }
      }}
    >
      <div className="flex items-start gap-4">
        {/* File type icon */}
        <div className="flex-shrink-0 w-12 h-12 rounded-lg bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center border border-slate-200 group-hover:border-indigo-200 group-hover:from-indigo-50 group-hover:to-purple-50 transition-colors">
          <FileIcon className="w-6 h-6 text-slate-500 group-hover:text-indigo-600 transition-colors" />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* File name */}
          <h3 className="font-medium text-slate-900 truncate group-hover:text-indigo-600 transition-colors">
            {result.file_name}
          </h3>

          {/* Path and metadata */}
          <div className="flex items-center gap-2 mt-1 text-sm text-slate-500">
            <FolderOpen className="w-3.5 h-3.5" />
            <span className="truncate">{result.path || '/'}</span>
            <span className="text-slate-300">•</span>
            <span>{formatFileSize(result.size)}</span>
          </div>

          {/* Snippet with highlighted terms */}
          {result.snippet && (
            <p
              className="mt-2 text-sm text-slate-600 line-clamp-2"
              dangerouslySetInnerHTML={{
                __html: highlightSearchTerms(result.snippet, query),
              }}
            />
          )}
        </div>

        {/* Right side: relevance + navigate button */}
        <div className="flex-shrink-0 flex flex-col items-end gap-2">
          <div className="flex items-center gap-1.5 px-2 py-1 bg-gradient-to-r from-emerald-50 to-teal-50 rounded-full border border-emerald-200">
            <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
            <span className="text-xs font-medium text-emerald-700">
              {relevancePercent}%
            </span>
          </div>
          <span className="text-xs text-slate-400">{t('search.relevance')}</span>
          {/* Navigate to folder button */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onNavigate(result.library_id, result.path || '/');
            }}
            className="flex items-center gap-1 px-2 py-1 text-xs text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 rounded transition-colors"
            title={t('search.goToFolder', 'Go to folder')}
          >
            <FolderOpen className="w-3.5 h-3.5" />
            <span>{t('search.goToFolder', 'Go to folder')}</span>
          </button>
        </div>
      </div>
    </div>
  );
}

// Main Search component
export default function Search() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // State
  const [searchInput, setSearchInput] = useState(searchParams.get('q') || '');
  const [selectedLibrary, setSelectedLibrary] = useState<string>(
    searchParams.get('library') || ''
  );
  const [selectedMimeType, setSelectedMimeType] = useState<string>(
    searchParams.get('type') || ''
  );
  const [showFilters, setShowFilters] = useState(false);
  const [debouncedQuery, setDebouncedQuery] = useState(searchParams.get('q') || '');
  const [previewFile, setPreviewFile] = useState<BrowseItem | null>(null);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchInput);
      // Update URL params
      const params = new URLSearchParams();
      if (searchInput) params.set('q', searchInput);
      if (selectedLibrary) params.set('library', selectedLibrary);
      if (selectedMimeType) params.set('type', selectedMimeType);
      setSearchParams(params, { replace: true });
    }, 300);

    return () => clearTimeout(timer);
  }, [searchInput, selectedLibrary, selectedMimeType, setSearchParams]);

  // Fetch libraries for filter dropdown
  const { data: librariesData } = useQuery({
    queryKey: ['libraries'],
    queryFn: () => listLibraries(1, 100),
  });

  // Search query
  const {
    data: searchData,
    isLoading,
    isError,
    error,
  } = useQuery<SearchResponse>({
    queryKey: ['search', debouncedQuery, selectedLibrary, selectedMimeType],
    queryFn: () =>
      searchApi.search({
        query: debouncedQuery,
        libraryId: selectedLibrary || undefined,
        mimeType: selectedMimeType || undefined,
        limit: 50,
      }),
    enabled: debouncedQuery.length >= 2,
    staleTime: 30000,
  });

  // Navigate to file location
  const handleNavigate = useCallback(
    (libraryId: string, path: string) => {
      // Navigate to the file's directory in the explorer
      const directory = path.split('/').slice(0, -1).join('/') || '/';
      navigate(`/libraries/${libraryId}?path=${encodeURIComponent(directory)}`);
    },
    [navigate]
  );

  // Open preview dialog
  const handlePreview = useCallback((result: SearchResult) => {
    // Convert SearchResult to BrowseItem for PreviewDialog
    const browseItem: BrowseItem = {
      id: result.file_id,
      type: 'file',
      name: result.file_name,
      path: result.path || '/',
      size_bytes: result.size,
      content_type: result.mime_type,
      created_at: '',
      modified_at: '',
    };
    setPreviewFile(browseItem);
    setIsPreviewOpen(true);
  }, []);

  // Close preview dialog
  const handleClosePreview = useCallback(() => {
    setIsPreviewOpen(false);
    setPreviewFile(null);
  }, []);

  // Clear filters
  const clearFilters = () => {
    setSelectedLibrary('');
    setSelectedMimeType('');
  };

  // MIME type filter options
  const mimeTypeOptions = [
    { value: '', label: t('search.filters.allTypes') },
    { value: 'application/pdf', label: 'PDF' },
    { value: 'image/', label: t('search.filters.images') },
    { value: 'text/', label: t('search.filters.text') },
    { value: 'application/vnd.openxmlformats', label: t('search.filters.office') },
    { value: 'video/', label: t('search.filters.videos') },
    { value: 'audio/', label: t('search.filters.audio') },
  ];

  const hasActiveFilters = selectedLibrary || selectedMimeType;

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 shadow-lg shadow-indigo-500/30 mb-4">
          <SearchIcon className="w-8 h-8 text-white" />
        </div>
        <h1 className="text-3xl font-bold text-slate-900 mb-2">
          {t('search.title')}
        </h1>
        <p className="text-slate-600 max-w-md mx-auto">
          {t('search.subtitle')}
        </p>
      </div>

      {/* Search input */}
      <div className="relative mb-6">
        <div className="relative">
          <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder={t('search.placeholder')}
            className={cn(
              'w-full pl-12 pr-12 py-4 text-lg',
              'bg-white border-2 border-slate-200 rounded-2xl',
              'focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100',
              'placeholder:text-slate-400 transition-all duration-200'
            )}
            autoFocus
          />
          {searchInput && (
            <button
              onClick={() => setSearchInput('')}
              className="absolute right-4 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600 transition-colors"
              aria-label={t('common.cancel')}
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Filter toggle */}
        <div className="flex items-center justify-between mt-3">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={cn(
              'inline-flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg transition-colors',
              showFilters || hasActiveFilters
                ? 'bg-indigo-100 text-indigo-700'
                : 'text-slate-600 hover:bg-slate-100'
            )}
          >
            <Filter className="w-4 h-4" />
            {t('search.filters.title')}
            {hasActiveFilters && (
              <span className="ml-1 px-1.5 py-0.5 text-xs bg-indigo-600 text-white rounded-full">
                {[selectedLibrary, selectedMimeType].filter(Boolean).length}
              </span>
            )}
          </button>

          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="text-sm text-slate-500 hover:text-slate-700 transition-colors"
            >
              {t('search.filters.clear')}
            </button>
          )}
        </div>

        {/* Filters panel */}
        {showFilters && (
          <div className="mt-4 p-4 bg-slate-50 rounded-xl border border-slate-200 grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Library filter */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">
                {t('search.filters.library')}
              </label>
              <select
                value={selectedLibrary}
                onChange={(e) => setSelectedLibrary(e.target.value)}
                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
              >
                <option value="">{t('search.filters.allLibraries')}</option>
                {librariesData?.items.map((library: Library) => (
                  <option key={library.id} value={library.id}>
                    {library.name}
                  </option>
                ))}
              </select>
            </div>

            {/* File type filter */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">
                {t('search.filters.fileType')}
              </label>
              <select
                value={selectedMimeType}
                onChange={(e) => setSelectedMimeType(e.target.value)}
                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
              >
                {mimeTypeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}
      </div>

      {/* Results section */}
      <div className="space-y-4">
        {/* Loading state */}
        {isLoading && debouncedQuery.length >= 2 && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 text-indigo-600 animate-spin" />
            <span className="ml-3 text-slate-600">{t('search.searching')}</span>
          </div>
        )}

        {/* Error state */}
        {isError && (
          <div className="flex items-center justify-center py-12 text-red-600">
            <AlertCircle className="w-6 h-6 mr-2" />
            <span>
              {error instanceof Error ? error.message : t('search.error')}
            </span>
          </div>
        )}

        {/* Empty query state */}
        {!debouncedQuery && !isLoading && (
          <div className="text-center py-12">
            <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-gradient-to-br from-slate-100 to-slate-200 flex items-center justify-center">
              <Sparkles className="w-10 h-10 text-slate-400" />
            </div>
            <h3 className="text-lg font-medium text-slate-700 mb-2">
              {t('search.startSearching')}
            </h3>
            <p className="text-slate-500 max-w-md mx-auto">
              {t('search.startSearchingDesc')}
            </p>
          </div>
        )}

        {/* Too short query */}
        {debouncedQuery && debouncedQuery.length < 2 && !isLoading && (
          <div className="text-center py-8 text-slate-500">
            {t('search.minLength')}
          </div>
        )}

        {/* Results */}
        {searchData && !isLoading && (
          <>
            {/* Results count */}
            <div className="flex items-center justify-between text-sm text-slate-600 mb-4">
              <span>
                {t('search.resultsCount', { count: searchData.total })}
              </span>
              {searchData.total > 0 && (
                <span className="text-slate-400">
                  {t('search.sortedByRelevance')}
                </span>
              )}
            </div>

            {/* No results */}
            {searchData.results.length === 0 && (
              <div className="text-center py-12">
                <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-gradient-to-br from-amber-50 to-orange-100 flex items-center justify-center">
                  <SearchIcon className="w-10 h-10 text-amber-500" />
                </div>
                <h3 className="text-lg font-medium text-slate-700 mb-2">
                  {t('search.noResults')}
                </h3>
                <p className="text-slate-500 max-w-md mx-auto">
                  {t('search.noResultsDesc')}
                </p>
              </div>
            )}

            {/* Results list */}
            <div className="space-y-3">
              {searchData.results.map((result: SearchResult) => (
                <SearchResultItem
                  key={result.file_id}
                  result={result}
                  query={debouncedQuery}
                  onPreview={handlePreview}
                  onNavigate={handleNavigate}
                />
              ))}
            </div>
          </>
        )}
      </div>

      {/* Semantic search info */}
      <div className="mt-12 p-4 bg-gradient-to-r from-indigo-50 via-purple-50 to-pink-50 rounded-xl border border-indigo-100">
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <h4 className="font-medium text-slate-800">
              {t('search.semanticInfo.title')}
            </h4>
            <p className="text-sm text-slate-600 mt-1">
              {t('search.semanticInfo.description')}
            </p>
          </div>
        </div>
      </div>

      {/* Preview Dialog */}
      <PreviewDialog
        open={isPreviewOpen}
        onClose={handleClosePreview}
        file={previewFile}
      />
    </div>
  );
}
