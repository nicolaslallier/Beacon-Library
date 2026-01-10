/**
 * Share links API service
 */

import { apiClient } from './api';

export type ShareType = 'view' | 'download' | 'edit';
export type ShareTargetType = 'file' | 'directory' | 'library';

export interface ShareLink {
  id: string;
  token: string;
  share_type: ShareType;
  target_type: ShareTargetType;
  target_id: string;
  created_by: string;
  password_protected: boolean;
  expires_at: string | null;
  max_access_count: number | null;
  allow_guest_access: boolean;
  notify_on_access: boolean;
  access_count: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  share_url: string | null;
  is_expired: boolean;
  remaining_accesses: number | null;
}

export interface ShareLinkCreate {
  target_type: ShareTargetType;
  target_id: string;
  share_type?: ShareType;
  password_protected?: boolean;
  password?: string;
  expires_at?: string;
  max_access_count?: number;
  allow_guest_access?: boolean;
  notify_on_access?: boolean;
}

export interface ShareLinkUpdate {
  share_type?: ShareType;
  password_protected?: boolean;
  password?: string;
  expires_at?: string;
  max_access_count?: number;
  allow_guest_access?: boolean;
  notify_on_access?: boolean;
  is_active?: boolean;
}

export interface SharePublicInfo {
  id: string;
  share_type: ShareType;
  target_type: ShareTargetType;
  target_name: string;
  password_protected: boolean;
  allow_guest_access: boolean;
  is_expired: boolean;
}

export interface ShareAccessRequest {
  password?: string;
}

export interface ShareAccessResponse {
  access_token: string;
  share_type: ShareType;
  target_type: ShareTargetType;
  target_id: string;
  target_name: string;
  expires_at: string;
}

export interface ShareStatistics {
  share_id: string;
  total_accesses: number;
  unique_visitors: number;
  last_accessed_at: string | null;
  access_by_date: Record<string, number>;
}

export interface GuestAccountCreate {
  email: string;
  share_link_id: string;
}

export interface GuestAccountResponse {
  guest_id: string;
  email: string;
  temporary_password: string | null;
  login_url: string;
}

/**
 * Share links API
 */
export const sharesApi = {
  /**
   * Create a new share link
   */
  async create(data: ShareLinkCreate): Promise<ShareLink> {
    const response = await apiClient.post<ShareLink>('/api/shares', data);
    return response.data;
  },

  /**
   * List all share links for the current user
   */
  async list(includeExpired = false): Promise<ShareLink[]> {
    const response = await apiClient.get<ShareLink[]>('/api/shares', {
      params: { include_expired: includeExpired },
    });
    return response.data;
  },

  /**
   * List share links for a specific resource
   */
  async listForResource(
    targetType: ShareTargetType,
    targetId: string
  ): Promise<ShareLink[]> {
    const response = await apiClient.get<ShareLink[]>(
      `/api/shares/resource/${targetType}/${targetId}`
    );
    return response.data;
  },

  /**
   * Get a specific share link
   */
  async get(shareId: string): Promise<ShareLink> {
    const response = await apiClient.get<ShareLink>(`/api/shares/${shareId}`);
    return response.data;
  },

  /**
   * Update a share link
   */
  async update(shareId: string, data: ShareLinkUpdate): Promise<ShareLink> {
    const response = await apiClient.patch<ShareLink>(
      `/api/shares/${shareId}`,
      data
    );
    return response.data;
  },

  /**
   * Revoke a share link (deactivate without deleting)
   */
  async revoke(shareId: string): Promise<void> {
    await apiClient.post(`/api/shares/${shareId}/revoke`);
  },

  /**
   * Delete a share link
   */
  async delete(shareId: string): Promise<void> {
    await apiClient.delete(`/api/shares/${shareId}`);
  },

  /**
   * Get share statistics
   */
  async getStatistics(shareId: string): Promise<ShareStatistics> {
    const response = await apiClient.get<ShareStatistics>(
      `/api/shares/${shareId}/statistics`
    );
    return response.data;
  },

  /**
   * Create a guest account for share access
   */
  async createGuestAccount(
    data: GuestAccountCreate
  ): Promise<GuestAccountResponse> {
    const response = await apiClient.post<GuestAccountResponse>(
      '/api/shares/guest',
      data
    );
    return response.data;
  },

  /**
   * Get public info about a share link (no auth required)
   */
  async getPublicInfo(token: string): Promise<SharePublicInfo> {
    const response = await apiClient.get<SharePublicInfo>(
      `/api/shares/public/${token}`
    );
    return response.data;
  },

  /**
   * Access a shared resource (no auth required)
   */
  async accessShare(
    token: string,
    data: ShareAccessRequest
  ): Promise<ShareAccessResponse> {
    const response = await apiClient.post<ShareAccessResponse>(
      `/api/shares/public/${token}/access`,
      data
    );
    return response.data;
  },
};

/**
 * Helper to generate share URL from token
 */
export function getShareUrl(token: string): string {
  return `${window.location.origin}/share/${token}`;
}

/**
 * Helper to copy share URL to clipboard
 */
export async function copyShareUrl(token: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(getShareUrl(token));
    return true;
  } catch {
    return false;
  }
}

/**
 * Format expiry date for display
 */
export function formatExpiryDate(expiresAt: string | null): string {
  if (!expiresAt) return 'Never';

  const date = new Date(expiresAt);
  const now = new Date();
  const diff = date.getTime() - now.getTime();

  if (diff < 0) return 'Expired';

  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));

  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h`;

  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
  return `${minutes}m`;
}
