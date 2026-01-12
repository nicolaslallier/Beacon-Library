/**
 * Search API service for semantic search functionality
 */

import { apiClient } from './api';

// Types
export interface SearchResult {
  file_id: string;
  file_name: string;
  library_id: string;
  path: string | null;
  mime_type: string;
  size: number;
  relevance_score: number;
  snippet: string;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
}

export interface SearchOptions {
  query: string;
  libraryId?: string;
  limit?: number;
  mimeType?: string;
}

// ============================================================================
// Search API
// ============================================================================

/**
 * Perform a semantic search across files
 */
export async function semanticSearch(
  options: SearchOptions
): Promise<SearchResponse> {
  const response = await apiClient.get<SearchResponse>('/search', {
    params: {
      q: options.query,
      library_id: options.libraryId,
      limit: options.limit || 20,
      mime_type: options.mimeType,
    },
  });
  return response.data;
}

/**
 * Get file type icon based on MIME type
 */
export function getFileTypeFromMime(mimeType: string): string {
  if (mimeType.startsWith('image/')) return 'image';
  if (mimeType.startsWith('video/')) return 'video';
  if (mimeType.startsWith('audio/')) return 'audio';
  if (mimeType.includes('pdf')) return 'pdf';
  if (mimeType.includes('word') || mimeType.includes('document')) return 'document';
  if (mimeType.includes('sheet') || mimeType.includes('excel')) return 'spreadsheet';
  if (mimeType.includes('presentation') || mimeType.includes('powerpoint')) return 'presentation';
  if (mimeType.includes('text/')) return 'text';
  if (mimeType.includes('zip') || mimeType.includes('archive') || mimeType.includes('compressed')) return 'archive';
  return 'file';
}

/**
 * Format file size for display
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

/**
 * Highlight search terms in text
 */
export function highlightSearchTerms(text: string, query: string): string {
  if (!query || !text) return text;
  
  // Split query into words and escape regex special characters
  const words = query
    .split(/\s+/)
    .filter(word => word.length > 2)
    .map(word => word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  
  if (words.length === 0) return text;
  
  const regex = new RegExp(`(${words.join('|')})`, 'gi');
  return text.replace(regex, '<mark class="bg-yellow-200 rounded px-0.5">$1</mark>');
}

// Search API object for consistency with other services
export const searchApi = {
  search: semanticSearch,
};

export default searchApi;
