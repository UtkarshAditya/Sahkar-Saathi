import {
  BookOpen,
  ChartColumn,
  GraduationCap,
  Info,
  Landmark,
  MessageSquareText,
  Scale,
  Settings,
  Sprout,
  type LucideIcon,
} from 'lucide-react';
import { USE_MOCKS } from '@/services/api';

export type NavGroup = 'core' | 'guides' | 'staff';

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

/** One source of truth for the sidebar, mobile menu, breadcrumbs and bottom bar. */
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
  { to: '/about', labelKey: 'nav.about', pageKey: 'about', icon: Info, group: 'core' },
  {
    to: '/crop-insurance',
    labelKey: 'nav.cropInsurance',
    pageKey: 'cropInsurance',
    icon: Sprout,
    group: 'guides',
    primaryOnMobile: true,
  },
  { to: '/schemes', labelKey: 'nav.schemes', pageKey: 'schemes', icon: Landmark, group: 'guides' },
  { to: '/library', labelKey: 'nav.library', pageKey: 'library', icon: BookOpen, group: 'guides' },
  { to: '/learn', labelKey: 'nav.learn', pageKey: 'learn', icon: GraduationCap, group: 'guides' },
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

export const NAV_GROUPS: NavGroup[] = ['core', 'guides', 'staff'];

export function findNavItem(pathname: string): NavItem | undefined {
  return NAV_ITEMS.find((item) =>
    item.to === '/' ? pathname === '/' : pathname === item.to || pathname.startsWith(`${item.to}/`),
  );
}
