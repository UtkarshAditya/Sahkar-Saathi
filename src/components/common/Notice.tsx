import type { ReactNode } from 'react';
import { CircleCheck, Info, ShieldAlert, TriangleAlert } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/format';

export type NoticeTone = 'info' | 'warning' | 'legal' | 'success';

const TONES: Record<NoticeTone, { box: string; icon: ReactNode }> = {
  info: {
    box: 'border-sky-700 bg-sky-50 text-sky-900',
    icon: <Info className="size-5 text-sky-700" aria-hidden />,
  },
  warning: {
    box: 'border-saffron-700 bg-saffron-50 text-saffron-800',
    icon: <TriangleAlert className="size-5 text-saffron-600" aria-hidden />,
  },
  legal: {
    box: 'border-saffron-700 bg-saffron-50 text-ink',
    icon: <ShieldAlert className="size-5 text-saffron-700" aria-hidden />,
  },
  success: {
    box: 'border-brand-700 bg-brand-50 text-brand-900',
    icon: <CircleCheck className="size-5 text-brand-700" aria-hidden />,
  },
};

interface NoticeProps {
  tone?: NoticeTone;
  title?: ReactNode;
  children?: ReactNode;
  className?: string;
  role?: 'note' | 'status' | 'alert';
}

export function Notice({ tone = 'info', title, children, className, role = 'note' }: NoticeProps) {
  const { box, icon } = TONES[tone];
  return (
    <div role={role} className={cn('flex gap-3 rounded-xl border-2 px-4 py-3', box, className)}>
      <span className="mt-0.5 shrink-0">{icon}</span>
      <div className="min-w-0 text-sm leading-relaxed [overflow-wrap:anywhere]">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={title ? 'mt-0.5' : undefined}>{children}</div>}
      </div>
    </div>
  );
}

/** Fixed "information, not legal advice" banner for Ask and Grievance helper. */
export function LegalNotice({ className }: { className?: string }) {
  const { t } = useTranslation();
  return (
    <Notice tone="legal" title={t('notice.legalTitle')} className={className}>
      {t('notice.legalBody')}
    </Notice>
  );
}
