import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { Landmark, MessageSquareText, SearchX } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Card } from '@/components/common/Card';
import { EmptyState, ErrorState, LoadingState } from '@/components/common/EmptyState';
import { Modal } from '@/components/common/Modal';
import { PageHeader } from '@/components/common/PageHeader';
import { SearchInput } from '@/components/common/SearchInput';
import { SourceMeta } from '@/components/common/SourceMeta';
import { SCHEME_CATEGORIES } from '@/data/mockSchemes';
import { useAsync } from '@/hooks/useAsync';
import { cn } from '@/lib/format';
import { api } from '@/services/api';
import type { Scheme, SchemeCategory } from '@/types';

function categoryLabel(id: SchemeCategory) {
  return SCHEME_CATEGORIES.find((c) => c.id === id)?.label ?? id;
}

export default function SchemesPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data, loading, error, reload } = useAsync(api.listSchemes);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<SchemeCategory | 'all'>('all');
  const [open, setOpen] = useState<Scheme | null>(null);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (data ?? []).filter(
      (s) =>
        (category === 'all' || s.category === category) &&
        (!q || `${s.title} ${s.summary}`.toLowerCase().includes(q)),
    );
  }, [data, search, category]);

  function askAbout(scheme: Scheme) {
    navigate(`/?q=${encodeURIComponent(`Tell me about ${scheme.title}. Who can use it and how?`)}`);
  }

  return (
    <>
      <PageHeader
        title={t('pages.schemes.title')}
        description={t('pages.schemes.description')}
        icon={<Landmark className="size-6" aria-hidden />}
        badges={<Badge tone="saffron">{t('common.sample')}: details not yet verified</Badge>}
      />

      <Card padding="sm" className="mb-6">
        <SearchInput
          label="Search schemes"
          value={search}
          onChange={setSearch}
          placeholder="e.g. storage, credit, PACS"
        />
        <div role="group" aria-label="Filter by category" className="mt-4 flex flex-wrap gap-2">
          {[{ id: 'all' as const, label: t('common.all') }, ...SCHEME_CATEGORIES].map((c) => (
            <button
              key={c.id}
              type="button"
              aria-pressed={category === c.id}
              onClick={() => setCategory(c.id)}
              className={cn(
                'min-h-10 rounded-full border px-3.5 text-sm font-medium transition-colors',
                category === c.id
                  ? 'border-brand-700 bg-brand-800 text-white'
                  : 'border-line bg-surface text-ink-soft hover:bg-brand-50',
              )}
            >
              {c.label}
            </button>
          ))}
        </div>
      </Card>

      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error.message} onRetry={reload} />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<SearchX className="size-6" aria-hidden />}
          title={t('common.noResults')}
          description="No scheme matches your search. Try another word or category."
          action={
            <Button
              variant="secondary"
              onClick={() => {
                setSearch('');
                setCategory('all');
              }}
            >
              {t('common.clearFilters')}
            </Button>
          }
        />
      ) : (
        <>
          <p className="mb-3 text-sm text-ink-muted" aria-live="polite">
            {filtered.length} of {data?.length ?? 0} schemes
          </p>
          <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filtered.map((scheme) => (
              <li key={scheme.slug}>
                <Card as="article" className="flex h-full flex-col">
                  <div className="mb-2 flex flex-wrap gap-2">
                    <Badge tone="brand">{categoryLabel(scheme.category)}</Badge>
                    {scheme.is_sample && <Badge tone="saffron">{t('common.sample')}</Badge>}
                  </div>
                  <h2 className="text-lg font-semibold">{scheme.title}</h2>
                  <p className="mt-1 text-ink-soft">{scheme.summary}</p>
                  <dl className="mt-3 flex-1 text-sm">
                    <dt className="font-semibold">Who can use it</dt>
                    <dd className="text-ink-muted">{scheme.eligibility}</dd>
                  </dl>
                  <div className="mt-4 border-t border-line pt-3">
                    <SourceMeta
                      sourceLabel={scheme.source_label}
                      sourceUrl={scheme.source_url}
                      asOf={scheme.as_of}
                    />
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button variant="secondary" size="sm" onClick={() => setOpen(scheme)}>
                      {t('common.viewDetails')}
                    </Button>
                    <Button
                      variant="subtle"
                      size="sm"
                      onClick={() => askAbout(scheme)}
                      icon={<MessageSquareText className="size-4" aria-hidden />}
                    >
                      {t('common.askAboutThis')}
                    </Button>
                  </div>
                </Card>
              </li>
            ))}
          </ul>
        </>
      )}

      <Modal
        open={open !== null}
        onClose={() => setOpen(null)}
        title={open?.title ?? ''}
        footer={
          open && (
            <>
              <Button variant="secondary" onClick={() => setOpen(null)}>
                {t('common.close')}
              </Button>
              <Button
                onClick={() => askAbout(open)}
                icon={<MessageSquareText className="size-5" aria-hidden />}
              >
                {t('common.askAboutThis')}
              </Button>
            </>
          )
        }
      >
        {open && (
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap gap-2">
              <Badge tone="brand">{categoryLabel(open.category)}</Badge>
              {open.is_sample && <Badge tone="saffron">{t('common.sample')}</Badge>}
            </div>
            <dl className="flex flex-col gap-3">
              <div>
                <dt className="font-semibold">What it is</dt>
                <dd className="text-ink-soft">{open.summary}</dd>
              </div>
              <div>
                <dt className="font-semibold">Who can use it</dt>
                <dd className="text-ink-soft">{open.eligibility}</dd>
              </div>
              <div>
                <dt className="font-semibold">How to access it</dt>
                <dd className="text-ink-soft">{open.how_to_access}</dd>
              </div>
            </dl>
            <SourceMeta
              sourceLabel={open.source_label}
              sourceUrl={open.source_url}
              asOf={open.as_of}
            />
          </div>
        )}
      </Modal>
    </>
  );
}
