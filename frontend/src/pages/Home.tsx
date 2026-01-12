import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { 
  Library, 
  Upload, 
  Search, 
  Clock, 
  Files, 
  HardDrive,
  ArrowRight,
  Sparkles,
  FolderOpen
} from 'lucide-react';
import { fetchHealth, normalizeError, type HealthResponse } from '../services/api';
import { listLibraries } from '../services/files';
import StatusWidget, { type StatusType } from '../components/StatusWidget';

// Stat card component
function StatCard({ 
  icon: Icon, 
  label, 
  value, 
  subtext,
  gradient 
}: { 
  icon: React.ElementType; 
  label: string; 
  value: string | number; 
  subtext?: string;
  gradient: string;
}) {
  return (
    <div className="relative overflow-hidden bg-white rounded-2xl shadow-lg shadow-slate-200/50 border border-slate-100 p-6 group hover:shadow-xl hover:shadow-indigo-500/10 transition-all duration-300">
      {/* Background gradient */}
      <div className={`absolute inset-0 opacity-5 group-hover:opacity-10 transition-opacity ${gradient}`} />
      
      <div className="relative flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-slate-500 mb-1">{label}</p>
          <p className="text-3xl font-bold text-slate-800">{value}</p>
          {subtext && (
            <p className="text-xs text-slate-400 mt-1">{subtext}</p>
          )}
        </div>
        <div className={`w-12 h-12 rounded-xl ${gradient} flex items-center justify-center shadow-lg`}>
          <Icon className="w-6 h-6 text-white" />
        </div>
      </div>
    </div>
  );
}

// Action card component
function ActionCard({ 
  to, 
  icon: Icon, 
  title, 
  description,
  gradient,
  isPrimary = false
}: { 
  to: string; 
  icon: React.ElementType; 
  title: string; 
  description: string;
  gradient: string;
  isPrimary?: boolean;
}) {
  return (
    <Link
      to={to}
      className={`relative overflow-hidden rounded-2xl p-6 group transition-all duration-300 hover:-translate-y-1 ${
        isPrimary 
          ? `${gradient} shadow-xl shadow-indigo-500/25 hover:shadow-2xl hover:shadow-indigo-500/30` 
          : 'bg-white border border-slate-100 shadow-lg shadow-slate-200/50 hover:shadow-xl hover:shadow-indigo-500/10 hover:border-indigo-200'
      }`}
    >
      {/* Decorative elements for primary card */}
      {isPrimary && (
        <>
          <div className="absolute top-0 right-0 w-32 h-32 bg-white/10 rounded-full -translate-y-1/2 translate-x-1/2" />
          <div className="absolute bottom-0 left-0 w-24 h-24 bg-white/10 rounded-full translate-y-1/2 -translate-x-1/2" />
        </>
      )}
      
      <div className="relative flex items-start gap-4">
        <div className={`w-14 h-14 rounded-xl flex items-center justify-center transition-transform duration-300 group-hover:scale-110 ${
          isPrimary 
            ? 'bg-white/20' 
            : `${gradient} shadow-lg`
        }`}>
          <Icon className={`w-7 h-7 ${isPrimary ? 'text-white' : 'text-white'}`} />
        </div>
        <div className="flex-1">
          <h3 className={`text-lg font-semibold mb-1 ${isPrimary ? 'text-white' : 'text-slate-800'}`}>
            {title}
          </h3>
          <p className={`text-sm ${isPrimary ? 'text-white/80' : 'text-slate-500'}`}>
            {description}
          </p>
        </div>
        <ArrowRight className={`w-5 h-5 transition-transform duration-300 group-hover:translate-x-1 ${
          isPrimary ? 'text-white/70' : 'text-slate-400'
        }`} />
      </div>
    </Link>
  );
}

