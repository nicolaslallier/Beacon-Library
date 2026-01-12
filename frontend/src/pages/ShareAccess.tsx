/**
 * ShareAccess page for accessing shared resources via public link.
 *
 * Features:
 * - Password verification for protected shares
 * - Guest access or login prompt
 * - File preview/download based on share type
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useQuery, useMutation } from '@tanstack/react-query';
import { sharesApi } from '../services/shares';
import type { ShareAccessResponse } from '../services/shares';
import { cn } from '../lib/utils';

export function ShareAccess() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [password, setPassword] = useState('');
  const [accessData, setAccessData] = useState<ShareAccessResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch public share info
  const {
    data: shareInfo,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['share-public', token],
    queryFn: () => sharesApi.getPublicInfo(token!),
    enabled: !!token,
    retry: false,
  });

  // Access share mutation
  const accessMutation = useMutation({
    mutationFn: () => sharesApi.accessShare(token!, { password: password || undefined }),
    onSuccess: (data) => {
      setAccessData(data);
      setError(null);
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || t('share.accessError'));
    },
  });

  // Auto-access if no password required
  useEffect(() => {
    if (shareInfo && !shareInfo.password_protected && !shareInfo.is_expired) {
      accessMutation.mutate();
    }
  }, [shareInfo]);

  // Handle password submission
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    accessMutation.mutate();
  };

  // Render loading state
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <div className="text-center">
          <div className="h-12 w-12 animate-spin rounded-full border-4 border-emerald-500 border-t-transparent mx-auto mb-4" />
          <p className="text-slate-400">{t('common.loading')}</p>
        </div>
      </div>
    );
  }

  // Render error state
  if (isError || !shareInfo) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <div className="max-w-md w-full mx-4">
          <div className="rounded-xl bg-slate-800/50 border border-red-900/50 p-8 text-center">
            <div className="mx-auto h-16 w-16 rounded-full bg-red-900/30 flex items-center justify-center mb-4">
              <svg className="h-8 w-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <h1 className="text-xl font-semibold text-slate-100 mb-2">
              {t('share.notFound')}
            </h1>
            <p className="text-slate-400 mb-6">
              {t('share.notFoundDesc')}
            </p>
            <button
              onClick={() => navigate('/')}
              className="rounded-lg bg-slate-700 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-600 transition-colors"
            >
              {t('common.goHome')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Render expired state
  if (shareInfo.is_expired) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <div className="max-w-md w-full mx-4">
          <div className="rounded-xl bg-slate-800/50 border border-amber-900/50 p-8 text-center">
            <div className="mx-auto h-16 w-16 rounded-full bg-amber-900/30 flex items-center justify-center mb-4">
              <svg className="h-8 w-8 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h1 className="text-xl font-semibold text-slate-100 mb-2">
              {t('share.linkExpired')}
            </h1>
            <p className="text-slate-400 mb-6">
              {t('share.linkExpiredDesc')}
            </p>
            <button
              onClick={() => navigate('/')}
              className="rounded-lg bg-slate-700 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-600 transition-colors"
            >
              {t('common.goHome')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Render access granted state
  if (accessData) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <div className="max-w-md w-full mx-4">
          <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-8">
            <div className="text-center mb-6">
              <div className="mx-auto h-16 w-16 rounded-full bg-emerald-900/30 flex items-center justify-center mb-4">
                <svg className="h-8 w-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h1 className="text-xl font-semibold text-slate-100 mb-2">
                {t('share.accessGranted')}
              </h1>
              <p className="text-slate-400">
                {accessData.target_name}
              </p>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between rounded-lg bg-slate-900/50 px-4 py-3">
                <span className="text-sm text-slate-400">{t('share.type')}</span>
                <span
                  className={cn(
                    'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
                    accessData.share_type === 'view'
                      ? 'bg-blue-900/50 text-blue-300'
                      : accessData.share_type === 'download'
                      ? 'bg-green-900/50 text-green-300'
                      : 'bg-amber-900/50 text-amber-300'
                  )}
                >
                  {t(`share.types.${accessData.share_type}`)}
                </span>
              </div>
              <div className="flex items-center justify-between rounded-lg bg-slate-900/50 px-4 py-3">
                <span className="text-sm text-slate-400">{t('share.validUntil')}</span>
                <span className="text-sm text-slate-200">
                  {new Date(accessData.expires_at).toLocaleString()}
                </span>
              </div>
            </div>

            <div className="mt-6 flex gap-3">
              {accessData.share_type !== 'view' && (
                <button
                  onClick={() => {
                    // TODO: Implement download with access token
                    window.location.href = `/api/files/${accessData.target_id}/download?access_token=${accessData.access_token}`;
                  }}
                  className="flex-1 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-emerald-500 transition-colors"
                >
                  {t('share.download')}
                </button>
              )}
              <button
                onClick={() => {
                  // TODO: Navigate to preview/explorer view
                  navigate(`/preview/${accessData.target_type}/${accessData.target_id}?token=${accessData.access_token}`);
                }}
                className={cn(
                  'rounded-lg px-4 py-2.5 text-sm font-medium transition-colors',
                  accessData.share_type === 'view'
                    ? 'flex-1 bg-emerald-600 text-white hover:bg-emerald-500'
                    : 'bg-slate-700 text-slate-200 hover:bg-slate-600'
                )}
              >
                {t('share.preview')}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Render password form
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <div className="max-w-md w-full mx-4">
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-8">
          <div className="text-center mb-6">
            <div className="mx-auto h-16 w-16 rounded-full bg-slate-700 flex items-center justify-center mb-4">
              {shareInfo.target_type === 'file' ? (
                <svg className="h-8 w-8 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                </svg>
              ) : shareInfo.target_type === 'directory' ? (
                <svg className="h-8 w-8 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                </svg>
              ) : (
                <svg className="h-8 w-8 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
              )}
            </div>
            <h1 className="text-xl font-semibold text-slate-100 mb-2">
              {shareInfo.target_name}
            </h1>
            <p className="text-slate-400 text-sm">
              {shareInfo.password_protected
                ? t('share.passwordRequired')
                : t('share.accessingShare')}
            </p>
          </div>

          {shareInfo.password_protected && (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label
                  htmlFor="password"
                  className="block text-sm font-medium text-slate-300 mb-2"
                >
                  {t('share.password')}
                </label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={t('share.enterPassword')}
                  className="w-full rounded-lg bg-slate-900 border border-slate-600 px-4 py-2.5 text-slate-200 placeholder-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  autoFocus
                />
              </div>

              {error && (
                <div className="rounded-lg bg-red-900/30 border border-red-900/50 px-4 py-3 text-sm text-red-300">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={accessMutation.isPending || !password}
                className="w-full rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {accessMutation.isPending ? t('common.loading') : t('share.accessFile')}
              </button>
            </form>
          )}

          {!shareInfo.password_protected && accessMutation.isPending && (
            <div className="flex items-center justify-center py-4">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-emerald-500 border-t-transparent" />
            </div>
          )}

          {!shareInfo.allow_guest_access && (
            <div className="mt-4 pt-4 border-t border-slate-700">
              <p className="text-sm text-slate-400 text-center mb-3">
                {t('share.loginRequired')}
              </p>
              <button
                onClick={() => navigate('/login')}
                className="w-full rounded-lg bg-slate-700 px-4 py-2.5 text-sm font-medium text-slate-200 hover:bg-slate-600 transition-colors"
              >
                {t('common.login')}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default ShareAccess;
