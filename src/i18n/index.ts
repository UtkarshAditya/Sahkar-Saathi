import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import type { LanguageOption } from '@/types';
import en from './locales/en.json';
import hi from './locales/hi.json';
import regional from './locales/regional.json';

/**
 * The third language is configurable. Set VITE_REGIONAL_LANGUAGE_CODE and
 * VITE_REGIONAL_LANGUAGE_LABEL in .env.local and put its strings in
 * locales/regional.json. Missing keys fall back to English.
 *
 * The starter regional.json is Marathi and must be reviewed by a native speaker.
 */
export const REGIONAL_LANGUAGE: LanguageOption = {
  code: import.meta.env.VITE_REGIONAL_LANGUAGE_CODE || 'mr',
  label: import.meta.env.VITE_REGIONAL_LANGUAGE_LABEL || 'मराठी',
  englishLabel: 'Regional',
};

export const LANGUAGES: LanguageOption[] = [
  { code: 'en', label: 'English', englishLabel: 'English' },
  { code: 'hi', label: 'हिन्दी', englishLabel: 'Hindi' },
  REGIONAL_LANGUAGE,
];

export const DEFAULT_LANGUAGE = 'en';

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    hi: { translation: hi },
    [REGIONAL_LANGUAGE.code]: { translation: regional },
  },
  lng: DEFAULT_LANGUAGE,
  fallbackLng: DEFAULT_LANGUAGE,
  supportedLngs: LANGUAGES.map((l) => l.code),
  interpolation: { escapeValue: false }, // React already escapes output
  returnNull: false,
});

export default i18n;
