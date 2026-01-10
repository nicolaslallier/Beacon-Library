/**
 * File and Library API service
 */

import axios from 'axios';
import { config } from '../config';

// Types
export interface Library {
  id: string;
  name: string;
  description?: string;
  bucket_name: string;
  owner_id: string;
  created_by: string;
  mcp_write_enabled: boolean;
  max_file_size_bytes?: number;
  created_at: string;
  updated_at: string;
  file_count: number;
  total_size_bytes: number;
}

export interface Directory {
  id: string;
  library_id: string;
  parent_id?: string;
  name: string;
  path: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  item_count: number;
}

export interface FileMetadata {
  id: string;
  library_id: string;
  directory_id?: string;
  filename: string;
  path: string;
  size_bytes: number;
  checksum_sha256: string;
  content_type: string;
  current_version: number;
  created_by: string;
  modified_by: string;
  created_at: string;
  updated_at: string;
  download_url?: string;
}

export type ItemType = 'directory' | 'file';

export interface BrowseItem {
  id: string;
  name: string;
  type: ItemType;
  path: string;
  created_at: string;
  updated_at: string;
  created_by: string;
  size_bytes?: number;
  content_type?: string;
  checksum_sha256?: string;
  current_version?: number;
  item_count?: number;
}

export interface BrowseResponse {
  library_id: string;
  path: string;
  parent_id?: string;
  breadcrumb: Array<{ name: string; path: string; id?: string }>;
  items: BrowseItem[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
  sort_by: string;
  sort_order: string;
}

export interface UploadInitResponse {
  upload_id: string;
  file_id: string;
  chunk_size: number;
  total_chunks: number;
  presigned_urls?: string[];
}

export interface DuplicateConflict {
  conflict: boolean;
  message: string;
  options: string[];
  existing_file: FileMetadata;
  suggested_name?: string;
}

// API client with auth header injection
const apiClient = axios.create({
  baseURL: config.apiUrl,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/vnd.beacon.v1+json',
  },
});

// Add auth token to requests
export function setAuthToken(token: string | null) {
  if (token) {
    apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  } else {
    delete apiClient.defaults.headers.common['Authorization'];
  }
}

// ============================================================================
// Library API
// ============================================================================

export async function listLibraries(page = 1, pageSize = 50): Promise<{
  items: Library[];
  total: number;
  has_more: boolean;
}> {
  const response = await apiClient.get('/api/libraries', {
    params: { page, page_size: pageSize },
  });
  return response.data;
}

export async function getLibrary(libraryId: string): Promise<Library> {
  const response = await apiClient.get(`/api/libraries/${libraryId}`);
  return response.data;
}

export async function createLibrary(data: {
  name: string;
  description?: string;
  mcp_write_enabled?: boolean;
}): Promise<Library> {
  const response = await apiClient.post('/api/libraries', data);
  return response.data;
}

export async function updateLibrary(
  libraryId: string,
  data: Partial<{
    name: string;
    description: string;
    mcp_write_enabled: boolean;
  }>
): Promise<Library> {
  const response = await apiClient.patch(`/api/libraries/${libraryId}`, data);
  return response.data;
}

export async function deleteLibrary(libraryId: string): Promise<void> {
  await apiClient.delete(`/api/libraries/${libraryId}`);
}

// ============================================================================
// Browse API
// ============================================================================

export async function browseLibrary(
  libraryId: string,
  options: {
    path?: string;
    directoryId?: string;
    page?: number;
    pageSize?: number;
    sortBy?: string;
    sortOrder?: 'asc' | 'desc';
  } = {}
): Promise<BrowseResponse> {
  const response = await apiClient.get(`/api/libraries/${libraryId}/browse`, {
    params: {
      path: options.path || '/',
      directory_id: options.directoryId,
      page: options.page || 1,
      page_size: options.pageSize || 50,
      sort_by: options.sortBy || 'name',
      sort_order: options.sortOrder || 'asc',
    },
  });
  return response.data;
}

// ============================================================================
// Directory API
// ============================================================================

export async function createDirectory(
  libraryId: string,
  data: { name: string; parent_id?: string }
): Promise<Directory> {
  const response = await apiClient.post(
    `/api/libraries/${libraryId}/directories`,
    data
  );
  return response.data;
}

export async function renameDirectory(
  libraryId: string,
  directoryId: string,
  name: string
): Promise<Directory> {
  const response = await apiClient.patch(
    `/api/libraries/${libraryId}/directories/${directoryId}`,
    { name }
  );
  return response.data;
}

export async function moveDirectory(
  libraryId: string,
  directoryId: string,
  newParentId?: string
): Promise<Directory> {
  const response = await apiClient.post(
    `/api/libraries/${libraryId}/directories/${directoryId}/move`,
    { new_parent_id: newParentId }
  );
  return response.data;
}

