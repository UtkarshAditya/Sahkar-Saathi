import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { I18nextProvider } from 'react-i18next';
import i18n, { DEFAULT_LANGUAGE, LANGUAGES } from '@/i18n';
import type { LanguageCode } from '@/types';
import { SettingsContext, type Settings } from './settings-context';

const STORAGE_KEY = 'sahkar-saathi:settings';

interface StoredSettings {
  language?: LanguageCode;
  stateCode?: string | null;
}

// Only preferences are stored on the device: no names, numbers or chat text.
function readStored(): StoredSettings {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredSettings) : {};
  } catch {
    return {};
  }
}

function writeStored(value: StoredSettings) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  } catch {
    // Storage can be unavailable (private mode). Settings still work for the session.
  }
}

function SettingsProvider({ children }: { children: ReactNode }) {
  const [stored] = useState(readStored);
  const [language, setLanguageState] = useState<LanguageCode>(() =>
    LANGUAGES.some((l) => l.code === stored.language) ? stored.language! : DEFAULT_LANGUAGE,
  );
  const [stateCode, setStateCode] = useState<string | null>(stored.stateCode ?? null);

  useEffect(() => {
    void i18n.changeLanguage(language);
    document.documentElement.lang = language;
  }, [language]);

  useEffect(() => {
    writeStored({ language, stateCode });
  }, [language, stateCode]);

  const setLanguage = useCallback((code: LanguageCode) => setLanguageState(code), []);

  const value = useMemo<Settings>(
    () => ({ language, setLanguage, stateCode, setStateCode }),
    [language, setLanguage, stateCode],
  );

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <I18nextProvider i18n={i18n}>
      <SettingsProvider>{children}</SettingsProvider>
    </I18nextProvider>
  );
}
