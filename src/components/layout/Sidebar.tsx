import { useId, useState } from 'react';
import { NavLink, useLocation } from 'react-router';
import { ChevronDown, PanelLeftClose, PanelLeftOpen, ShieldCheck } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { findNavItem, NAV_ITEMS, type NavGroup, type NavItem } from '@/app/navigation';
import { cn } from '@/lib/format';
import { Brand } from './Brand';

function itemsIn(group: NavGroup): NavItem[] {
  return NAV_ITEMS.filter((item) => item.group === group);
}

interface NavRowProps {
  item: NavItem;
  collapsed: boolean;
  onNavigate?: () => void;
}

function NavRow({ item, collapsed, onNavigate }: NavRowProps) {
  const { t } = useTranslation();
  const label = t(item.labelKey);
  return (
    <li>
      <NavLink
        to={item.to}
        reloadDocument={item.reloadDocument}
        end={item.to === '/'}
        onClick={onNavigate}
        title={collapsed ? label : undefined}
        className={({ isActive }) =>
          cn(
            'flex min-h-11 items-center gap-3 rounded-lg text-[0.9375rem] transition-colors',
            collapsed ? 'justify-center px-0' : 'px-3',
            isActive
              ? 'bg-brand-100 font-semibold text-brand-900'
              : 'font-medium text-ink-soft hover:bg-subtle hover:text-ink',
          )
        }
      >
        {({ isActive }) => (
          <>
            <item.icon
              className={cn('size-5 shrink-0', isActive ? 'text-brand-700' : 'text-ink-muted')}
              aria-hidden
            />
            <span className={cn('truncate', collapsed && 'sr-only')}>{label}</span>
          </>
        )}
      </NavLink>
    </li>
  );
}

interface SidebarContentProps {
  /** Icons only (desktop). */
  collapsed?: boolean;
  onNavigate?: () => void;
}

/** Grouped navigation. Shared by the desktop sidebar and the mobile drawer. */
export function SidebarContent({ collapsed = false, onNavigate }: SidebarContentProps) {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const staffId = useId();
  const onStaffPage = findNavItem(pathname)?.group === 'staff';
  const [staffOpen, setStaffOpen] = useState(onStaffPage);
  const showStaff = staffOpen || onStaffPage;

  const groupHeading = (label: string) =>
    collapsed ? (
      <div className="mx-3 my-2 border-t border-line" role="presentation" />
    ) : (
      <p className="mt-4 mb-1 px-3 text-xs font-semibold text-ink-muted">{label}</p>
    );

  return (
    <nav
      aria-label={t('nav.primary')}
      className={cn('flex flex-1 flex-col overflow-y-auto py-4', collapsed ? 'px-2' : 'px-3')}
    >
      <ul className="flex flex-col gap-0.5">
        {itemsIn('core').map((item) => (
          <NavRow key={item.to} item={item} collapsed={collapsed} onNavigate={onNavigate} />
        ))}
      </ul>

      {groupHeading(t('nav.groups.library'))}
      <ul className="flex flex-col gap-0.5" aria-label={t('nav.groups.library')}>
        {itemsIn('library').map((item) => (
          <NavRow key={item.to} item={item} collapsed={collapsed} onNavigate={onNavigate} />
        ))}
      </ul>

      <div className={collapsed ? 'mx-3 my-2 border-t border-line' : 'my-2'} role="presentation" />
      <ul className="flex flex-col gap-0.5">
        {itemsIn('help').map((item) => (
          <NavRow key={item.to} item={item} collapsed={collapsed} onNavigate={onNavigate} />
        ))}
      </ul>

      <div className="mt-auto pt-4">
        <button
          type="button"
          aria-expanded={showStaff}
          aria-controls={staffId}
          onClick={() => setStaffOpen((open) => !open)}
          title={collapsed ? t('nav.groups.staff') : undefined}
          className={cn(
            'flex min-h-11 w-full items-center gap-3 rounded-lg text-sm font-medium text-ink-muted hover:bg-subtle hover:text-ink',
            collapsed ? 'justify-center' : 'px-3',
          )}
        >
          <ShieldCheck className="size-5 shrink-0" aria-hidden />
          <span className={cn('flex-1 text-left', collapsed && 'sr-only')}>
            {t('nav.groups.staff')}
          </span>
          <ChevronDown
            className={cn(
              'size-4 shrink-0 transition-transform',
              showStaff && 'rotate-180',
              collapsed && 'hidden',
            )}
            aria-hidden
          />
        </button>
        <ul id={staffId} hidden={!showStaff} className="mt-0.5 flex flex-col gap-0.5">
          {itemsIn('staff').map((item) => (
            <NavRow key={item.to} item={item} collapsed={collapsed} onNavigate={onNavigate} />
          ))}
        </ul>
      </div>
    </nav>
  );
}

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const { t } = useTranslation();
  return (
    <aside
      className={cn(
        'fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-line bg-surface lg:flex print:hidden',
        collapsed ? 'w-[4.5rem]' : 'w-64',
      )}
    >
      <div className={cn('flex h-16 items-center', collapsed ? 'justify-center' : 'px-5')}>
        <Brand iconOnly={collapsed} />
      </div>
      <SidebarContent collapsed={collapsed} />
      <div className={cn('border-t border-line py-2', collapsed ? 'px-2' : 'px-3')}>
        <button
          type="button"
          onClick={onToggle}
          aria-label={collapsed ? t('nav.expandSidebar') : t('nav.collapseSidebar')}
          title={collapsed ? t('nav.expandSidebar') : undefined}
          className={cn(
            'flex min-h-11 w-full items-center gap-3 rounded-lg text-sm font-medium text-ink-muted hover:bg-subtle hover:text-ink',
            collapsed ? 'justify-center' : 'px-3',
          )}
        >
          {collapsed ? (
            <PanelLeftOpen className="size-5" aria-hidden />
          ) : (
            <>
              <PanelLeftClose className="size-5" aria-hidden />
              <span>{t('nav.collapseSidebar')}</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}
