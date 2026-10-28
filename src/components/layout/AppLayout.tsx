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
  const isStaffRoute = pathname.startsWith('/staff') || pathname.startsWith('/admin');

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

      <Sidebar />

      <div className="flex min-h-dvh flex-col lg:pl-72">
        <Header onOpenMenu={() => setMenuOpen(true)} />
        <main
          id="main"
          tabIndex={-1}
          className="flex-1 px-4 pt-6 pb-28 outline-none sm:px-6 sm:pt-8 lg:px-10 lg:pb-12"
        >
          <div className="mx-auto max-w-6xl">
            {!isStaffRoute && <LegalNotice className="mb-6" />}
            <Outlet />
          </div>
        </main>
        <footer className="hidden border-t border-line px-10 py-4 text-sm text-ink-muted lg:block">
          <div className="mx-auto max-w-6xl">
            Sahkar Saathi · SIH 2026 problem statement 26088 · Prototype.
            {!isStaffRoute && ' Information, not legal advice.'}
          </div>
        </footer>
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
