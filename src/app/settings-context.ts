import { createContext } from 'react';
import type { LanguageCode } from '@/types';

/** The shared language and state choices every page uses (architecture doc, section 4). */
export interface Settings {
  language: LanguageCode;
  setLanguage: (code: LanguageCode) => void;
  /** State code, or null when the user has not chosen one. */
  stateCode: string | null;
  setStateCode: (code: string | null) => void;
}

export const SettingsContext = createContext<Settings | null>(null);
