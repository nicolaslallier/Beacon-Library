import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import en from './locales/en.json';
import fr from './locales/fr.json';

// Detect browser language
const getBrowserLanguage = (): string => {
  const lang = navigator.language || 'en';
  return lang.split('-')[0]; // Get just the language code (e.g., 'en' from 'en-US')
};

// Initialize i18next
i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      fr: { translation: fr },
    },
    lng: getBrowserLanguage(),
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false, // React already escapes values
    },
    // Enable debug in development
    debug: import.meta.env.DEV,
  });

export default i18n;
