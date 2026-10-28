import { BookOpen, ExternalLink, Quote } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/common/Card';
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
    <Card as="aside" padding="sm" aria-labelledby="citations-heading">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 id="citations-heading" className="flex items-center gap-2 font-semibold">
          <BookOpen className="size-5 text-brand-700" aria-hidden />
          {t('chat.sources')}
        </h2>
      </div>

      {!citations || citations.length === 0 ? (
        <p className="text-sm text-ink-muted">{t('chat.noSources')}</p>
      ) : (
        <ol className="flex flex-col gap-3">
          {citations.map((c, i) => (
            <li key={c.id} className="rounded-xl border border-line bg-canvas p-3">
              <p className="flex gap-2 font-semibold">
                <span className="flex size-6 shrink-0 items-center justify-center rounded bg-brand-800 text-xs text-white">
                  {i + 1}
                </span>
                <span>{c.title}</span>
              </p>
              <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-sm">
                {c.publisher.trim() && (
                  <>
                    <dt className="text-ink-muted">Publisher</dt>
                    <dd>{c.publisher}</dd>
                  </>
                )}
                <dt className="text-ink-muted">Date</dt>
                <dd>
                  {c.published_date ? formatDate(c.published_date) : t('common.dateNotStated')}
                </dd>
                <dt className="text-ink-muted">{t('common.page')}</dt>
                <dd>
                  {c.page ?? '—'}
                  {c.section ? ` · ${c.section}` : ''}
                </dd>
              </dl>
              {c.excerpt && (
                <blockquote className="mt-2 flex gap-2 border-l-2 border-saffron-300 pl-2 text-sm text-ink-soft italic">
                  <Quote className="size-4 shrink-0 text-saffron-500" aria-hidden />
                  {c.excerpt}
                </blockquote>
              )}
              {c.url && (
                <div className="mt-2">
                  <a
                    href={c.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-sm font-semibold text-brand-800 underline"
                  >
                    Open original
                    <ExternalLink className="size-3.5" aria-hidden />
                  </a>
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
