import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CircleQuestionMark,
  Copy,
  Download,
  FileSearch,
  HandCoins,
  Printer,
  RotateCcw,
  SearchX,
  ShieldCheck,
  Sprout,
  UserX,
  Vote,
  Wallet,
  type LucideIcon,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/common/Button';
import { ErrorState, LoadingState } from '@/components/common/EmptyState';
import { Notice } from '@/components/common/Notice';
import { PageHeader } from '@/components/common/PageHeader';
import { SourceMeta } from '@/components/common/SourceMeta';
import { StateSelector } from '@/components/common/StateSelector';
import { ContactText } from '@/components/grievance/ContactText';
import { stateName } from '@/data/options';
import { useAsync } from '@/hooks/useAsync';
import { useCopyToClipboard } from '@/hooks/useCopyToClipboard';
import { useSettings } from '@/hooks/useSettings';
import { cn, downloadTextFile } from '@/lib/format';
import { parseForumNote } from '@/lib/grievance';
import { api, USE_MOCKS } from '@/services/api';
import type { GrievanceCategory, GrievanceGuide } from '@/types';

/** The backend rejects shorter descriptions. */
const MIN_LENGTH = 20;
const STEPS = 3;

const CATEGORY_ICONS: Record<string, LucideIcon> = {
  'deposit-refund': Wallet,
  membership: UserX,
  election: Vote,
  records: FileSearch,
  loan: HandCoins,
  'crop-insurance': Sprout,
};

type Step = 1 | 2 | 3;

export default function GrievancePage() {
  const { t } = useTranslation();
  const settings = useSettings();
  const categories = useAsync(() => api.grievanceCategories());

  const [step, setStep] = useState<Step>(1);
  // undefined: not chosen yet; null: "Not sure", detected from the description.
  const [category, setCategory] = useState<GrievanceCategory | null | undefined>(undefined);
  const [description, setDescription] = useState('');
  const [stateCode, setStateCode] = useState<string | null>(settings.stateCode);
  const [guide, setGuide] = useState<GrievanceGuide | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const firstRender = useRef(true);

  // Move focus to the new step's heading so keyboard and screen reader users follow along.
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    headingRef.current?.focus();
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' });
  }, [step]);

  function chooseCategory(next: GrievanceCategory | null) {
    setCategory(next);
    setStep(2);
  }

  function startOver() {
    setGuide(null);
    setDescription('');
    setCategory(undefined);
    setStep(1);
  }

  const stepTitles: Record<Step, string> = {
    1: t('grievance.step1Title'),
    2: t('grievance.step2Title'),
    3: t('grievance.step3Title'),
  };

  return (
    <div className="mx-auto w-full max-w-4xl">
      <PageHeader
        title={t('pages.grievance.title')}
        description={t('pages.grievance.description')}
      />

      <p className="-mt-4 mb-8 flex items-start gap-2 text-sm text-ink-soft">
        <ShieldCheck className="mt-0.5 size-4 shrink-0 text-brand-700" aria-hidden />
        {t('grievance.neverFiles')}
      </p>

      <StepIndicator step={step} titles={stepTitles} />

      <h2
        ref={headingRef}
        tabIndex={-1}
        className="mt-6 mb-5 text-xl font-semibold tracking-tight outline-none"
      >
        {stepTitles[step]}
      </h2>

      {step === 1 &&
        (categories.loading ? (
          <LoadingState />
        ) : categories.error || !categories.data ? (
          <ErrorState message={t('grievance.categoriesError')} onRetry={categories.reload} />
        ) : (
          <CategoryStep
            categories={categories.data}
            selected={category}
            onChoose={chooseCategory}
          />
        ))}

      {step === 2 && (
        <DetailsStep
          category={category ?? null}
          description={description}
          onDescriptionChange={setDescription}
          stateCode={stateCode}
          onStateChange={setStateCode}
          onBack={() => setStep(1)}
          onResult={(result) => {
            setGuide(result);
            setStep(3);
          }}
        />
      )}

      {step === 3 && guide && (
        <RouteStep
          guide={guide}
          stateCode={stateCode}
          onBack={() => setStep(2)}
          onStartOver={startOver}
        />
      )}

      <p className="mt-10 border-t border-line pt-4 text-sm text-ink-muted">
        {t('grievance.disclaimer')}
      </p>
    </div>
  );
}

/* ----- Step indicator ----- */

