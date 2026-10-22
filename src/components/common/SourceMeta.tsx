import { CalendarDays, ExternalLink, FileText } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { formatDate } from '@/lib/format';

interface SourceMetaProps {
  sourceLabel: string;
  sourceUrl: string | null;
  asOf: string | null;
}

/** Source and date line shown under every fact, scheme and citation. */
export function SourceMeta({ sourceLabel, sourceUrl, asOf }: SourceMetaProps) {
  const { t } = useTranslation();
  return (
    <dl className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-muted">
      <div className="flex items-center gap-1.5">
        <FileText className="size-4 shrink-0" aria-hidden />
        <dt className="sr-only">{t('common.source')}</dt>
        <dd>
          {sourceUrl ? (
            <a
              href={sourceUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 font-medium text-brand-800 underline underline-offset-2"
            >
              {sourceLabel}
              <ExternalLink className="size-3.5" aria-hidden />
            </a>
          ) : (
            <span>{t('common.sourceBeingAdded')}</span>
          )}
        </dd>
      </div>
      {asOf && (
        <div className="flex items-center gap-1.5">
          <CalendarDays className="size-4 shrink-0" aria-hidden />
          <dt className="sr-only">{t('common.asOf')}</dt>
          <dd>{`${t('common.asOf')} ${formatDate(asOf)}`}</dd>
        </div>
      )}
    </dl>
  );
}
