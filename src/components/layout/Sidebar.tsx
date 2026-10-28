import { NavLink, useLocation } from 'react-router';
import { Check, ShieldAlert } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { NAV_GROUPS, NAV_ITEMS } from '@/app/navigation';
import { LanguageSelector } from '@/components/common/LanguageSelector';
import { StateSelector } from '@/components/common/StateSelector';
import { cn } from '@/lib/format';
import { Brand } from './Brand';

/** Navigation, language and state selectors, and the safety notice. Shared with the mobile drawer. */
export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const isStaffRoute = pathname.startsWith('/staff') || pathname.startsWith('/admin');

  return (
    <div className="flex h-full flex-col gap-6 overflow-y-auto px-4 py-5">
      <nav aria-label={t('nav.primary')} className="flex flex-col gap-5">
        {NAV_GROUPS.map((group) => (
          <div key={group}>
            <p className="mb-2 px-3 text-[0.7rem] font-semibold tracking-[0.18em] text-ink-muted uppercase">
              {t(`nav.groups.${group}`)}
            </p>
            <ul className="flex flex-col gap-1.5">
              {NAV_ITEMS.filter((item) => item.group === group).map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    reloadDocument={item.reloadDocument}
                    end={item.to === '/'}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      cn(
                        'relative flex min-h-12 items-center gap-3 rounded-xl border px-3 font-semibold transition-all duration-200',
                        isActive
                          ? 'border-brand-800 bg-brand-800 text-white shadow-[0_10px_18px_rgba(26,69,47,0.18)]'
                          : 'border-transparent bg-transparent text-ink-soft hover:border-brand-200 hover:bg-brand-50 hover:text-brand-900',
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <span
                          className={cn(
                            'flex size-8 items-center justify-center rounded-lg border',
                            isActive
                              ? 'border-white/25 bg-white/10 text-saffron-200'
                              : 'border-brand-100 bg-brand-50 text-brand-700',
                          )}
                        >
                          <item.icon className="size-4" aria-hidden />
                        </span>
                        <span className="flex-1 text-left">{t(item.labelKey)}</span>
                        {isActive && <Check className="size-4 shrink-0" aria-hidden />}
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      <section
        aria-labelledby="settings-heading"
        className="flex flex-col gap-4 border-t border-line bg-surface-alt/60 p-3 pt-5"
      >
        <h2 id="settings-heading" className="sr-only">
          {t('settings.title')}
        </h2>
        <LanguageSelector />
        <StateSelector showHint />
      </section>

      {!isStaffRoute && (
        <p className="mt-auto flex gap-2 rounded-2xl border-2 border-saffron-700 bg-saffron-50 px-3 py-2.5 text-xs leading-relaxed text-saffron-900 shadow-[0_6px_16px_rgba(156,70,10,0.08)]">
          <ShieldAlert className="size-4 shrink-0 text-saffron-700" aria-hidden />
          {t('notice.sidebar')}
        </p>
      )}
    </div>
  );
}

export function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-72 flex-col border-r border-line bg-surface shadow-[8px_0_24px_rgba(20,56,38,0.08)] lg:flex">
      <div className="border-b border-line bg-surface-alt/50 px-5 py-4">
        <Brand />
      </div>
      <SidebarContent />
    </aside>
  );
}
