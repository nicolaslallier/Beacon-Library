import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { BookOpen, Search, Clock } from 'lucide-react';
import { fetchHealth, normalizeError, type HealthResponse } from '../services/api';
import StatusWidget, { type StatusType } from '../components/StatusWidget';

export default function Home() {
  const {
    data,
    isLoading,
    error,
    refetch,
    isRefetching,
  } = useQuery<HealthResponse>({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 30000, // Check health every 30 seconds
    retry: 1,
  });

  // Determine status based on query state
  const getStatus = (): StatusType => {
    if (isLoading || isRefetching) return 'loading';
    if (error) return 'error';
    if (data?.status === 'ok' || data?.status === 'healthy') return 'connected';
    return 'degraded';
  };

  const status = getStatus();
  const normalizedError = error ? normalizeError(error) : null;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Welcome Section */}
      <section className="mb-12">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          Welcome to Beacon Library
        </h1>
        <p className="text-lg text-gray-600 max-w-2xl">
          Your electronic document management system. Organize, search, and manage
          your documents with ease.
        </p>
      </section>

      {/* Primary Actions */}
      <section className="mb-12">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Get Started</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-2xl">
          <Link
            to="/catalog"
            className="flex items-center gap-4 p-4 bg-white rounded-lg shadow-sm border border-gray-200 hover:border-indigo-300 hover:shadow-md transition-all group"
          >
            <div className="flex-shrink-0 w-12 h-12 bg-indigo-100 rounded-lg flex items-center justify-center group-hover:bg-indigo-200 transition-colors">
              <BookOpen className="w-6 h-6 text-indigo-600" />
            </div>
            <div>
              <h3 className="font-medium text-gray-900 group-hover:text-indigo-600 transition-colors">
                Browse Catalog
              </h3>
              <p className="text-sm text-gray-500">
                Explore available documents
              </p>
            </div>
          </Link>

          <Link
            to="/search"
            className="flex items-center gap-4 p-4 bg-white rounded-lg shadow-sm border border-gray-200 hover:border-indigo-300 hover:shadow-md transition-all group"
          >
            <div className="flex-shrink-0 w-12 h-12 bg-indigo-100 rounded-lg flex items-center justify-center group-hover:bg-indigo-200 transition-colors">
              <Search className="w-6 h-6 text-indigo-600" />
            </div>
            <div>
              <h3 className="font-medium text-gray-900 group-hover:text-indigo-600 transition-colors">
                Search
              </h3>
              <p className="text-sm text-gray-500">
                Find specific documents
              </p>
            </div>
          </Link>
        </div>
      </section>

      {/* Status and Activity Section */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl">
        {/* Backend Status Widget */}
        <div>
          <StatusWidget
            status={status}
            version={data?.version}
            onRetry={() => refetch()}
            errorMessage={normalizedError?.message}
          />
        </div>

        {/* Recent Activity Placeholder */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <h3 className="text-sm font-medium text-gray-500 mb-3">Recent Activity</h3>
          <div className="flex items-center gap-3 text-gray-400">
            <Clock className="w-5 h-5" />
            <p className="text-sm">No recent activity to display</p>
          </div>
          <p className="mt-2 text-xs text-gray-400">
            Your recent actions will appear here
          </p>
        </div>
      </section>
    </div>
  );
}
