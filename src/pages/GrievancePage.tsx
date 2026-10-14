import { useId, useRef, useState, type FormEvent } from 'react';
import {
  Check,
  ClipboardList,
  Copy,
  Download,
  Landmark,
  ListChecks,
  Mic,
  RotateCcw,
  Scale,
  SquarePen,
  Wand,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Card, CardTitle } from '@/components/common/Card';
import { LegalNotice, Notice } from '@/components/common/Notice';
import { PageHeader } from '@/components/common/PageHeader';
import { StateSelector } from '@/components/common/StateSelector';
import { GRIEVANCE_CATEGORIES } from '@/data/mockGrievance';
import { useCopyToClipboard } from '@/hooks/useCopyToClipboard';
import { useSettings } from '@/hooks/useSettings';
import { cn, downloadTextFile } from '@/lib/format';
import { api } from '@/services/api';
import type { GrievanceGuide } from '@/types';

const MIN_LENGTH = 20;

const PROCESS = [
  { title: 'Describe', body: 'Tell us what happened, in your own words.' },
  { title: 'Review guidance', body: 'See the forum, steps and documents to collect.' },
  { title: 'Send it yourself', body: 'Edit the draft, then submit it to the office yourself.' },
];

export default function GrievancePage() {
  const { t } = useTranslation();
  const settings = useSettings();
  const descriptionId = useId();

  const [description, setDescription] = useState('');
  const [stateCode, setStateCode] = useState<string | null>(settings.stateCode);
  const [categoryHint, setCategoryHint] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [guide, setGuide] = useState<GrievanceGuide | null>(null);
  const [draft, setDraft] = useState('');
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const resultRef = useRef<HTMLElement>(null);
  const { copied, error: copyError, copy } = useCopyToClipboard();

  const tooShort = description.trim().length < MIN_LENGTH;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (tooShort) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.grievanceGuide({
        description,
        state: stateCode,
        language: settings.language,
        category_hint: categoryHint,
      });
      setGuide(result);
      setDraft(result.draft_text);
      setChecked(new Set());
      requestAnimationFrame(() =>
        resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
      );
    } catch {
      setError('Could not prepare guidance. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setGuide(null);
    setDraft('');
    setDescription('');
    setCategoryHint(null);
    setTouched(false);
  }

  function toggleChecked(index: number) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  return (
    <>
      <PageHeader
        title={t('pages.grievance.title')}
        description={t('pages.grievance.description')}
        icon={<Scale className="size-6" aria-hidden />}
        breadcrumbs={[]}
        badges={
          <Badge tone="saffron">{t('common.demo')}: guidance uses sample forums and steps</Badge>
        }
      />

      <div className="mb-6 flex flex-col gap-3">
        <Notice tone="warning" title="Sahkar Saathi never files a complaint for you">
          This page only helps you prepare. Nothing is sent to any office or stored with your name.
          You decide whether and where to submit the draft.
        </Notice>
        <LegalNotice />
      </div>

      <ol className="mb-6 grid gap-3 sm:grid-cols-3">
        {PROCESS.map((step, i) => (
          <li key={step.title} className="flex gap-3 rounded-2xl border border-line bg-surface p-4">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-saffron-100 font-bold text-saffron-800">
              {i + 1}
            </span>
            <div>
              <p className="font-semibold">{step.title}</p>
              <p className="text-sm text-ink-muted">{step.body}</p>
            </div>
          </li>
        ))}
      </ol>

      <Card as="section" aria-labelledby="describe-heading">
        <CardTitle
          icon={<SquarePen className="size-5" aria-hidden />}
          title={<span id="describe-heading">Describe your problem</span>}
          description="Do not include phone numbers, Aadhaar or account numbers. Add those yourself in the final letter."
        />
        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-5">
          <fieldset>
            <legend className="field-label">Type of problem (optional)</legend>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                aria-pressed={categoryHint === null}
                onClick={() => setCategoryHint(null)}
                className={chipClass(categoryHint === null)}
              >
                Detect from my description
              </button>
              {GRIEVANCE_CATEGORIES.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  aria-pressed={categoryHint === c.id}
                  onClick={() => setCategoryHint(c.id)}
                  title={c.description}
                  className={chipClass(categoryHint === c.id)}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </fieldset>

          <div>
            <label htmlFor={descriptionId} className="field-label">
              What happened?
            </label>
            <textarea
              id={descriptionId}
              rows={5}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              onBlur={() => setTouched(true)}
              aria-invalid={touched && tooShort}
              aria-describedby={`${descriptionId}-help`}
              placeholder="Example: I closed my fixed deposit with our society in March, but the money has not been returned even after two written requests."
              className="field-input"
            />
            <div id={`${descriptionId}-help`} className="flex flex-wrap justify-between gap-2">
              {touched && tooShort ? (
                <p className="field-error">
                  Please write at least {MIN_LENGTH} characters so we can guide you.
                </p>
              ) : (
                <p className="field-hint flex items-center gap-1.5">
                  <Mic className="size-4" aria-hidden />
                  Voice description is planned for Sprint 3. Type for now.
                </p>
              )}
              <p className="field-hint">{description.trim().length} characters</p>
            </div>
          </div>

          <StateSelector
            value={stateCode}
            onChange={setStateCode}
            showHint
            className="sm:max-w-sm"
          />

          {error && (
            <Notice tone="warning" role="alert">
              {error}
            </Notice>
          )}

          <div className="flex flex-wrap gap-2">
            <Button
              type="submit"
              size="lg"
              loading={loading}
              icon={<Wand className="size-5" aria-hidden />}
            >
              Get guidance
            </Button>
            {guide && (
              <Button
                variant="ghost"
                size="lg"
                onClick={reset}
                icon={<RotateCcw className="size-5" aria-hidden />}
              >
                Start again
              </Button>
            )}
          </div>
        </form>
      </Card>

      {guide && (
        <section ref={resultRef} aria-labelledby="result-heading" className="mt-8 scroll-mt-24">
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <h2 id="result-heading" className="text-xl font-bold">
              Your guidance
            </h2>
            <Badge tone="saffron">Sample guidance, not verified</Badge>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardTitle
                icon={<Landmark className="size-5" aria-hidden />}
                title="Where to complain"
                level={3}
              />
              <dl className="flex flex-col gap-3">
                <div>
                  <dt className="text-sm text-ink-muted">Detected category</dt>
                  <dd className="font-semibold">{guide.category.label}</dd>
                </div>
                <div>
                  <dt className="text-sm text-ink-muted">Forum</dt>
                  <dd className="font-semibold">{guide.forum}</dd>
                  <dd className="mt-1 text-sm text-ink-muted">{guide.forum_note}</dd>
                </div>
              </dl>
            </Card>

            <Card>
              <CardTitle
                icon={<ListChecks className="size-5" aria-hidden />}
                title="Steps to follow"
                level={3}
              />
              <ol className="flex flex-col gap-3">
                {guide.steps.map((step, i) => (
                  <li key={step} className="flex gap-3">
                    <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-800 text-sm font-bold text-white">
                      {i + 1}
                    </span>
                    <span>{step}</span>
                  </li>
                ))}
              </ol>
            </Card>

            <Card className="lg:col-span-2">
              <CardTitle
                icon={<ClipboardList className="size-5" aria-hidden />}
                title="Documents checklist"
                description={`Tick what you have. ${checked.size} of ${guide.documents_needed.length} ready. (Not saved.)`}
                level={3}
              />
              <ul className="grid gap-2 sm:grid-cols-2">
                {guide.documents_needed.map((doc, i) => (
                  <li key={doc}>
                    <label className="flex min-h-11 cursor-pointer items-start gap-3 rounded-xl border border-line px-3 py-2.5 hover:bg-brand-50">
                      <input
                        type="checkbox"
                        checked={checked.has(i)}
                        onChange={() => toggleChecked(i)}
                        className="mt-1 size-4 accent-brand-700"
                      />
                      <span className={cn(checked.has(i) && 'text-ink-muted line-through')}>
                        {doc}
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            </Card>

            <Card className="lg:col-span-2">
              <CardTitle
                icon={<SquarePen className="size-5" aria-hidden />}
                title={<label htmlFor="draft">Draft complaint (edit freely)</label>}
                description="Replace everything in [square brackets]. Your edits stay in this browser tab only."
                level={3}
              />
              <textarea
                id="draft"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={16}
                className="field-input font-mono text-sm leading-relaxed"
              />
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Button
                  variant="primary"
                  onClick={() => void copy(draft)}
                  icon={
                    copied ? (
                      <Check className="size-5" aria-hidden />
                    ) : (
                      <Copy className="size-5" aria-hidden />
                    )
                  }
                >
                  {copied ? t('common.copied') : 'Copy draft'}
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => downloadTextFile('grievance-draft.txt', draft)}
                  icon={<Download className="size-5" aria-hidden />}
                >
                  Download as text
                </Button>
                <Button variant="ghost" onClick={() => setDraft(guide.draft_text)}>
                  Restore original draft
                </Button>
                <span role="status" className="text-sm text-red-700">
                  {copyError}
                </span>
              </div>
            </Card>
          </div>
        </section>
      )}
    </>
  );
}

function chipClass(active: boolean) {
  return cn(
    'min-h-10 rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors',
    active
      ? 'border-brand-700 bg-brand-800 text-white'
      : 'border-line bg-surface text-ink-soft hover:border-brand-300 hover:bg-brand-50',
  );
}