function StepIndicator({ step, titles }: { step: Step; titles: Record<Step, string> }) {
  const { t } = useTranslation();
  return (
    <div>
      <p className="text-sm font-medium text-ink-muted">
        {t('grievance.stepOf', { current: step, total: STEPS })}
      </p>
      <ol className="mt-2 grid grid-cols-3 gap-2" aria-label={t('grievance.progress')}>
        {([1, 2, 3] as Step[]).map((n) => (
          <li key={n} aria-current={n === step ? 'step' : undefined}>
            <span
              className={cn('block h-1.5 rounded-full', n <= step ? 'bg-brand-600' : 'bg-line')}
              aria-hidden
            />
            <span
              className={cn(
                'mt-1.5 hidden text-xs sm:block',
                n === step ? 'font-semibold text-ink' : 'text-ink-muted',
              )}
            >
              {titles[n]}
            </span>
            <span className="sr-only sm:hidden">{titles[n]}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

/* ----- Step 1: what is the problem? ----- */

interface CategoryStepProps {
  categories: GrievanceCategory[];
  selected: GrievanceCategory | null | undefined;
  onChoose: (category: GrievanceCategory | null) => void;
}

function CategoryStep({ categories, selected, onChoose }: CategoryStepProps) {
  const { t } = useTranslation();
  return (
    <>
      <p className="-mt-2 mb-5 text-ink-soft">{t('grievance.step1Hint')}</p>
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {categories.map((c) => (
          <li key={c.id}>
            <CategoryCard
              icon={CATEGORY_ICONS[c.id] ?? CircleQuestionMark}
              label={c.label}
              description={c.description}
              active={selected?.id === c.id}
              onClick={() => onChoose(c)}
            />
          </li>
        ))}
        <li>
          <CategoryCard
            icon={CircleQuestionMark}
            label={t('grievance.notSure')}
            description={t('grievance.notSureBody')}
            active={selected === null}
            onClick={() => onChoose(null)}
          />
        </li>
      </ul>
    </>
  );
}

interface CategoryCardProps {
  icon: LucideIcon;
  label: string;
  description: string;
  active: boolean;
  onClick: () => void;
}

function CategoryCard({ icon: Icon, label, description, active, onClick }: CategoryCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'flex h-full min-h-11 w-full items-start gap-3 rounded-2xl border bg-surface p-4 text-left transition-colors hover:border-brand-300 hover:bg-brand-50/50',
        active ? 'border-brand-600 ring-1 ring-brand-600' : 'border-line',
      )}
    >
      <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
        <Icon className="size-5" aria-hidden />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-semibold text-ink">{label}</span>
        <span className="mt-0.5 block text-sm text-ink-muted">{description}</span>
      </span>
      {active && <Check className="size-5 shrink-0 text-brand-700" aria-hidden />}
    </button>
  );
}

/* ----- Step 2: a few details ----- */

interface DetailsStepProps {
  category: GrievanceCategory | null;
  description: string;
  onDescriptionChange: (value: string) => void;
  stateCode: string | null;
  onStateChange: (code: string | null) => void;
  onBack: () => void;
  onResult: (guide: GrievanceGuide) => void;
}

function DetailsStep({
  category,
  description,
  onDescriptionChange,
  stateCode,
  onStateChange,
  onBack,
  onResult,
}: DetailsStepProps) {
  const { t } = useTranslation();
  const { language } = useSettings();
  const id = useId();
  const [touched, setTouched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const length = description.trim().length;
  const tooShort = length < MIN_LENGTH;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (tooShort) return;
    setLoading(true);
    setError(false);
    try {
      onResult(
        await api.grievanceGuide({
          description,
          state: stateCode,
          language,
          category_hint: category?.id ?? null,
        }),
      );
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-6">
      <p className="text-sm text-ink-soft">
        <span className="text-ink-muted">{t('grievance.problemLabel')}:</span>{' '}
        <span className="font-semibold text-ink">{category?.label ?? t('grievance.notSure')}</span>
      </p>

      <div>
        <label htmlFor={id} className="field-label">
          {t('grievance.describeLabel')}
        </label>
        <textarea
          id={id}
          rows={5}
          value={description}
          onChange={(e) => onDescriptionChange(e.target.value)}
          onBlur={() => setTouched(true)}
          aria-invalid={touched && tooShort}
          aria-describedby={`${id}-help`}
          placeholder={t('grievance.describePlaceholder')}
          className="field-input"
        />
        <div id={`${id}-help`} className="flex flex-wrap justify-between gap-x-4">
          {touched && tooShort ? (
            <p className="field-error">{t('grievance.tooShort', { min: MIN_LENGTH })}</p>
          ) : (
            <p className="field-hint">{t('grievance.describeHint')}</p>
          )}
          <p className="field-hint">{t('grievance.charCount', { count: length })}</p>
        </div>
      </div>

      <StateSelector value={stateCode} onChange={onStateChange} showHint className="sm:max-w-sm" />

      {error && (
        <Notice tone="warning" role="alert">
          {t('grievance.guideError')}
        </Notice>
      )}

      <div className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          onClick={onBack}
          icon={<ArrowLeft className="size-4" aria-hidden />}
        >
          {t('grievance.back')}
        </Button>
        <Button type="submit" loading={loading}>
          {t('grievance.showRoute')}
          {!loading && <ArrowRight className="size-4" aria-hidden />}
        </Button>
      </div>
    </form>
  );
}

/* ----- Step 3: where to go ----- */

interface RouteStepProps {
  guide: GrievanceGuide;
  stateCode: string | null;
  onBack: () => void;
  onStartOver: () => void;
}

function RouteStep({ guide, stateCode, onBack, onStartOver }: RouteStepProps) {
  const { t } = useTranslation();
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [draft, setDraft] = useState(guide.draft_text);
  const summaryCopy = useCopyToClipboard();
  const draftCopy = useCopyToClipboard();
  const note = parseForumNote(guide.forum_note);
  // With the real API, a demo guide means no verified route is recorded for this category.
  const noRoute = !USE_MOCKS && guide.is_demo;

  function toggle(index: number) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  function summary(): string {
    const lines = [
      `${t('pages.grievance.title')}: ${guide.category.label}`,
      stateCode ? `${t('settings.state')}: ${stateName(stateCode)}` : null,
      '',
      `${noRoute ? t('grievance.contactInstead') : t('grievance.startHere')}: ${guide.forum}`,
      guide.forum_note,
      '',
      `${t('grievance.stepsTitle')}:`,
      ...guide.steps.map((s, i) => `${i + 1}. ${s}`),
    ];
    if (guide.documents_needed.length > 0) {
      lines.push(
        '',
        `${t('grievance.checklistTitle')}:`,
        ...guide.documents_needed.map((d) => `- ${d}`),
      );
    }
    lines.push('', t('grievance.disclaimer'));
    return lines.filter((line) => line !== null).join('\n');
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="-mt-2 flex flex-wrap items-center gap-2 text-sm text-ink-soft">
        <span className="text-ink-muted">{t('grievance.problemLabel')}:</span>
        <span className="font-semibold text-ink">{guide.category.label}</span>
      </div>

      {noRoute ? (
        <section
          aria-labelledby="no-route"
          className="rounded-2xl border border-line bg-surface p-5 sm:p-6"
        >
          <h3 id="no-route" className="flex items-center gap-2 font-semibold">
            <SearchX className="size-5 text-ink-muted" aria-hidden />
            {t('grievance.noRouteTitle')}
          </h3>
          <p className="mt-1 text-ink-soft">{t('grievance.noRouteBody')}</p>
          <p className="mt-4 text-sm font-semibold text-ink-muted">
            {t('grievance.contactInstead')}
          </p>
          <p className="font-semibold">{guide.forum}</p>
          <ContactText text={guide.forum_note} className="mt-1 text-sm text-ink-soft" />
        </section>
      ) : (
        <ol aria-label={t('grievance.step3Title')}>
          <Rung label={t('grievance.startHere')} last>
            <h3 className="text-lg font-semibold">{guide.forum}</h3>
            {note.text && <ContactText text={note.text} className="mt-1 text-ink-soft" />}
            {note.sourceUrl && (
              <div className="mt-3">
                <SourceMeta
                  sourceLabel={note.sourceUrl}
                  sourceUrl={note.sourceUrl}
                  asOf={note.asOf}
                />
              </div>
            )}
          </Rung>
        </ol>
      )}

      <section aria-labelledby="steps-title">
        <h3 id="steps-title" className="mb-3 font-semibold">
          {t('grievance.stepsTitle')}
        </h3>
        <ol className="flex flex-col gap-3">
          {guide.steps.map((s, i) => (
            <li key={s} className="flex gap-3">
              <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-semibold text-brand-800 ring-1 ring-brand-200">
                {i + 1}
              </span>
              <ContactText text={s} className="text-ink-soft" />
            </li>
          ))}
        </ol>
      </section>

      {guide.documents_needed.length > 0 && (
        <section aria-labelledby="checklist-title">
          <h3 id="checklist-title" className="font-semibold">
            {t('grievance.checklistTitle')}
          </h3>
          <p className="mb-3 text-sm text-ink-muted">
            {t('grievance.checklistProgress', {
              done: checked.size,
              total: guide.documents_needed.length,
            })}
          </p>
          <ul className="grid gap-2 sm:grid-cols-2">
            {guide.documents_needed.map((doc, i) => (
              <li key={doc}>
                <label className="flex min-h-11 cursor-pointer items-start gap-3 rounded-xl border border-line bg-surface px-3 py-2.5 hover:bg-subtle">
                  <input
                    type="checkbox"
                    checked={checked.has(i)}
                    onChange={() => toggle(i)}
                    className="mt-1 size-4 accent-brand-700"
                  />
                  <span className={cn(checked.has(i) && 'text-ink-muted line-through')}>{doc}</span>
                </label>
              </li>
            ))}
          </ul>
        </section>
      )}

      <details className="group rounded-2xl border border-line bg-surface print:hidden">
        <summary className="flex min-h-11 cursor-pointer items-center justify-between gap-2 rounded-2xl px-4 py-3 font-semibold hover:bg-subtle">
          {t('grievance.draftTitle')}
          <ArrowRight
            className="size-4 text-ink-muted transition-transform group-open:rotate-90"
            aria-hidden
          />
        </summary>
        <div className="border-t border-line px-4 py-4">
          <label htmlFor="draft" className="field-hint mt-0 mb-2 block">
            {t('grievance.draftHint')}
          </label>
          <textarea
            id="draft"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={14}
            className="field-input font-mono text-sm leading-relaxed"
          />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void draftCopy.copy(draft)}
              icon={
                draftCopy.copied ? (
                  <Check className="size-4" aria-hidden />
                ) : (
                  <Copy className="size-4" aria-hidden />
                )
              }
            >
              {draftCopy.copied ? t('common.copied') : t('grievance.copyDraft')}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => downloadTextFile('grievance-draft.txt', draft)}
              icon={<Download className="size-4" aria-hidden />}
            >
              {t('common.download')}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setDraft(guide.draft_text)}>
              {t('grievance.restoreDraft')}
            </Button>
            <span role="status" className="text-sm text-red-700">
              {draftCopy.error}
            </span>
          </div>
        </div>
      </details>

      <div className="flex flex-wrap items-center gap-2 print:hidden">
        <Button
          onClick={() => void summaryCopy.copy(summary())}
          icon={
            summaryCopy.copied ? (
              <Check className="size-4" aria-hidden />
            ) : (
              <Copy className="size-4" aria-hidden />
            )
          }
        >
          {summaryCopy.copied ? t('common.copied') : t('grievance.copySummary')}
        </Button>
        <Button
          variant="secondary"
          onClick={() => window.print()}
          icon={<Printer className="size-4" aria-hidden />}
        >
          {t('grievance.print')}
        </Button>
        <Button
          variant="ghost"
          onClick={onBack}
          icon={<ArrowLeft className="size-4" aria-hidden />}
        >
          {t('grievance.back')}
        </Button>
        <Button
          variant="ghost"
          onClick={onStartOver}
          icon={<RotateCcw className="size-4" aria-hidden />}
        >
          {t('grievance.startOver')}
        </Button>
        <span role="status" className="text-sm text-red-700">
          {summaryCopy.error}
        </span>
      </div>
    </div>
  );
}

/** One rung of the route ladder: a label, then its content, joined by a line to the next rung. */
function Rung({ label, last, children }: { label: string; last?: boolean; children: ReactNode }) {
  return (
    <li className="relative flex gap-4">
      <div className="flex flex-col items-center" aria-hidden>
        <span className="mt-1 size-3 rounded-full bg-brand-600 ring-4 ring-brand-100" />
        {!last && <span className="mt-1 w-px flex-1 bg-line" />}
      </div>
      <div className="min-w-0 flex-1 rounded-2xl border border-line bg-surface p-5 sm:p-6">
        <p className="mb-1 text-xs font-semibold tracking-wide text-brand-700 uppercase">{label}</p>
        {children}
      </div>
    </li>
  );
}
