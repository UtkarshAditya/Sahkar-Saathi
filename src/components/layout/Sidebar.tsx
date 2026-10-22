import { NavLink } from 'react-router';
import { useTranslation } from 'react-i18next';
import { NAV_GROUPS, NAV_ITEMS } from '@/app/navigation';
import { LanguageSelector } from '@/components/common/LanguageSelector';
import { StateSelector } from '@/components/common/StateSelector';
import { cn } from '@/lib/format';
import { Brand } from './Brand';

/** Navigation, language and state selectors, and the safety notice. Shared with the mobile drawer. */
export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useTranslation();

  return (
    <div className="flex h-full flex-col gap-6 overflow-y-auto px-4 py-5">
      <section
        aria-labelledby="settings-heading"
        className="flex flex-col gap-4 border-b border-line pb-5"
      >
        <h2 id="settings-heading" className="sr-only">
          {t('settings.title')}
        </h2>
        <LanguageSelector />
        <StateSelector showHint />
      </section>

      <nav aria-label={t('nav.primary')} className="flex flex-col gap-5">
        {NAV_GROUPS.map((group) => (
          <div key={group}>
            <p className="mb-1.5 px-3 text-xs font-semibold tracking-wide text-ink-muted uppercase">
              {t(`nav.groups.${group}`)}
            </p>
            <ul className="flex flex-col gap-0.5">
              {NAV_ITEMS.filter((item) => item.group === group).map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    reloadDocument={item.reloadDocument}
                    end={item.to === '/'}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      cn(
                        'relative flex min-h-11 items-center gap-3 rounded-lg px-3 font-medium transition-colors',
                        isActive
                          ? 'bg-brand-800 text-white'
                          : 'text-ink-soft hover:bg-brand-50 hover:text-brand-900',
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <item.icon
                          className={cn(
                            'size-5 shrink-0',
                            isActive ? 'text-saffron-300' : 'text-brand-700',
                          )}
                          aria-hidden
                        />
                        <span>{t(item.labelKey)}</span>
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
    </div>
  );
}

export function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-72 flex-col border-r border-line bg-surface lg:flex">
      <div className="border-b border-line px-5 py-4">
        <Brand />
      </div>
      <SidebarContent />
    </aside>
  );
}
