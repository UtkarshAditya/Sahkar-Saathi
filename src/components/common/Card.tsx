import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '@/lib/format';

interface CardProps extends HTMLAttributes<HTMLElement> {
  as?: 'div' | 'section' | 'article' | 'aside' | 'li';
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

const PADDING = { none: '', sm: 'p-4', md: 'p-5 sm:p-6', lg: 'p-6 sm:p-8' };

export function Card({ as: Tag = 'div', padding = 'md', className, ...rest }: CardProps) {
  return (
    <Tag
      className={cn('rounded-2xl border border-line bg-surface', PADDING[padding], className)}
      {...rest}
    />
  );
}

interface CardTitleProps {
  icon?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  level?: 2 | 3;
}

/** Consistent heading row for cards: optional icon tile, title, description, action. */
export function CardTitle({ icon, title, description, action, level = 2 }: CardTitleProps) {
  const Heading = level === 2 ? 'h2' : 'h3';
  return (
    <div className="mb-4 flex items-start gap-3">
      {icon && (
        <span className="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
          {icon}
        </span>
      )}
      <div className="min-w-0 flex-1">
        <Heading className={cn('font-semibold', level === 2 ? 'text-lg' : 'text-base')}>
          {title}
        </Heading>
        {description && <p className="mt-0.5 text-sm text-ink-muted">{description}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
