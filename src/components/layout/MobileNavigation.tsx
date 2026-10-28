import { useEffect, useRef } from 'react';
import { NavLink } from 'react-router';
import { Ellipsis, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { NAV_ITEMS } from '@/app/navigation';
import { cn } from '@/lib/format';
import { Brand } from './Brand';
import { SidebarContent } from './Sidebar';

interface MobileNavigationProps {
  open: boolean;
  onOpen: () => void;
  onClose: () => void;
}

/** Phone and tablet navigation: a bottom bar for the main pages and a full menu drawer. */
export function MobileNavigation({ open, onOpen, onClose }: MobileNavigationProps) {
  const { t } = useTranslation();
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <>
      <dialog
        ref={dialogRef}
        onClose={onClose}
        onClick={(e) => {
          if (e.target === dialogRef.current) onClose();
        }}
        aria-label={t('nav.primary')}
        className="m-0 h-dvh max-h-dvh w-[min(20rem,88vw)] max-w-none border-r border-line bg-surface p-0 text-ink backdrop:bg-brand-950/40 lg:hidden"
      >
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <Brand compact />
            <button
              type="button"
              onClick={onClose}
              className="flex size-12 items-center justify-center rounded-lg text-ink-muted hover:bg-canvas hover:text-ink"
              aria-label={t('nav.closeMenu')}
            >
              <X className="size-5" aria-hidden />
            </button>
          </div>
          <SidebarContent onNavigate={onClose} />
        </div>
      </dialog>

      <nav
        aria-label={t('nav.primary')}
        className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-surface/95 pb-[env(safe-area-inset-bottom)] shadow-[0_-6px_20px_rgba(20,56,38,0.06)] lg:hidden"
      >
        <ul className="mx-auto grid max-w-lg grid-cols-4">
          {NAV_ITEMS.filter((item) => item.primaryOnMobile).map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                reloadDocument={item.reloadDocument}
                end={item.to === '/'}
                className={({ isActive }) =>
                  cn(
                    'flex min-h-16 flex-col items-center justify-center gap-0.5 px-1 text-xs font-semibold transition-colors',
                    isActive ? 'text-brand-800' : 'text-ink-muted hover:text-brand-800',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <span
                      className={cn(
                        'flex h-8 w-12 items-center justify-center rounded-full border transition-colors',
                        isActive
                          ? 'border-brand-200 bg-brand-100 text-brand-800 shadow-sm'
                          : 'border-transparent bg-transparent text-current',
                      )}
                    >
                      <item.icon className="size-5" aria-hidden />
                    </span>
                    <span className="truncate">{t(item.labelKey)}</span>
                  </>
                )}
              </NavLink>
            </li>
          ))}
          <li>
            <button
              type="button"
              onClick={onOpen}
              className="flex min-h-16 w-full flex-col items-center justify-center gap-0.5 px-1 text-xs font-semibold text-ink-muted transition-colors hover:text-brand-800"
            >
              <span className="flex h-8 w-12 items-center justify-center rounded-full border border-transparent">
                <Ellipsis className="size-5" aria-hidden />
              </span>
              {t('nav.more')}
            </button>
          </li>
        </ul>
      </nav>
    </>
  );
}
