import { useId, useState } from 'react';
import { ChevronDown, ExternalLink, FileText } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn, formatDate } from '@/lib/format';
import type { Citation } from '@/types';

/** Collapsed by default when an answer has more sources than this. */
const OPEN_UP_TO = 2;

function SourceItem({ citation, index }: { citation: Citation; index: number }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const meta = [
    citation.section,
    citation.page != null ? `${t('common.page')} ${citation.page}` : null,
    citation.published_date ? formatDate(citation.published_date) : t('common.dateNotStated'),
  ].filter(Boolean);

  return (
    <li className="rounded-xl border border-line bg-surface">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className="flex min-h-11 w-full items-start gap-3 rounded-xl px-3 py-2.5 text-left hover:bg-subtle"
      >
        <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded bg-brand-50 text-xs font-semibold text-brand-800">
          {index + 1}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium text-ink">{citation.title}</span>
          <span className="block text-xs text-ink-muted">{meta.join(' · ')}</span>
        </span>
        <ChevronDown
          className={cn(
            'mt-0.5 size-4 shrink-0 text-ink-muted transition-transform',
            open && 'rotate-180',
          )}
          aria-hidden
        />
      </button>
      <div id={panelId} hidden={!open} className="border-t border-line px-3 py-3 text-sm">
        {citation.publisher && <p className="text-ink-muted">{citation.publisher}</p>}
        {citation.excerpt && (
          <blockquote className="mt-2 border-l-2 border-brand-200 pl-3 text-ink-soft">
            {citation.excerpt}
          </blockquote>
        )}
        <p className="mt-2">
          {citation.url ? (
            <a
              href={citation.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex min-h-11 items-center gap-1 font-semibold text-brand-800 underline underline-offset-2 lg:min-h-0"
            >
              {t('chat.openSource')}
              <ExternalLink className="size-3.5" aria-hidden />
              <span className="sr-only">({t('chat.opensInNewTab')})</span>
            </a>
          ) : (
            <span className="text-ink-muted">{t('common.linkPending')}</span>
          )}
        </p>
      </div>
    </li>
  );
}

/** The sources of one answer, shown right under it. Each expands in place to its excerpt. */
export function SourceList({ citations }: { citations: Citation[] }) {
  const { t } = useTranslation();
  const listId = useId();
  const [expanded, setExpanded] = useState(citations.length <= OPEN_UP_TO);
  if (citations.length === 0) return null;

  const count = t('chat.sourceCount', { count: citations.length });

  return (
    <section className="mt-4" aria-label={`${t('chat.sources')}: ${count}`}>
      {citations.length > OPEN_UP_TO ? (
        <button
          type="button"
          aria-expanded={expanded}
          aria-controls={listId}
          onClick={() => setExpanded((v) => !v)}
          className="-ml-2 flex min-h-11 items-center gap-1.5 rounded-lg px-2 text-sm font-semibold text-ink-soft hover:bg-subtle hover:text-ink lg:min-h-9"
        >
          <FileText className="size-4" aria-hidden />
          {t('chat.sources')} · {count}
          <ChevronDown
            className={cn('size-4 transition-transform', expanded && 'rotate-180')}
            aria-hidden
          />
        </button>
      ) : (
        <p className="flex items-center gap-1.5 text-sm font-semibold text-ink-soft">
          <FileText className="size-4" aria-hidden />
          {t('chat.sources')} · {count}
        </p>
      )}
      <ol id={listId} hidden={!expanded} className="mt-2 grid items-start gap-2 sm:grid-cols-2">
        {citations.map((c, i) => (
          <SourceItem key={c.id} citation={c} index={i} />
        ))}
      </ol>
    </section>
  );
}
