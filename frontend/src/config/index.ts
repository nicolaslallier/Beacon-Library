/**
 * Centralized configuration management
 * All configuration values are derived from environment variables with sensible defaults
 */

export const config = {
  // API Configuration
  api: {
    baseUrl: import.meta.env.VITE_API_BASE_URL || '/api',
    timeout: Number(import.meta.env.VITE_API_TIMEOUT) || 10000,
  },

  // Application metadata
  app: {
    name: 'Beacon Library',
    description: 'Electronic Document Management System',
    version: import.meta.env.VITE_APP_VERSION || '0.1.0',
  },

  // Environment detection
  env: {
    isDevelopment: import.meta.env.DEV,
    isProduction: import.meta.env.PROD,
    mode: import.meta.env.MODE,
  },

  // Feature flags (for future use)
  features: {
    enableAuth: import.meta.env.VITE_ENABLE_AUTH === 'true',
  },
} as const;

export default config;
