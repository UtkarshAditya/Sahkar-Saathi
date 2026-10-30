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

const BAR_ITEM =
  'flex min-h-16 w-full flex-col items-center justify-center gap-0.5 px-1 text-xs font-semibold';

/** Phone and tablet navigation: a bottom bar for Ask and Grievance, and a full menu drawer. */
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
        className="m-0 h-dvh max-h-dvh w-[min(18rem,85vw)] max-w-none border-r border-line bg-surface p-0 text-ink backdrop:bg-ink/30 lg:hidden"
      >
        <div className="flex h-full flex-col">
          <div className="flex h-16 items-center justify-between px-4">
            <Brand />
            <button
              type="button"
              onClick={onClose}
              className="flex size-11 items-center justify-center rounded-lg text-ink-muted hover:bg-subtle hover:text-ink"
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
        className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] lg:hidden print:hidden"
      >
        <ul className="mx-auto grid max-w-md grid-cols-3">
          {NAV_ITEMS.filter((item) => item.primaryOnMobile).map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                reloadDocument={item.reloadDocument}
                end={item.to === '/'}
                className={({ isActive }) =>
                  cn(BAR_ITEM, isActive ? 'text-brand-800' : 'text-ink-muted hover:text-ink')
                }
              >
                {({ isActive }) => (
                  <>
                    <span
                      className={cn(
                        'flex h-7 w-12 items-center justify-center rounded-full',
                        isActive && 'bg-brand-100',
                      )}
                    >
                      <item.icon className="size-5" aria-hidden />
                    </span>
                    <span className="max-w-full truncate">{t(item.labelKey)}</span>
                  </>
                )}
              </NavLink>
            </li>
          ))}
          <li>
            <button
              type="button"
              onClick={onOpen}
              aria-haspopup="dialog"
              className={cn(BAR_ITEM, 'text-ink-muted hover:text-ink')}
            >
              <span className="flex h-7 w-12 items-center justify-center rounded-full">
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
