import { useLocation } from 'react-router';
import { useTranslation } from 'react-i18next';
import { findNavItem } from '@/app/navigation';
import { LanguageSelector } from '@/components/common/LanguageSelector';
import { StateSelector } from '@/components/common/StateSelector';

/** Minimal top bar: where you are, plus the language and state choices. */
export function Header() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const current = findNavItem(pathname);
  const title = current ? t(current.labelKey) : t('pages.notFound.title');

  return (
    <header className="sticky top-0 z-20 border-b border-line bg-canvas/90 backdrop-blur print:hidden">
      <div className="flex h-16 items-center gap-2 px-4 sm:gap-3 sm:px-6 lg:px-8">
        <p className="min-w-0 flex-1 truncate font-semibold text-ink">{title}</p>
        <LanguageSelector variant="compact" />
        <StateSelector variant="compact" />
      </div>
    </header>
  );
}
