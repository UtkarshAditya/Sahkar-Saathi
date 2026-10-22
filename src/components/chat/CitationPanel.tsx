import { ExternalLink, Quote } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { formatDate } from '@/lib/format';
import type { Citation } from '@/types';

/** Compact numbered list of sources, shown inside each answer. */
export function CitationList({ citations }: { citations: Citation[] }) {
  const { t } = useTranslation();
  if (citations.length === 0) return null;
  return (
    <ol className="mt-3 flex flex-col gap-1.5 border-t border-line pt-3 text-sm">
      {citations.map((c, i) => (
        <li key={c.id} className="flex gap-2">
          <span className="flex size-5 shrink-0 items-center justify-center rounded bg-brand-100 text-xs font-bold text-brand-800">
            {i + 1}
          </span>
          <span className="text-ink-soft">
            <span className="font-medium text-ink">{c.title}</span> ·{' '}
            {c.published_date ? formatDate(c.published_date) : t('common.dateNotStated')}
            {c.page != null && ` · ${t('common.page')} ${c.page}`}
          </span>
        </li>
      ))}
    </ol>
  );
}

interface CitationPanelProps {
  citations: Citation[] | null;
}

/** Detailed sources for the selected answer: title, publisher, date, page, excerpt and link. */
export function CitationPanel({ citations }: CitationPanelProps) {
  const { t } = useTranslation();

  return (
    <div aria-label={t('chat.sources')}>
      {!citations || citations.length === 0 ? (
        <p className="text-sm text-ink-muted">{t('chat.noSources')}</p>
      ) : (
        <ol className="flex flex-col gap-3">
          {citations.map((c, i) => (
            <li key={c.id} className="rounded-xl bg-canvas p-4">
              <p className="flex gap-2 font-semibold">
                <span className="flex size-6 shrink-0 items-center justify-center rounded bg-brand-800 text-xs text-white">
                  {i + 1}
                </span>
                <span>{c.title}</span>
              </p>
              <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-sm">
                <dt className="text-ink-muted">Publisher</dt>
                <dd>{c.publisher}</dd>
                <dt className="text-ink-muted">Date</dt>
                <dd>
                  {c.published_date ? formatDate(c.published_date) : t('common.dateNotStated')}
                </dd>
                {c.page != null && (
                  <>
                    <dt className="text-ink-muted">{t('common.page')}</dt>
                    <dd>{c.page}</dd>
                  </>
                )}
                {c.section && (
                  <>
                    <dt className="text-ink-muted">Section</dt>
                    <dd>{c.section}</dd>
                  </>
                )}
              </dl>
              {c.excerpt && (
                <blockquote className="mt-2 flex gap-2 border-l-2 border-saffron-300 pl-2 text-sm text-ink-soft italic">
                  <Quote className="size-4 shrink-0 text-saffron-500" aria-hidden />
                  {c.excerpt}
                </blockquote>
              )}
              <div className="mt-2">
                {c.url ? (
                  <a
                    href={c.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-sm font-semibold text-brand-800 underline"
                  >
                    Open original
                    <ExternalLink className="size-3.5" aria-hidden />
                  </a>
                ) : (
                  <span className="inline-flex items-center gap-1 text-sm text-ink-muted">
                    <ExternalLink className="size-3.5" aria-hidden />
                    {t('common.linkPending')}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
