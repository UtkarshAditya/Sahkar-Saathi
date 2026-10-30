import { useId, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { BookOpen, ExternalLink, MessageSquareText, SearchX } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Card } from '@/components/common/Card';
import { EmptyState, ErrorState, LoadingState } from '@/components/common/EmptyState';
import { Notice } from '@/components/common/Notice';
import { PageHeader } from '@/components/common/PageHeader';
import { SearchInput } from '@/components/common/SearchInput';
import { DOCUMENT_TYPES, documentTypeLabel } from '@/data/mockDocuments';
import { stateName } from '@/data/options';
import { useAsync } from '@/hooks/useAsync';
import { LANGUAGES } from '@/i18n';
import { formatDate } from '@/lib/format';
import { api } from '@/services/api';
import type { DocumentType, LibraryDocument } from '@/types';

function languageName(code: string) {
  return LANGUAGES.find((l) => l.code === code)?.label ?? code;
}

export default function LawLibraryPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const ids = { state: useId(), language: useId(), type: useId(), retired: useId() };
  const { data, loading, error, reload } = useAsync(() => api.listDocuments());

  const [search, setSearch] = useState('');
  const [state, setState] = useState('');
  const [language, setLanguage] = useState('');
  const [docType, setDocType] = useState<DocumentType | ''>('');
  const [showRetired, setShowRetired] = useState(false);

  const stateOptions = useMemo(
    () =>
      Array.from(new Set((data ?? []).map((d) => d.state))).sort((a) => (a === 'central' ? -1 : 1)),
    [data],
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (data ?? []).filter(
      (d) =>
        (showRetired || d.status === 'active') &&
        (!state || d.state === state) &&
        (!language || d.language === language) &&
        (!docType || d.doc_type === docType) &&
        (!q || `${d.title} ${d.publisher}`.toLowerCase().includes(q)),
    );
  }, [data, search, state, language, docType, showRetired]);

  const hasFilters = Boolean(search || state || language || docType);

  function clearFilters() {
    setSearch('');
    setState('');
    setLanguage('');
    setDocType('');
  }

  function askAbout(doc: LibraryDocument) {
    navigate(`/?doc=${doc.id}&q=${encodeURIComponent(`What does "${doc.title}" say about `)}`);
  }

  return (
    <>
      <PageHeader
        title={t('pages.library.title')}
        description={t('pages.library.description')}
        icon={<BookOpen className="size-6" aria-hidden />}
      />

      <Notice tone="info" className="mb-6">
        “Ask about this document” limits your next question to that document.
      </Notice>

      <Card padding="sm" className="mb-6">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div className="md:col-span-2 xl:col-span-1">
            <SearchInput
              label={t('common.search')}
              value={search}
              onChange={setSearch}
              placeholder="Title or publisher"
            />
          </div>
          <div>
            <label htmlFor={ids.state} className="field-label">
              State
            </label>
            <select
              id={ids.state}
              className="field-input"
              value={state}
              onChange={(e) => setState(e.target.value)}
            >
              <option value="">{t('common.all')}</option>
              {stateOptions.map((s) => (
                <option key={s} value={s}>
                  {stateName(s)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor={ids.language} className="field-label">
              Language
            </label>
            <select
              id={ids.language}
              className="field-input"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
            >
              <option value="">{t('common.all')}</option>
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor={ids.type} className="field-label">
              Document type
            </label>
            <select
              id={ids.type}
              className="field-input"
              value={docType}
              onChange={(e) => setDocType(e.target.value as DocumentType | '')}
            >
              <option value="">{t('common.all')}</option>
              {DOCUMENT_TYPES.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <label
            htmlFor={ids.retired}
            className="flex min-h-10 cursor-pointer items-center gap-2 text-sm"
          >
            <input
              id={ids.retired}
              type="checkbox"
              checked={showRetired}
              onChange={(e) => setShowRetired(e.target.checked)}
              className="size-4 accent-brand-700"
            />
            Show retired versions
          </label>
          {hasFilters && (
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              {t('common.clearFilters')}
            </Button>
          )}
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
          description="No document matches these filters."
          action={
            <Button variant="secondary" onClick={clearFilters}>
              {t('common.clearFilters')}
            </Button>
          }
        />
      ) : (
        <>
          <p className="mb-3 text-sm text-ink-muted" aria-live="polite">
            {filtered.length} documents
          </p>

          {/* Table from tablet width up */}
          <div className="hidden overflow-x-auto rounded-2xl border border-line bg-surface md:block">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Library documents</caption>
              <thead className="border-b border-line bg-canvas text-xs tracking-wide text-ink-muted uppercase">
                <tr>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Title
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Type
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    State
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Published
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Version
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {filtered.map((doc) => (
                  <tr key={doc.id} className="align-top hover:bg-brand-50/50">
                    <td className="px-4 py-3">
                      <p className="font-semibold text-ink">{doc.title}</p>
                      <p className="text-ink-muted">
                        {doc.publisher} · {languageName(doc.language)}
                      </p>
                      <SourceLink doc={doc} />
                    </td>
                    <td className="px-4 py-3">{documentTypeLabel(doc.doc_type)}</td>
                    <td className="px-4 py-3">{stateName(doc.state)}</td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {doc.published_date
                        ? formatDate(doc.published_date)
                        : t('common.dateNotStated')}
                    </td>
                    <td className="px-4 py-3">
                      <span className="whitespace-nowrap">{doc.version}</span>
                      {doc.status === 'retired' && (
                        <Badge tone="neutral" className="mt-1">
                          Retired
                        </Badge>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button
                        variant="subtle"
                        size="sm"
                        disabled={doc.status === 'retired'}
                        onClick={() => askAbout(doc)}
                        icon={<MessageSquareText className="size-4" aria-hidden />}
                      >
                        Ask
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Cards on phones */}
          <ul className="flex flex-col gap-3 md:hidden">
            {filtered.map((doc) => (
              <li key={doc.id}>
                <Card as="article" padding="sm">
                  <div className="mb-2 flex flex-wrap gap-2">
                    <Badge tone="brand">{documentTypeLabel(doc.doc_type)}</Badge>
                    <Badge>{stateName(doc.state)}</Badge>
                    {doc.status === 'retired' && <Badge>Retired</Badge>}
                  </div>
                  <h2 className="font-semibold">{doc.title}</h2>
                  <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-sm">
                    <dt className="text-ink-muted">Publisher</dt>
                    <dd>{doc.publisher}</dd>
                    <dt className="text-ink-muted">Published</dt>
                    <dd>
                      {doc.published_date
                        ? formatDate(doc.published_date)
                        : t('common.dateNotStated')}
                    </dd>
                    <dt className="text-ink-muted">Version</dt>
                    <dd>{doc.version}</dd>
                    <dt className="text-ink-muted">Language</dt>
                    <dd>{languageName(doc.language)}</dd>
                  </dl>
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                    <SourceLink doc={doc} />
                    <Button
                      variant="subtle"
                      size="sm"
                      disabled={doc.status === 'retired'}
                      onClick={() => askAbout(doc)}
                      icon={<MessageSquareText className="size-4" aria-hidden />}
                    >
                      Ask about this document
                    </Button>
                  </div>
                </Card>
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}

function SourceLink({ doc }: { doc: LibraryDocument }) {
  const { t } = useTranslation();
  if (doc.source_url) {
    return (
      <a
        href={doc.source_url}
        target="_blank"
        rel="noreferrer"
        className="mt-1 inline-flex items-center gap-1 text-sm font-semibold text-brand-800 underline"
      >
        Original document
        <ExternalLink className="size-3.5" aria-hidden />
      </a>
    );
  }
  return (
    <span className="mt-1 inline-flex items-center gap-1 text-sm text-ink-muted">
      <ExternalLink className="size-3.5" aria-hidden />
      {t('common.linkPending')}
    </span>
  );
}