// Format bytes helper
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export default function Home() {
  // Health check query
  const {
    data: healthData,
    isLoading: healthLoading,
    error: healthError,
    refetch: refetchHealth,
    isRefetching,
  } = useQuery<HealthResponse>({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 30000,
    retry: 1,
  });

  // Libraries query for stats
  const { data: librariesData } = useQuery({
    queryKey: ['libraries'],
    queryFn: () => listLibraries(),
  });

  // Calculate stats
  const totalLibraries = librariesData?.items?.length ?? 0;
  const totalFiles = librariesData?.items?.reduce((acc, lib) => acc + (lib.file_count || 0), 0) ?? 0;
  const totalStorage = librariesData?.items?.reduce((acc, lib) => acc + (lib.total_size_bytes || 0), 0) ?? 0;

  // Determine status
  const getStatus = (): StatusType => {
    if (healthLoading || isRefetching) return 'loading';
    if (healthError) return 'error';
    if (healthData?.status === 'ok' || healthData?.status === 'healthy') return 'connected';
    return 'degraded';
  };

  const status = getStatus();
  const normalizedError = healthError ? normalizeError(healthError) : null;

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative overflow-hidden">
        {/* Background with gradient */}
        <div 
          className="absolute inset-0" 
          style={{
            background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.05) 0%, rgba(168, 85, 247, 0.08) 50%, rgba(236, 72, 153, 0.05) 100%)'
          }}
        />
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiM2MzY2ZjEiIGZpbGwtb3BhY2l0eT0iMC4wMyI+PGNpcmNsZSBjeD0iMzAiIGN5PSIzMCIgcj0iMiIvPjwvZz48L2c+PC9zdmc+')] opacity-50" />
        
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
          <div className="text-center max-w-3xl mx-auto">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/80 backdrop-blur-sm border border-indigo-100 shadow-lg shadow-indigo-500/10 mb-8">
              <Sparkles className="w-4 h-4 text-indigo-500" />
              <span className="text-sm font-medium text-slate-600">Electronic Document Management</span>
            </div>
            
            {/* Title */}
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold mb-6">
              <span className="text-slate-800">Welcome to </span>
              <span className="bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-500 bg-clip-text text-transparent">
                Beacon Library
              </span>
            </h1>
            
            {/* Subtitle */}
            <p className="text-lg sm:text-xl text-slate-600 mb-10 max-w-2xl mx-auto">
              Organize, search, and manage your documents with ease. 
              A modern solution for all your document management needs.
            </p>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                to="/libraries"
                className="inline-flex items-center gap-2 px-8 py-4 text-lg font-semibold text-white bg-gradient-to-r from-indigo-600 to-purple-600 rounded-2xl shadow-xl shadow-indigo-500/30 hover:shadow-2xl hover:shadow-indigo-500/40 transition-all duration-300 hover:-translate-y-1"
              >
                <FolderOpen className="w-5 h-5" />
                Browse Libraries
              </Link>
              <Link
                to="/catalog"
                className="inline-flex items-center gap-2 px-8 py-4 text-lg font-semibold text-slate-700 bg-white rounded-2xl shadow-lg shadow-slate-200/50 border border-slate-200 hover:border-indigo-200 hover:shadow-xl transition-all duration-300 hover:-translate-y-1"
              >
                <Upload className="w-5 h-5" />
                Upload Files
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 -mt-8 relative z-10">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
          <StatCard
            icon={Library}
            label="Libraries"
            value={totalLibraries}
            subtext="Document collections"
            gradient="bg-gradient-to-br from-indigo-500 to-purple-600"
          />
          <StatCard
            icon={Files}
            label="Total Files"
            value={totalFiles}
            subtext="Across all libraries"
            gradient="bg-gradient-to-br from-purple-500 to-pink-500"
          />
          <StatCard
            icon={HardDrive}
            label="Storage Used"
            value={formatBytes(totalStorage)}
            subtext="Cloud storage"
            gradient="bg-gradient-to-br from-pink-500 to-rose-500"
          />
        </div>
      </section>

      {/* Quick Actions */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-slate-800">Quick Actions</h2>
            <p className="text-slate-500 text-sm">Get started with common tasks</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <ActionCard
            to="/libraries"
            icon={Library}
            title="Browse Libraries"
            description="Explore and manage your document collections"
            gradient="bg-gradient-to-r from-indigo-600 to-purple-600"
            isPrimary
          />
          <ActionCard
            to="/catalog"
            icon={Upload}
            title="Upload Documents"
            description="Add new files to your libraries"
            gradient="bg-gradient-to-br from-purple-500 to-pink-500"
          />
          <ActionCard
            to="/search"
            icon={Search}
            title="Search Documents"
            description="Find files across all your libraries"
            gradient="bg-gradient-to-br from-pink-500 to-rose-500"
          />
        </div>
      </section>

      {/* Status and Activity Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-16">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* System Status */}
          <StatusWidget
            status={status}
            version={healthData?.version}
            onRetry={() => refetchHealth()}
            errorMessage={normalizedError?.message}
          />

          {/* Recent Activity */}
          <div className="relative overflow-hidden bg-white rounded-2xl shadow-lg shadow-slate-200/50 border border-slate-100 p-5">
            <div className="absolute inset-0 bg-gradient-to-br from-slate-50 to-white opacity-50" />
            
            <div className="relative">
              <div className="flex items-center gap-2 mb-4">
                <Clock className="w-4 h-4 text-slate-400" />
                <h3 className="text-sm font-semibold text-slate-600">Recent Activity</h3>
              </div>
              
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-slate-100 to-slate-50 flex items-center justify-center mb-4">
                  <Clock className="w-8 h-8 text-slate-300" />
                </div>
                <p className="text-sm font-medium text-slate-500">No recent activity</p>
                <p className="text-xs text-slate-400 mt-1">
                  Your recent actions will appear here
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
