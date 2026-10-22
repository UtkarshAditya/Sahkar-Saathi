import { useEffect, useState } from 'react';
import { Outlet, ScrollRestoration, useLocation } from 'react-router';
import { useTranslation } from 'react-i18next';
import { Header } from './Header';
import { MobileNavigation } from './MobileNavigation';
import { Sidebar } from './Sidebar';
import { LegalNotice } from '@/components/common/Notice';

export default function AppLayout() {
  const { t } = useTranslation();
  const [menuOpen, setMenuOpen] = useState(false);
  const { pathname } = useLocation();
  const isAskRoute = pathname === '/';

  // Close the drawer whenever the route changes.
  useEffect(() => setMenuOpen(false), [pathname]);

  return (
    <div className={isAskRoute ? 'h-dvh overflow-hidden' : 'min-h-dvh'}>
      <a
        href="#main"
        className="sr-only z-50 rounded-lg bg-brand-800 px-4 py-2 font-semibold text-white focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        {t('nav.skipToContent')}
      </a>

      <Sidebar />

      <div
        className={
          isAskRoute ? 'flex h-dvh min-h-0 flex-col lg:pl-72' : 'flex min-h-dvh flex-col lg:pl-72'
        }
      >
        <Header onOpenMenu={() => setMenuOpen(true)} chatMode={isAskRoute} />
        <main
          id="main"
          tabIndex={-1}
          className={
            isAskRoute
              ? 'flex min-h-0 flex-1 flex-col overflow-hidden px-0 py-0 outline-none'
              : 'flex-1 px-4 pt-6 pb-28 outline-none sm:px-6 sm:pt-8 lg:px-10 lg:pb-12'
          }
        >
          <div
            className={
              isAskRoute
                ? 'mx-auto flex h-full min-h-0 w-full max-w-6xl flex-1 flex-col'
                : 'mx-auto max-w-6xl'
            }
          >
            <Outlet />
            {!isAskRoute && <LegalNotice compact className="mt-8" />}
          </div>
        </main>
        <footer
          className={
            isAskRoute
              ? 'hidden'
              : 'hidden border-t border-line px-10 py-4 text-sm text-ink-muted lg:block'
          }
        >
          <div className="mx-auto max-w-6xl">Sahkar Saathi · SIH 2026 problem statement 26088</div>
        </footer>
      </div>

      <MobileNavigation
        open={menuOpen}
        onOpen={() => setMenuOpen(true)}
        onClose={() => setMenuOpen(false)}
        hideBottomNav={isAskRoute}
      />
      <ScrollRestoration />
    </div>
  );
}
