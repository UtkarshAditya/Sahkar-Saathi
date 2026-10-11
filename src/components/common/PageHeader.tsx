import type { ReactNode } from 'react';
import { ChevronRight } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';

export interface Crumb {
  label: string;
  to?: string;
}

interface PageHeaderProps {
  title: string;
  description?: ReactNode;
  icon?: ReactNode;
  /** Trail after "Home". The current page is added automatically. */
  breadcrumbs?: Crumb[];
  badges?: ReactNode;
  actions?: ReactNode;
}

export function PageHeader({
  title,
  description,
  icon,
  breadcrumbs,
  badges,
  actions,
}: PageHeaderProps) {
  const { t } = useTranslation();
  useDocumentTitle(title);

  return (
    <header className="mb-6 sm:mb-8">
      {breadcrumbs && (
        <nav aria-label="Breadcrumb" className="mb-3">
          <ol className="flex flex-wrap items-center gap-1 text-sm text-ink-muted">
            <li>
              <Link to="/" className="rounded hover:text-brand-800 hover:underline">
                {t('header.home')}
              </Link>
            </li>
            {breadcrumbs.map((crumb) => (
              <li key={crumb.label} className="flex items-center gap-1">
                <ChevronRight className="size-4" aria-hidden />
                {crumb.to ? (
                  <Link to={crumb.to} className="rounded hover:text-brand-800 hover:underline">
                    {crumb.label}
                  </Link>
                ) : (
                  <span>{crumb.label}</span>
                )}
              </li>
            ))}
            <li className="flex items-center gap-1">
              <ChevronRight className="size-4" aria-hidden />
              <span aria-current="page" className="font-medium text-ink-soft">
                {title}
              </span>
            </li>
          </ol>
        </nav>
      )}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-start gap-4">
          {icon && (
            <span className="hidden size-12 shrink-0 items-center justify-center rounded-2xl bg-brand-800 text-white sm:flex">
              {icon}
            </span>
          )}
          <div className="min-w-0">
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{title}</h1>
            {description && <p className="mt-1.5 max-w-2xl text-ink-soft">{description}</p>}
            {badges && <div className="mt-3 flex flex-wrap gap-2">{badges}</div>}
          </div>
        </div>
        {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
      </div>
    </header>
  );
}
