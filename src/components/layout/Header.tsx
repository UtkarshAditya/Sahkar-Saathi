import { Link, useLocation } from 'react-router';
import { CircleQuestionMark, MapPin, Menu } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { findNavItem } from '@/app/navigation';
import { LanguageSelector } from '@/components/common/LanguageSelector';
import { stateName } from '@/data/options';
import { useSettings } from '@/hooks/useSettings';
import { Brand } from './Brand';

export function Header({ onOpenMenu }: { onOpenMenu: () => void }) {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const { stateCode } = useSettings();
  const current = findNavItem(pathname);
  const isStaffRoute = pathname.startsWith('/staff') || pathname.startsWith('/admin');

  return (
    <header className="sticky top-0 z-20 border-b border-line bg-surface/95 backdrop-blur-xl shadow-[0_1px_0_rgba(20,56,38,0.08)]">
      <div className="flex min-h-16 items-center gap-3 px-4 sm:px-6 lg:px-10">
        {/* Phone and tablet */}
        <div className="flex min-w-0 flex-1 items-center lg:hidden">
          <Brand compact />
        </div>

        {/* Desktop: where you are */}
        <div className="hidden min-w-0 flex-1 items-center gap-2 text-sm text-ink-muted lg:flex">
          {current && !isStaffRoute && (
            <div className="inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50 px-3 py-1.5">
              <span className="text-xs font-semibold tracking-[0.12em] text-brand-700 uppercase">
                {t(`nav.groups.${current.group}`)}
              </span>
              <span aria-hidden className="text-brand-400">
                /
              </span>
              <span className="font-semibold text-ink">{t(current.labelKey)}</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          {stateCode && (
            <span className="hidden items-center gap-1 rounded-full border border-brand-200 bg-brand-50 px-2.5 py-1 text-xs font-semibold text-brand-800 md:inline-flex">
              <MapPin className="size-3.5" aria-hidden />
              {stateName(stateCode)}
            </span>
          )}
          <LanguageSelector variant="compact" className="hidden min-[20rem]:block lg:hidden" />
          <Link
            to="/about"
            className="hidden min-h-12 items-center gap-1.5 rounded-xl border border-brand-200 bg-brand-50 px-3 text-sm font-semibold text-brand-800 shadow-sm transition-colors hover:bg-brand-100 sm:inline-flex"
          >
            <CircleQuestionMark className="size-4" aria-hidden />
            {t('header.help')}
          </Link>
          <button
            type="button"
            onClick={onOpenMenu}
            className="flex size-12 items-center justify-center rounded-xl border border-line bg-surface text-ink shadow-sm transition-colors hover:bg-brand-50 lg:hidden"
            aria-label={t('nav.openMenu')}
          >
            <Menu className="size-5" aria-hidden />
          </button>
        </div>
      </div>
    </header>
  );
}
