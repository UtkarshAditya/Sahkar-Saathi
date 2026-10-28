import type { ReactNode } from 'react';
import { cn } from '@/lib/format';

export type BadgeTone = 'neutral' | 'brand' | 'saffron' | 'red' | 'blue';

const TONES: Record<BadgeTone, string> = {
  neutral: 'bg-stone-100 text-ink-soft ring-stone-200',
  brand: 'bg-brand-50 text-brand-800 ring-brand-200',
  saffron: 'bg-saffron-50 text-saffron-800 ring-saffron-200',
  red: 'bg-red-50 text-red-800 ring-red-200',
  blue: 'bg-sky-50 text-sky-800 ring-sky-200',
};

interface BadgeProps {
  tone?: BadgeTone;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function Badge({ tone = 'neutral', icon, children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset',
        TONES[tone],
        className,
      )}
    >
      {icon}
      {children}
    </span>
  );
}
