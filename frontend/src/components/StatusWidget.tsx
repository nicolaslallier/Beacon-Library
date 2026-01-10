import { CheckCircle, AlertTriangle, RefreshCw } from 'lucide-react';

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
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <h3 className="text-sm font-medium text-gray-500 mb-3">Backend Status</h3>

      {status === 'loading' && (
        <div className="flex items-center gap-3">
          <div className="animate-pulse bg-gray-200 rounded-full w-10 h-10" />
          <div className="flex-1">
            <div className="animate-pulse bg-gray-200 rounded h-4 w-24 mb-2" />
            <div className="animate-pulse bg-gray-200 rounded h-3 w-32" />
          </div>
        </div>
      )}

      {status === 'connected' && (
        <div className="flex items-center gap-3">
          <div className="flex-shrink-0 w-10 h-10 bg-green-100 rounded-full flex items-center justify-center">
            <CheckCircle className="w-6 h-6 text-green-600" aria-hidden="true" />
          </div>
          <div>
            <p className="text-sm font-medium text-green-800">Connected</p>
            {version && (
              <p className="text-xs text-gray-500">API Version: {version}</p>
            )}
          </div>
        </div>
      )}

      {status === 'degraded' && (
        <div className="flex items-center gap-3">
          <div className="flex-shrink-0 w-10 h-10 bg-amber-100 rounded-full flex items-center justify-center">
            <AlertTriangle className="w-6 h-6 text-amber-600" aria-hidden="true" />
          </div>
          <div>
            <p className="text-sm font-medium text-amber-800">Degraded</p>
            <p className="text-xs text-gray-500">Some services may be unavailable</p>
          </div>
        </div>
      )}

      {status === 'error' && (
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="flex-shrink-0 w-10 h-10 bg-red-100 rounded-full flex items-center justify-center">
              <AlertTriangle className="w-6 h-6 text-red-600" aria-hidden="true" />
            </div>
            <div>
              <p className="text-sm font-medium text-red-800">Offline</p>
              <p className="text-xs text-gray-500">
                {errorMessage || 'Unable to connect to the server'}
              </p>
            </div>
          </div>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-indigo-600 bg-indigo-50 rounded-md hover:bg-indigo-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 transition-colors"
            >
              <RefreshCw className="w-4 h-4" aria-hidden="true" />
              Retry
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Skeleton loader variant of StatusWidget for initial loading states
 */
export function StatusWidgetSkeleton() {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <div className="animate-pulse">
        <div className="bg-gray-200 rounded h-4 w-24 mb-3" />
        <div className="flex items-center gap-3">
          <div className="bg-gray-200 rounded-full w-10 h-10" />
          <div className="flex-1">
            <div className="bg-gray-200 rounded h-4 w-20 mb-2" />
            <div className="bg-gray-200 rounded h-3 w-28" />
          </div>
        </div>
      </div>
    </div>
  );
}
