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

  return (
    <header className="sticky top-0 z-20 border-b border-line bg-surface/95 backdrop-blur">
      <div className="flex min-h-16 items-center gap-3 px-4 sm:px-6 lg:px-10">
        {/* Phone and tablet */}
        <div className="flex min-w-0 flex-1 items-center lg:hidden">
          <Brand compact />
        </div>

        {/* Desktop: where you are */}
        <div className="hidden min-w-0 flex-1 items-center gap-2 text-sm text-ink-muted lg:flex">
          {current && (
            <>
              <span>{t(`nav.groups.${current.group}`)}</span>
              <span aria-hidden>/</span>
              <span className="font-semibold text-ink">{t(current.labelKey)}</span>
            </>
          )}
        </div>

        <div className="flex items-center gap-2">
          {stateCode && (
            <span className="hidden items-center gap-1 rounded-full bg-brand-50 px-2.5 py-1 text-xs font-semibold text-brand-800 ring-1 ring-brand-200 md:inline-flex">
              <MapPin className="size-3.5" aria-hidden />
              {stateName(stateCode)}
            </span>
          )}
          <LanguageSelector variant="compact" className="lg:hidden" />
          <Link
            to="/about"
            className="hidden min-h-10 items-center gap-1.5 rounded-lg px-3 text-sm font-semibold text-brand-800 hover:bg-brand-50 sm:inline-flex"
          >
            <CircleQuestionMark className="size-4" aria-hidden />
            {t('header.help')}
          </Link>
          <button
            type="button"
            onClick={onOpenMenu}
            className="flex size-10 items-center justify-center rounded-lg border border-line text-ink hover:bg-brand-50 lg:hidden"
            aria-label={t('nav.openMenu')}
          >
            <Menu className="size-5" aria-hidden />
          </button>
        </div>
      </div>
    </header>
  );
}
