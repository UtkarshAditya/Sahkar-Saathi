import { Link } from 'react-router';
import { CircleQuestionMark, Menu as MenuIcon } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { LanguageSelector } from '@/components/common/LanguageSelector';
import { Brand } from './Brand';

export function Header({
  onOpenMenu,
  chatMode = false,
}: {
  onOpenMenu: () => void;
  chatMode?: boolean;
}) {
  const { t } = useTranslation();

  return (
    <header
      className={
        chatMode
          ? 'z-20 shrink-0 border-b border-line bg-surface/95 backdrop-blur lg:hidden'
          : 'sticky top-0 z-20 border-b border-line bg-surface/95 backdrop-blur'
      }
    >
      <div className="flex min-h-16 items-center gap-3 px-4 sm:px-6 lg:px-10">
        {/* Phone and tablet */}
        {!chatMode && (
          <div className="flex min-w-0 flex-1 items-center lg:hidden">
            <Brand compact />
          </div>
        )}

        <div className={chatMode ? 'ml-auto flex items-center' : 'ml-auto flex items-center gap-2'}>
          {!chatMode && (
            <>
              <LanguageSelector variant="compact" className="lg:hidden" />
              <Link
                to="/about"
                className="hidden min-h-10 items-center gap-1.5 rounded-lg px-3 text-sm font-semibold text-brand-800 hover:bg-brand-50 sm:inline-flex"
              >
                <CircleQuestionMark className="size-4" aria-hidden />
                {t('header.help')}
              </Link>
            </>
          )}
          <button
            type="button"
            onClick={onOpenMenu}
            className="flex min-h-12 shrink-0 items-center justify-center gap-2 rounded-lg border border-line px-3 text-sm font-semibold text-ink hover:bg-brand-50 lg:hidden"
            aria-label={t('nav.menu')}
          >
            <MenuIcon className="size-5" aria-hidden />
            <span>{t('nav.menu')}</span>
          </button>
        </div>
      </div>
    </header>
  );
}
