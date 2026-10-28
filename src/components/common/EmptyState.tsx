import type { ReactNode } from 'react';
import { CircleAlert, Inbox, LoaderCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { apiErrorTranslationKey } from '@/services/api';
import { Button } from './Button';

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-line bg-surface px-6 py-10 text-center">
      <span className="mb-3 flex size-12 items-center justify-center rounded-full bg-brand-50 text-brand-700">
        {icon ?? <Inbox className="size-6" aria-hidden />}
      </span>
      <h3 className="text-lg font-semibold">{title}</h3>
      {description && <p className="mt-1 max-w-md text-ink-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function LoadingState({ label }: { label?: string }) {
  const { t } = useTranslation();
  return (
    <div
      role="status"
      className="flex items-center justify-center gap-2 rounded-2xl border border-line bg-surface px-6 py-10 text-ink-muted"
    >
      <LoaderCircle className="size-5 animate-spin" aria-hidden />
      {label ?? t('common.loading')}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error?: unknown; onRetry?: () => void }) {
  const { t } = useTranslation();
  return (
    <EmptyState
      icon={<CircleAlert className="size-6 text-red-700" aria-hidden />}
      title={t('chat.errorTitle')}
      description={t(apiErrorTranslationKey(error))}
      action={
        onRetry && (
          <Button variant="secondary" onClick={onRetry}>
            {t('common.retry')}
          </Button>
        )
      }
    />
  );
}