export async function deleteDirectory(
  libraryId: string,
  directoryId: string
): Promise<void> {
  await apiClient.delete(
    `/api/libraries/${libraryId}/directories/${directoryId}`
  );
}

// ============================================================================
// File API
// ============================================================================

export async function getFile(fileId: string): Promise<FileMetadata> {
  const response = await apiClient.get(`/api/files/${fileId}`);
  return response.data;
}

export async function renameFile(
  fileId: string,
  filename: string
): Promise<FileMetadata> {
  const response = await apiClient.patch(`/api/files/${fileId}`, { filename });
  return response.data;
}

export async function deleteFile(fileId: string): Promise<void> {
  await apiClient.delete(`/api/files/${fileId}`);
}

export async function downloadFile(fileId: string): Promise<Blob> {
  const response = await apiClient.get(`/api/files/${fileId}/download`, {
    responseType: 'blob',
  });
  return response.data;
}

// ============================================================================
// Upload API
// ============================================================================

export async function initUpload(
  libraryId: string,
  options: {
    filename: string;
    contentType: string;
    sizeBytes: number;
    directoryId?: string;
    onDuplicate?: 'ask' | 'overwrite' | 'rename';
  }
): Promise<UploadInitResponse | DuplicateConflict> {
  const response = await apiClient.post('/api/files/upload/init', null, {
    params: {
      library_id: libraryId,
      filename: options.filename,
      content_type: options.contentType,
      size_bytes: options.sizeBytes,
      directory_id: options.directoryId,
      on_duplicate: options.onDuplicate || 'ask',
    },
  });
  return response.data;
}

export async function uploadPart(
  uploadId: string,
  partNumber: number,
  data: Blob
): Promise<{ part_number: number; etag: string; size_bytes: number }> {
  const formData = new FormData();
  formData.append('file', data);

  const response = await apiClient.post('/api/files/upload/part', formData, {
    params: {
      upload_id: uploadId,
      part_number: partNumber,
    },
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
}

export async function completeUpload(
  uploadId: string,
  parts: Array<{ part_number: number; etag: string; size_bytes: number }>,
  checksum?: string
): Promise<{ file: FileMetadata }> {
  const response = await apiClient.post('/api/files/upload/complete', {
    upload_id: uploadId,
    parts,
    checksum_sha256: checksum,
  });
  return response.data;
}

// ============================================================================
// Helper: Upload file with chunking
// ============================================================================

export interface UploadProgress {
  loaded: number;
  total: number;
  percent: number;
  currentChunk: number;
  totalChunks: number;
}

export async function uploadFile(
  libraryId: string,
  file: File,
  options: {
    directoryId?: string;
    onDuplicate?: 'ask' | 'overwrite' | 'rename';
    onProgress?: (progress: UploadProgress) => void;
    onConflict?: (conflict: DuplicateConflict) => Promise<'overwrite' | 'rename' | 'cancel'>;
  } = {}
): Promise<FileMetadata | null> {
  // Initialize upload
  let initResponse = await initUpload(libraryId, {
    filename: file.name,
    contentType: file.type || 'application/octet-stream',
    sizeBytes: file.size,
    directoryId: options.directoryId,
    onDuplicate: options.onDuplicate,
  });

  // Handle duplicate conflict
  if ('conflict' in initResponse && initResponse.conflict) {
    if (options.onConflict) {
      const action = await options.onConflict(initResponse);
      if (action === 'cancel') {
        return null;
      }
      // Retry with the chosen action
      initResponse = await initUpload(libraryId, {
        filename: file.name,
        contentType: file.type || 'application/octet-stream',
        sizeBytes: file.size,
        directoryId: options.directoryId,
        onDuplicate: action,
      }) as UploadInitResponse;
    } else {
      throw new Error('Duplicate file conflict');
    }
  }

  const uploadInit = initResponse as UploadInitResponse;
  const { upload_id, chunk_size, total_chunks } = uploadInit;

  // Upload chunks
  const parts: Array<{ part_number: number; etag: string; size_bytes: number }> = [];
  let uploadedBytes = 0;

  for (let i = 0; i < total_chunks; i++) {
    const start = i * chunk_size;
    const end = Math.min(start + chunk_size, file.size);
    const chunk = file.slice(start, end);

    const partResponse = await uploadPart(upload_id, i + 1, chunk);
    parts.push(partResponse);

    uploadedBytes += chunk.size;

    if (options.onProgress) {
      options.onProgress({
        loaded: uploadedBytes,
        total: file.size,
        percent: Math.round((uploadedBytes / file.size) * 100),
        currentChunk: i + 1,
        totalChunks: total_chunks,
      });
    }
  }

  // Complete upload
  const result = await completeUpload(upload_id, parts);
  return result.file;
}
