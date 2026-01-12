/**
 * ShareDialog component for creating and managing share links.
 *
 * Features:
 * - Create share links with different permission levels
 * - Set expiry dates and access limits
 * - Password protection
 * - Copy share URL to clipboard
 * - View existing shares for a resource
 */

import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  sharesApi,
  getShareUrl,
  copyShareUrl,
  formatExpiryDate,
} from '../../services/shares';
import type {
  ShareLink,
  ShareLinkCreate,
  ShareType,
  ShareTargetType,
} from '../../services/shares';
import { cn } from '../../lib/utils';

interface ShareDialogProps {
  isOpen: boolean;
  onClose: () => void;
  targetType: ShareTargetType;
  targetId: string;
  targetName: string;
}

type ExpiryPreset = 'never' | '1h' | '24h' | '7d' | '30d' | 'custom';

export function ShareDialog({
  isOpen,
  onClose,
  targetType,
  targetId,
  targetName,
}: ShareDialogProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  // Form state
  const [shareType, setShareType] = useState<ShareType>('view');
  const [expiryPreset, setExpiryPreset] = useState<ExpiryPreset>('7d');
  const [customExpiry, setCustomExpiry] = useState('');
  const [maxAccesses, setMaxAccesses] = useState<string>('');
  const [passwordProtected, setPasswordProtected] = useState(false);
  const [password, setPassword] = useState('');
  const [allowGuest, setAllowGuest] = useState(true);
  const [notifyOnAccess, setNotifyOnAccess] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Tab state
  const [activeTab, setActiveTab] = useState<'create' | 'existing'>('create');

  // Reset form when dialog opens
  useEffect(() => {
    if (isOpen) {
      setShareType('view');
      setExpiryPreset('7d');
      setCustomExpiry('');
      setMaxAccesses('');
      setPasswordProtected(false);
      setPassword('');
      setAllowGuest(true);
      setNotifyOnAccess(false);
    }
  }, [isOpen]);

  // Fetch existing shares for this resource
  const { data: existingShares = [], isLoading: loadingShares } = useQuery({
    queryKey: ['shares', targetType, targetId],
    queryFn: () => sharesApi.listForResource(targetType, targetId),
    enabled: isOpen,
  });

  // Create share mutation
  const createShareMutation = useMutation({
    mutationFn: (data: ShareLinkCreate) => sharesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['shares', targetType, targetId],
      });
      setActiveTab('existing');
    },
  });

  // Revoke share mutation
  const revokeShareMutation = useMutation({
    mutationFn: (shareId: string) => sharesApi.revoke(shareId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['shares', targetType, targetId],
      });
    },
  });

  // Delete share mutation
  const deleteShareMutation = useMutation({
    mutationFn: (shareId: string) => sharesApi.delete(shareId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['shares', targetType, targetId],
      });
    },
  });

  // Calculate expiry date from preset
  const getExpiryDate = (): string | undefined => {
    if (expiryPreset === 'never') return undefined;
    if (expiryPreset === 'custom') return customExpiry || undefined;

    const now = new Date();
    switch (expiryPreset) {
      case '1h':
        now.setHours(now.getHours() + 1);
        break;
      case '24h':
        now.setHours(now.getHours() + 24);
        break;
      case '7d':
        now.setDate(now.getDate() + 7);
        break;
      case '30d':
        now.setDate(now.getDate() + 30);
        break;
    }
    return now.toISOString();
  };

  // Handle form submission
  const handleCreateShare = () => {
    const data: ShareLinkCreate = {
      target_type: targetType,
      target_id: targetId,
      share_type: shareType,
      expires_at: getExpiryDate(),
      max_access_count: maxAccesses ? parseInt(maxAccesses, 10) : undefined,
      password_protected: passwordProtected,
      password: passwordProtected ? password : undefined,
      allow_guest_access: allowGuest,
      notify_on_access: notifyOnAccess,
    };
    createShareMutation.mutate(data);
  };

  // Handle copy to clipboard
  const handleCopy = async (share: ShareLink) => {
    const success = await copyShareUrl(share.token);
    if (success) {
      setCopiedId(share.id);
      setTimeout(() => setCopiedId(null), 2000);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="share-dialog-title"
    >
      <div
        className="relative w-full max-w-lg rounded-xl bg-slate-900 shadow-2xl border border-slate-700"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-700 px-6 py-4">
          <h2
            id="share-dialog-title"
            className="text-lg font-semibold text-slate-100"
          >
            {t('share.title', { name: targetName })}
          </h2>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors"
            aria-label={t('common.close')}
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-700">
          <button
            className={cn(
              'flex-1 px-4 py-3 text-sm font-medium transition-colors',
              activeTab === 'create'
                ? 'border-b-2 border-emerald-500 text-emerald-400'
                : 'text-slate-400 hover:text-slate-200'
            )}
            onClick={() => setActiveTab('create')}
          >
            {t('share.createNew')}
          </button>
          <button
            className={cn(
              'flex-1 px-4 py-3 text-sm font-medium transition-colors',
              activeTab === 'existing'
                ? 'border-b-2 border-emerald-500 text-emerald-400'
                : 'text-slate-400 hover:text-slate-200'
            )}
            onClick={() => setActiveTab('existing')}
          >
            {t('share.existing')} ({existingShares.length})
          </button>
        </div>

        {/* Content */}
        <div className="p-6 max-h-[60vh] overflow-y-auto">
          {activeTab === 'create' ? (
            <div className="space-y-6">
              {/* Permission Level */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  {t('share.permission')}
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {(['view', 'download', 'edit'] as ShareType[]).map((type) => (
                    <button
                      key={type}
                      onClick={() => setShareType(type)}
                      className={cn(
                        'rounded-lg px-4 py-2 text-sm font-medium transition-colors',
                        shareType === type
                          ? 'bg-emerald-600 text-white'
                          : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                      )}
                    >
                      {t(`share.types.${type}`)}
                    </button>
                  ))}
                </div>
              </div>

              {/* Expiry */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  {t('share.expiry')}
                </label>
                <div className="grid grid-cols-3 gap-2 mb-2">
                  {(['1h', '24h', '7d', '30d', 'never', 'custom'] as ExpiryPreset[]).map(
                    (preset) => (
                      <button
                        key={preset}
                        onClick={() => setExpiryPreset(preset)}
                        className={cn(
                          'rounded-lg px-3 py-2 text-sm transition-colors',
                          expiryPreset === preset
                            ? 'bg-emerald-600 text-white'
                            : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                        )}
                      >
                        {t(`share.expiry.${preset}`)}
                      </button>
                    )
                  )}
                </div>
                {expiryPreset === 'custom' && (
                  <input
                    type="datetime-local"
                    value={customExpiry}
                    onChange={(e) => setCustomExpiry(e.target.value)}
                    className="w-full rounded-lg bg-slate-800 border border-slate-600 px-4 py-2 text-slate-200 focus:border-emerald-500 focus:outline-none"
                  />
                )}
              </div>

              {/* Max Accesses */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  {t('share.maxAccesses')}
                </label>
                <input
                  type="number"
                  min="1"
                  value={maxAccesses}
                  onChange={(e) => setMaxAccesses(e.target.value)}
                  placeholder={t('share.unlimited')}
                  className="w-full rounded-lg bg-slate-800 border border-slate-600 px-4 py-2 text-slate-200 placeholder-slate-500 focus:border-emerald-500 focus:outline-none"
                />
              </div>

              {/* Password Protection */}
              <div>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={passwordProtected}
                    onChange={(e) => setPasswordProtected(e.target.checked)}
                    className="h-5 w-5 rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-emerald-500"
                  />
                  <span className="text-sm text-slate-300">
                    {t('share.passwordProtect')}
                  </span>
                </label>
                {passwordProtected && (
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={t('share.enterPassword')}
                    className="mt-2 w-full rounded-lg bg-slate-800 border border-slate-600 px-4 py-2 text-slate-200 placeholder-slate-500 focus:border-emerald-500 focus:outline-none"
                  />
                )}
              </div>

              {/* Additional Options */}
              <div className="space-y-3">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={allowGuest}
                    onChange={(e) => setAllowGuest(e.target.checked)}
                    className="h-5 w-5 rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-emerald-500"
                  />
                  <span className="text-sm text-slate-300">
                    {t('share.allowGuest')}
                  </span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={notifyOnAccess}
                    onChange={(e) => setNotifyOnAccess(e.target.checked)}
                    className="h-5 w-5 rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-emerald-500"
                  />
                  <span className="text-sm text-slate-300">
                    {t('share.notifyAccess')}
                  </span>
                </label>
              </div>

              {/* Error Message */}
              {createShareMutation.isError && (
                <div className="rounded-lg bg-red-900/50 border border-red-700 px-4 py-3 text-sm text-red-200">
                  {t('share.createError')}
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {loadingShares ? (
                <div className="flex items-center justify-center py-8">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-emerald-500 border-t-transparent" />
                </div>
              ) : existingShares.length === 0 ? (
                <div className="text-center py-8 text-slate-400">
                  {t('share.noShares')}
                </div>
              ) : (
                existingShares.map((share) => (
                  <div
                    key={share.id}
                    className={cn(
                      'rounded-lg border p-4',
                      share.is_active && !share.is_expired
                        ? 'border-slate-700 bg-slate-800/50'
                        : 'border-red-900/50 bg-red-900/20'
                    )}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span
                            className={cn(
                              'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
                              share.share_type === 'view'
                                ? 'bg-blue-900/50 text-blue-300'
                                : share.share_type === 'download'
                                ? 'bg-green-900/50 text-green-300'
                                : 'bg-amber-900/50 text-amber-300'
                            )}
                          >
                            {t(`share.types.${share.share_type}`)}
                          </span>
                          {share.password_protected && (
                            <span className="text-xs text-slate-500">🔒</span>
                          )}
                          {!share.is_active && (
                            <span className="inline-flex items-center rounded-full bg-red-900/50 px-2 py-0.5 text-xs font-medium text-red-300">
                              {t('share.revoked')}
                            </span>
                          )}
                          {share.is_expired && share.is_active && (
                            <span className="inline-flex items-center rounded-full bg-amber-900/50 px-2 py-0.5 text-xs font-medium text-amber-300">
                              {t('share.expired')}
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-slate-500 space-y-0.5">
                          <div>
                            {t('share.expires')}: {formatExpiryDate(share.expires_at)}
                          </div>
                          <div>
                            {t('share.accesses')}: {share.access_count}
                            {share.max_access_count && ` / ${share.max_access_count}`}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleCopy(share)}
                          className="rounded-lg p-2 text-slate-400 hover:bg-slate-700 hover:text-slate-200 transition-colors"
                          title={t('share.copyLink')}
                        >
                          {copiedId === share.id ? (
                            <svg className="h-4 w-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                          ) : (
                            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                            </svg>
                          )}
                        </button>
                        {share.is_active && (
                          <button
                            onClick={() => revokeShareMutation.mutate(share.id)}
                            className="rounded-lg p-2 text-slate-400 hover:bg-red-900/50 hover:text-red-300 transition-colors"
                            title={t('share.revoke')}
                          >
                            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                            </svg>
                          </button>
                        )}
                        <button
                          onClick={() => deleteShareMutation.mutate(share.id)}
                          className="rounded-lg p-2 text-slate-400 hover:bg-red-900/50 hover:text-red-300 transition-colors"
                          title={t('share.delete')}
                        >
                          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    </div>
                    <div className="mt-2">
                      <input
                        type="text"
                        readOnly
                        value={getShareUrl(share.token)}
                        className="w-full rounded bg-slate-900 border border-slate-700 px-3 py-1.5 text-xs text-slate-400 font-mono"
                        onClick={(e) => (e.target as HTMLInputElement).select()}
                      />
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 border-t border-slate-700 px-6 py-4">
          <button
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm font-medium text-slate-300 hover:bg-slate-800 transition-colors"
          >
            {t('common.cancel')}
          </button>
          {activeTab === 'create' && (
            <button
              onClick={handleCreateShare}
              disabled={
                createShareMutation.isPending ||
                (passwordProtected && password.length < 4)
              }
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {createShareMutation.isPending
                ? t('common.creating')
                : t('share.createLink')}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default ShareDialog;
