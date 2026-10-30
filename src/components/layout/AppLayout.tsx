import { useEffect, useState } from 'react';
import { Outlet, ScrollRestoration, useLocation } from 'react-router';
import { useTranslation } from 'react-i18next';
import { useSidebarCollapsed } from '@/hooks/useSidebarCollapsed';
import { cn } from '@/lib/format';
import { Header } from './Header';
import { MobileNavigation } from './MobileNavigation';
import { Sidebar } from './Sidebar';

export default function AppLayout() {
  const { t } = useTranslation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [collapsed, toggleCollapsed] = useSidebarCollapsed();
  const { pathname } = useLocation();
  // The Ask page is a full-height chat with its own pinned input and no footer.
  const isChat = pathname === '/';

  // Close the drawer whenever the route changes.
  useEffect(() => setMenuOpen(false), [pathname]);

  return (
    <div className="min-h-dvh">
      <a
        href="#main"
        className="sr-only z-50 rounded-lg bg-brand-800 px-4 py-2 font-semibold text-white focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        {t('nav.skipToContent')}
      </a>

      <Sidebar collapsed={collapsed} onToggle={toggleCollapsed} />

      <div
        className={cn(
          'flex min-h-dvh flex-col print:pl-0',
          collapsed ? 'lg:pl-[4.5rem]' : 'lg:pl-64',
        )}
      >
        <Header />
        <main
          id="main"
          tabIndex={-1}
          className={cn(
            'flex flex-1 flex-col px-4 outline-none sm:px-6 lg:px-8 print:p-0',
            isChat
              ? 'pb-[calc(4rem+env(safe-area-inset-bottom))] lg:pb-0'
              : 'pt-6 pb-28 sm:pt-8 lg:pb-12',
          )}
        >
          <div className={cn('mx-auto flex w-full flex-1 flex-col', !isChat && 'max-w-6xl')}>
            <Outlet />
          </div>
        </main>
        {!isChat && (
          <footer className="hidden border-t border-line px-8 py-4 text-sm text-ink-muted lg:block print:hidden">
            <div className="mx-auto max-w-6xl">
              Sahkar Saathi · SIH 2026 problem statement 26088 · Prototype. Information, not legal
              advice.
            </div>
          </footer>
        )}
      </div>

      <MobileNavigation
        open={menuOpen}
        onOpen={() => setMenuOpen(true)}
        onClose={() => setMenuOpen(false)}
      />
      <ScrollRestoration />
    </div>
  );
}
