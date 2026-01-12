import { CheckCircle, AlertTriangle, RefreshCw, Wifi, WifiOff, Activity } from 'lucide-react';

export type StatusType = 'connected' | 'degraded' | 'loading' | 'error';

interface StatusWidgetProps {
  status: StatusType;
  version?: string;
  onRetry?: () => void;
  errorMessage?: string;
}

export default function StatusWidget({
  status,
  version,
  onRetry,
  errorMessage,
}: StatusWidgetProps) {
  return (
    <div className="relative overflow-hidden bg-white rounded-2xl shadow-lg shadow-slate-200/50 border border-slate-100 p-5">
      {/* Decorative gradient background */}
      <div className="absolute inset-0 bg-gradient-to-br from-slate-50 to-white opacity-50" />
      
      <div className="relative">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="w-4 h-4 text-slate-400" />
          <h3 className="text-sm font-semibold text-slate-600">System Status</h3>
        </div>

        {status === 'loading' && (
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-100 to-indigo-100 animate-pulse" />
              <div className="absolute inset-0 flex items-center justify-center">
                <RefreshCw className="w-5 h-5 text-blue-500 animate-spin" />
              </div>
            </div>
            <div className="flex-1 space-y-2">
              <div className="h-4 w-24 bg-slate-200 rounded-lg animate-pulse" />
              <div className="h-3 w-32 bg-slate-100 rounded-lg animate-pulse" />
            </div>
          </div>
        )}

        {status === 'connected' && (
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-400 to-green-500 flex items-center justify-center shadow-lg shadow-emerald-500/30">
                <Wifi className="w-5 h-5 text-white" />
              </div>
              {/* Pulse indicator */}
              <span className="absolute -top-1 -right-1 flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500" />
              </span>
            </div>
            <div>
              <p className="text-sm font-semibold text-emerald-700">All Systems Online</p>
              {version && (
                <p className="text-xs text-slate-500 mt-0.5">API v{version}</p>
              )}
            </div>
          </div>
        )}

        {status === 'degraded' && (
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-lg shadow-amber-500/30">
              <AlertTriangle className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="text-sm font-semibold text-amber-700">Degraded Performance</p>
              <p className="text-xs text-slate-500 mt-0.5">Some services may be slow</p>
            </div>
          </div>
        )}

        {status === 'error' && (
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-red-400 to-rose-500 flex items-center justify-center shadow-lg shadow-red-500/30">
                <WifiOff className="w-5 h-5 text-white" />
              </div>
              <div>
                <p className="text-sm font-semibold text-red-700">Connection Error</p>
                <p className="text-xs text-slate-500 mt-0.5">
                  {errorMessage || 'Unable to reach the server'}
                </p>
              </div>
            </div>
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-indigo-500 to-purple-600 rounded-xl hover:from-indigo-600 hover:to-purple-700 shadow-md shadow-indigo-500/25 transition-all duration-200 hover:shadow-lg hover:shadow-indigo-500/30"
              >
                <RefreshCw className="w-4 h-4" aria-hidden="true" />
                Retry Connection
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Skeleton loader variant of StatusWidget for initial loading states
 */
export function StatusWidgetSkeleton() {
  return (
    <div className="relative overflow-hidden bg-white rounded-2xl shadow-lg shadow-slate-200/50 border border-slate-100 p-5">
      <div className="absolute inset-0 bg-gradient-to-br from-slate-50 to-white opacity-50" />
      <div className="relative animate-pulse">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-4 h-4 bg-slate-200 rounded" />
          <div className="h-4 w-24 bg-slate-200 rounded-lg" />
        </div>
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-slate-200" />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-28 bg-slate-200 rounded-lg" />
            <div className="h-3 w-20 bg-slate-100 rounded-lg" />
          </div>
        </div>
      </div>
    </div>
  );
}
