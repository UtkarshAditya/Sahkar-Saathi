import {
  BookOpen,
  ChartColumn,
  GraduationCap,
  Info,
  MessageSquareText,
  Scale,
  Settings,
  type LucideIcon,
} from 'lucide-react';
import { USE_MOCKS } from '@/services/api';

/** core: Ask and Grievance; library: reference pages; help: About; staff: collapsed group. */
export type NavGroup = 'core' | 'library' | 'help' | 'staff';

export interface NavItem {
  to: string;
  /** i18n key under nav.* */
  labelKey: string;
  /** i18n key prefix under pages.* (title, description) */
  pageKey: string;
  icon: LucideIcon;
  group: NavGroup;
  /** Shown in the phone bottom bar. */
  primaryOnMobile?: boolean;
  /** Full page load instead of client-side routing (the page is served by Django). */
  reloadDocument?: boolean;
}

/** One source of truth for the sidebar, mobile menu, header title and bottom bar. */
export const NAV_ITEMS: NavItem[] = [
  {
    to: '/',
    labelKey: 'nav.ask',
    pageKey: 'ask',
    icon: MessageSquareText,
    group: 'core',
    primaryOnMobile: true,
  },
  {
    to: '/grievance',
    labelKey: 'nav.grievance',
    pageKey: 'grievance',
    icon: Scale,
    group: 'core',
    primaryOnMobile: true,
  },
  { to: '/library', labelKey: 'nav.library', pageKey: 'library', icon: BookOpen, group: 'library' },
  { to: '/learn', labelKey: 'nav.learn', pageKey: 'learn', icon: GraduationCap, group: 'library' },
  { to: '/about', labelKey: 'nav.about', pageKey: 'about', icon: Info, group: 'help' },
  {
    to: '/staff/quality',
    labelKey: 'nav.quality',
    pageKey: 'quality',
    icon: ChartColumn,
    group: 'staff',
  },
  {
    // With the real backend, /admin/ is the Django admin site (Caddy or the Vite proxy
    // routes it there); in mock mode it is the React overview page.
    to: USE_MOCKS ? '/admin' : '/admin/',
    labelKey: 'nav.admin',
    pageKey: 'admin',
    icon: Settings,
    group: 'staff',
    reloadDocument: !USE_MOCKS,
  },
];

export const NAV_GROUPS: NavGroup[] = ['core', 'library', 'help', 'staff'];

export function findNavItem(pathname: string): NavItem | undefined {
  return NAV_ITEMS.find((item) =>
    item.to === '/' ? pathname === '/' : pathname === item.to || pathname.startsWith(`${item.to}/`),
  );
}
