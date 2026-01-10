/**
 * Notifications API service
 */

import { apiClient } from './api';

export type NotificationType =
  | 'share_received'
  | 'share_accessed'
  | 'share_expired'
  | 'file_uploaded'
  | 'file_deleted'
  | 'file_moved'
  | 'comment_added'
  | 'system';

export type NotificationPriority = 'low' | 'normal' | 'high' | 'urgent';

export interface Notification {
  id: string;
  user_id: string;
  notification_type: NotificationType;
  title: string;
  message: string;
  priority: NotificationPriority;
  action_url: string | null;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
  metadata: Record<string, unknown> | null;
}

export interface NotificationListResponse {
  notifications: Notification[];
  total: number;
  unread_count: number;
}

/**
 * Notifications API
 */
export const notificationsApi = {
  /**
   * List notifications for the current user
   */
  async list(
    unreadOnly = false,
    limit = 50,
    offset = 0
  ): Promise<NotificationListResponse> {
    const response = await apiClient.get<NotificationListResponse>(
      '/api/notifications',
      {
        params: {
          unread_only: unreadOnly,
          limit,
          offset,
        },
      }
    );
    return response.data;
  },

  /**
   * Mark a notification as read
   */
  async markAsRead(notificationId: string): Promise<void> {
    await apiClient.post(`/api/notifications/${notificationId}/read`);
  },

  /**
   * Mark all notifications as read
   */
  async markAllAsRead(): Promise<{ marked_read: number }> {
    const response = await apiClient.post<{ marked_read: number }>(
      '/api/notifications/read-all'
    );
    return response.data;
  },

  /**
   * Delete a notification
   */
  async delete(notificationId: string): Promise<void> {
    await apiClient.delete(`/api/notifications/${notificationId}`);
  },
};

/**
 * Get icon for notification type
 */
export function getNotificationIcon(type: NotificationType): string {
  switch (type) {
    case 'share_received':
      return '📤';
    case 'share_accessed':
      return '👁️';
    case 'share_expired':
      return '⏰';
    case 'file_uploaded':
      return '📁';
    case 'file_deleted':
      return '🗑️';
    case 'file_moved':
      return '📦';
    case 'comment_added':
      return '💬';
    case 'system':
    default:
      return '🔔';
  }
}

/**
 * Format notification time for display
 */
export function formatNotificationTime(createdAt: string): string {
  const date = new Date(createdAt);
  const now = new Date();
  const diff = now.getTime() - date.getTime();

  const minutes = Math.floor(diff / (1000 * 60));
  const hours = Math.floor(diff / (1000 * 60 * 60));
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));

  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;

  return date.toLocaleDateString();
}
