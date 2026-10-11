import { useContext } from 'react';
import { SettingsContext, type Settings } from '@/app/settings-context';

export function useSettings(): Settings {
  const settings = useContext(SettingsContext);
  if (!settings) throw new Error('useSettings must be used inside <AppProviders>.');
  return settings;
}
