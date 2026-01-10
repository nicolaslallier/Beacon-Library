import { Info } from 'lucide-react';
import config from '../config';

export default function About() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="max-w-2xl mx-auto">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-indigo-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Info className="w-8 h-8 text-indigo-600" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">About</h1>
          <p className="text-gray-600">
            Learn more about Beacon Library
          </p>
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 divide-y divide-gray-200">
          <div className="p-4">
            <h2 className="font-medium text-gray-900 mb-2">
              {config.app.name}
            </h2>
            <p className="text-sm text-gray-600">
              {config.app.description}
            </p>
          </div>

          <div className="p-4">
            <h3 className="text-sm font-medium text-gray-500 mb-2">Version</h3>
            <p className="text-sm text-gray-900">{config.app.version}</p>
          </div>

          <div className="p-4">
            <h3 className="text-sm font-medium text-gray-500 mb-2">Description</h3>
            <p className="text-sm text-gray-600">
              Beacon Library is an electronic document management system designed
              to help you organize, store, and retrieve your documents efficiently.
              With powerful search capabilities and an intuitive interface, managing
              your document library has never been easier.
            </p>
          </div>

          <div className="p-4">
            <h3 className="text-sm font-medium text-gray-500 mb-2">Features</h3>
            <ul className="text-sm text-gray-600 space-y-1">
              <li>• Document catalog management</li>
              <li>• Full-text search capabilities</li>
              <li>• User-friendly interface</li>
              <li>• Environment-based configuration</li>
            </ul>
          </div>

          <div className="p-4">
            <h3 className="text-sm font-medium text-gray-500 mb-2">Environment</h3>
            <p className="text-sm text-gray-900">
              {config.env.mode} {config.env.isDevelopment && '(Development)'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
