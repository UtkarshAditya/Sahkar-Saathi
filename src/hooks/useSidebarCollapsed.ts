import { useCallback, useState } from 'react';

const STORAGE_KEY = 'sahkar-saathi:sidebar-collapsed';

function readCollapsed(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === 'true';
  } catch {
    return false;
  }
}

/** Desktop sidebar collapsed to icons. Remembered on the device when storage is available. */
export function useSidebarCollapsed(): [boolean, () => void] {
  const [collapsed, setCollapsed] = useState(readCollapsed);

  const toggle = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        window.localStorage.setItem(STORAGE_KEY, String(next));
      } catch {
        // Storage can be unavailable (private mode). The choice still holds for the session.
      }
      return next;
    });
  }, []);

  return [collapsed, toggle];
}
