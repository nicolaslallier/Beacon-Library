import { Link, Outlet } from 'react-router-dom';
import { Library, Github, Heart } from 'lucide-react';
import Navbar from './Navbar';

export default function Layout() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50/30 flex flex-col">
      {/* Header with navigation */}
      <header>
        <Navbar />
      </header>

      {/* Main content area */}
      <main className="flex-1">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="relative mt-auto">
        {/* Gradient top border */}
        <div className="h-px bg-gradient-to-r from-transparent via-indigo-300 to-transparent" />
        
        <div className="bg-white/80 backdrop-blur-sm py-8">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex flex-col md:flex-row items-center justify-between gap-6">
              {/* Brand */}
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 shadow-lg shadow-indigo-500/20">
                  <Library className="w-5 h-5 text-white" />
                </div>
                <div>
                  <p className="font-semibold text-slate-800">Beacon Library</p>
                  <p className="text-xs text-slate-500">Electronic Document Management</p>
                </div>
              </div>

              {/* Quick Links */}
              <div className="flex items-center gap-6 text-sm">
                <Link to="/libraries" className="text-slate-600 hover:text-indigo-600 transition-colors">
                  Libraries
                </Link>
                <Link to="/catalog" className="text-slate-600 hover:text-indigo-600 transition-colors">
                  Upload
                </Link>
                <Link to="/search" className="text-slate-600 hover:text-indigo-600 transition-colors">
                  Search
                </Link>
                <Link to="/about" className="text-slate-600 hover:text-indigo-600 transition-colors">
                  About
                </Link>
              </div>

              {/* Copyright */}
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <span>Made with</span>
                <Heart className="w-4 h-4 text-pink-500 fill-pink-500" />
                <span>using</span>
                <a 
                  href="https://github.com" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-slate-600 hover:text-indigo-600 transition-colors"
                >
                  <Github className="w-4 h-4" />
                </a>
              </div>
            </div>

            {/* Bottom line */}
            <div className="mt-6 pt-6 border-t border-slate-100 text-center text-xs text-slate-400">
              <p>&copy; {new Date().getFullYear()} Beacon Library. All rights reserved.</p>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
