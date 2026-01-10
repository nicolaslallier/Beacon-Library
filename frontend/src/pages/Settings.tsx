import { Settings as SettingsIcon, Clock } from 'lucide-react';

export default function Settings() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="text-center max-w-md mx-auto">
        <div className="w-16 h-16 bg-indigo-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <SettingsIcon className="w-8 h-8 text-indigo-600" />
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Settings</h1>
        <p className="text-gray-600 mb-6">
          Configure your preferences and application settings.
        </p>
        <div className="inline-flex items-center gap-2 px-4 py-2 bg-amber-50 text-amber-700 rounded-full text-sm">
          <Clock className="w-4 h-4" />
          <span>Coming soon</span>
        </div>
      </div>
    </div>
  );
}
