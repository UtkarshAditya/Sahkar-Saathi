import type { ReactNode } from 'react';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';

interface PageHeaderProps {
  title: string;
  description?: ReactNode;
  icon?: ReactNode;
  badges?: ReactNode;
  actions?: ReactNode;
}

export function PageHeader({ title, description, icon, badges, actions }: PageHeaderProps) {
  useDocumentTitle(title);

  return (
    <header className="mb-8 sm:mb-10">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          {icon && (
            <span className="mt-0.5 hidden size-10 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700 sm:flex [&>svg]:size-5">
              {icon}
            </span>
          )}
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold tracking-tight sm:text-[1.75rem]">{title}</h1>
            {description && <p className="mt-2 max-w-2xl text-ink-soft">{description}</p>}
            {badges && <div className="mt-3 flex flex-wrap gap-2">{badges}</div>}
          </div>
        </div>
        {actions && <div className="flex shrink-0 flex-wrap gap-2 print:hidden">{actions}</div>}
      </div>
    </header>
  );
}
