/**
 * Breadcrumb navigation component
 * WCAG AAA compliant
 */

import { useTranslation } from 'react-i18next';
import { ChevronRight, Home } from 'lucide-react';

import { cn } from '../../lib/utils';

interface BreadcrumbItem {
  name: string;
  path: string;
  id?: string;
}

interface BreadcrumbProps {
  breadcrumb: BreadcrumbItem[];
  onNavigate: (path: string, directoryId?: string) => void;
}

export function Breadcrumb({ breadcrumb, onNavigate }: BreadcrumbProps) {
  const { t: _t } = useTranslation(); // Reserved for future i18n usage

  return (
    <nav
      className="flex items-center gap-1 px-4 py-2 bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-700 overflow-x-auto"
      aria-label="Breadcrumb"
    >
      <ol className="flex items-center gap-1" role="list">
        {breadcrumb.map((item, index) => {
          const isLast = index === breadcrumb.length - 1;
          const isFirst = index === 0;

          return (
            <li key={item.path} className="flex items-center">
              {index > 0 && (
                <ChevronRight
                  className="w-4 h-4 mx-1 text-slate-400 dark:text-slate-500 flex-shrink-0"
                  aria-hidden="true"
                />
              )}

              {isLast ? (
                <span
                  className="flex items-center gap-1.5 px-2 py-1 text-sm font-medium text-slate-900 dark:text-slate-100"
                  aria-current="page"
                >
                  {isFirst && <Home className="w-4 h-4" aria-hidden="true" />}
                  {item.name}
                </span>
              ) : (
                <button
                  onClick={() => onNavigate(item.path, item.id)}
                  className={cn(
                    'flex items-center gap-1.5 px-2 py-1 text-sm rounded-md transition-colors',
                    'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100',
                    'hover:bg-slate-100 dark:hover:bg-slate-700',
                    'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1'
                  )}
                >
                  {isFirst && <Home className="w-4 h-4" aria-hidden="true" />}
                  {item.name}
                </button>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
