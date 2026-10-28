import { ChartColumn, CircleCheck, Lock, TriangleAlert } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge, type BadgeTone } from '@/components/common/Badge';
import { ButtonLink } from '@/components/common/Button';
import { Card, CardTitle } from '@/components/common/Card';
import { EmptyState, ErrorState, LoadingState } from '@/components/common/EmptyState';
import { PageHeader } from '@/components/common/PageHeader';
import { useAsync } from '@/hooks/useAsync';
import { LANGUAGES } from '@/i18n';
import { formatDate, formatPercent } from '@/lib/format';
import { ApiError, api } from '@/services/api';
import type { EvalMetric, EvalMetricKey, EvalRun, FailureKind } from '@/types';

/** Django's admin login, which returns here afterwards. The session cookie is what the API checks. */
const STAFF_LOGIN = '/admin/login/?next=/staff/quality';

/** What the page shows when GET /eval/latest answers 401 (not logged in) or 403 (not staff). */
function AccessState({ code }: { code: string }) {
  const signedIn = code === 'staff_only';
  return (
    <EmptyState
      icon={<Lock className="size-6" aria-hidden />}
      title={signedIn ? 'This page is for staff only' : 'Log in as staff to see this page'}
      description={
        signedIn
          ? 'You are logged in, but your account does not have staff access. Log in with a staff account, or ask an administrator.'
          : 'The quality numbers are visible to staff only. Log in on the admin site, and you will come back here.'
      }
      action={
        <ButtonLink to={STAFF_LOGIN} reloadDocument variant="primary">
          {signedIn ? 'Log in with a staff account' : 'Log in as staff'}
        </ButtonLink>
      }
    />
  );
}

const FAILURE_LABELS: Record<FailureKind, { label: string; tone: BadgeTone }> = {
  'retrieval-miss': { label: 'Retrieval miss', tone: 'blue' },
  unfaithful: { label: 'Unsupported claim', tone: 'red' },
  'should-decline': { label: 'Should have declined', tone: 'saffron' },
  'wrong-state': { label: 'Wrong state', tone: 'neutral' },
};

export default function QualityDashboardPage() {
  const { t } = useTranslation();
  const { data, loading, error, reload } = useAsync((signal) => api.latestEval(signal));

  return (
    <>
      <PageHeader
        title={t('pages.quality.title')}
        description={t('pages.quality.description')}
        icon={<ChartColumn className="size-6" aria-hidden />}
        breadcrumbs={[{ label: t('nav.groups.staff') }]}
        badges={
          <Badge tone="neutral" icon={<Lock className="size-3" aria-hidden />}>
            Staff only
          </Badge>
        }
      />

      {loading ? (
        <LoadingState />
      ) : error instanceof ApiError &&
        (error.code === 'not_authenticated' || error.code === 'staff_only') ? (
        <AccessState code={error.code} />
      ) : error || !data ? (
        <ErrorState error={error} onRetry={reload} />
      ) : (
        <div className="flex flex-col gap-6">
          <section aria-labelledby="latest-heading">
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="latest-heading" className="text-lg font-semibold">
                Latest run
              </h2>
              <p className="text-sm text-ink-muted">
                {data.latest.label} · {formatDate(data.latest.run_at)} · {data.latest.questions}{' '}
                questions
              </p>
            </div>
            {data.metrics.length === 0 ? (
              <EmptyState title={t('common.noResults')} />
            ) : (
              <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {data.metrics.map((metric) => (
                  <li key={metric.key}>
                    <MetricTile metric={metric} />
                  </li>
                ))}
                <li>
                  <Card className="h-full">
                    <p className="text-sm font-semibold text-ink-soft">Failed questions</p>
                    <p className="mt-1 text-4xl font-bold tracking-tight">
                      {data.failed_questions.length}
                    </p>
                    <p className="mt-2 text-sm text-ink-muted">
                      Listed below with the reason, for prompt and data fixes.
                    </p>
                  </Card>
                </li>
              </ul>
            )}
          </section>

          <Card as="section" aria-labelledby="trend-heading">
            <CardTitle
              icon={<ChartColumn className="size-5" aria-hidden />}
              title={<span id="trend-heading">Change across runs</span>}
              description="Each bar is one evaluation run. The dashed line is the team target."
            />
            {data.runs.length === 0 ? (
              <EmptyState title={t('common.noResults')} />
            ) : (
              <div className="grid gap-6 md:grid-cols-3">
                {data.metrics.map((metric) => (
                  <RunBars key={metric.key} metric={metric} runs={data.runs} />
                ))}
              </div>
            )}
          </Card>

          <Card as="section" padding="none" aria-labelledby="runs-heading">
            <div className="px-5 pt-5">
              <h2 id="runs-heading" className="text-lg font-semibold">
                Recent evaluation runs
              </h2>
              <p className="text-sm text-ink-muted">
                Each run records its settings so results can be compared.
              </p>
            </div>
            {data.runs.length === 0 ? (
              <div className="m-5">
                <EmptyState title={t('common.noResults')} />
              </div>
            ) : (
              <div className="mt-4 overflow-x-auto">
                <table className="w-full min-w-[44rem] text-left text-sm">
                  <thead className="border-y border-line bg-canvas text-xs tracking-wide text-ink-muted uppercase">
                    <tr>
                      <th scope="col" className="px-5 py-2.5 font-semibold">
                        Run
                      </th>
                      <th scope="col" className="px-3 py-2.5 font-semibold">
                        Settings
                      </th>
                      <th scope="col" className="px-3 py-2.5 text-right font-semibold">
                        Hit rate
                      </th>
                      <th scope="col" className="px-3 py-2.5 text-right font-semibold">
                        Faithfulness
                      </th>
                      <th scope="col" className="px-5 py-2.5 text-right font-semibold">
                        Refusal
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {[...data.runs].reverse().map((run) => (
                      <tr key={run.id}>
                        <td className="px-5 py-3">
                          <p className="font-semibold">{run.label}</p>
                          <p className="text-ink-muted">{formatDate(run.run_at)}</p>
                        </td>
                        <td className="px-3 py-3 text-ink-soft">
                          {run.config.embedding_model} · {run.config.llm} · top-k {run.config.top_k}{' '}
                          · threshold {run.config.threshold} · prompt {run.config.prompt_version}
                        </td>
                        <td className="px-3 py-3 text-right tabular-nums">
                          {formatPercent(run.hit_rate)}
                        </td>
                        <td className="px-3 py-3 text-right tabular-nums">
                          {formatPercent(run.faithfulness)}
                        </td>
                        <td className="px-5 py-3 text-right tabular-nums">
                          {formatPercent(run.correct_refusal)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card as="section" padding="none" aria-labelledby="failed-heading">
            <div className="px-5 pt-5">
              <h2 id="failed-heading" className="text-lg font-semibold">
                Failed questions (latest run)
              </h2>
            </div>
            {data.failed_questions.length === 0 && (
              <p className="px-5 pt-3 pb-5 text-ink-muted">
                No failed questions in the latest run.
              </p>
            )}
            <ul className="mt-3 divide-y divide-line border-t border-line">
              {data.failed_questions.map((fq) => {
                const failure = FAILURE_LABELS[fq.failure];
                return (
                  <li
                    key={fq.id}
                    className="flex flex-col gap-1 px-5 py-3 sm:flex-row sm:items-start sm:gap-4"
                  >
                    <div className="flex shrink-0 gap-2 sm:w-52">
                      <Badge tone={failure.tone}>{failure.label}</Badge>
                      <Badge>
                        {LANGUAGES.find((l) => l.code === fq.language)?.englishLabel ?? fq.language}
                      </Badge>
                    </div>
                    <div>
                      <p className="font-medium">{fq.question}</p>
                      <p className="text-sm text-ink-muted">{fq.note}</p>
                    </div>
                  </li>
                );
              })}
            </ul>
          </Card>
        </div>
      )}
    </>
  );
}

function MetricTile({ metric }: { metric: EvalMetric }) {
  const meets = metric.value >= metric.target;
  return (
    <Card className="h-full">
      <p className="text-sm font-semibold text-ink-soft">{metric.label}</p>
      <p className="mt-1 text-4xl font-bold tracking-tight tabular-nums">
        {formatPercent(metric.value)}
      </p>
      <div
        className="relative mt-3 h-2 rounded-full bg-stone-200"
        role="img"
        aria-label={`${formatPercent(metric.value)} against a target of ${formatPercent(metric.target)}`}
      >
        <div
          className="h-2 rounded-full bg-brand-600"
          style={{ width: `${metric.value * 100}%` }}
        />
        <div
          className="absolute -top-1 h-4 w-0.5 bg-ink"
          style={{ left: `${metric.target * 100}%` }}
        />
      </div>
      <p className="mt-2 flex items-center gap-1.5 text-sm">
        {meets ? (
          <CircleCheck className="size-4 text-brand-700" aria-hidden />
        ) : (
          <TriangleAlert className="size-4 text-saffron-600" aria-hidden />
        )}
        <span className="font-semibold">{meets ? 'Meets target' : 'Below target'}</span>
        <span className="text-ink-muted">· target {formatPercent(metric.target)}</span>
      </p>
      <p className="mt-2 text-sm text-ink-muted">{metric.description}</p>
    </Card>
  );
}

const RUN_KEY: Record<
  EvalMetricKey,
  keyof Pick<EvalRun, 'hit_rate' | 'faithfulness' | 'correct_refusal'>
> = {
  hit_rate: 'hit_rate',
  faithfulness: 'faithfulness',
  correct_refusal: 'correct_refusal',
};

/** Single-series column chart (one hue) with a target line. Values are labelled directly. */
function RunBars({ metric, runs }: { metric: EvalMetric; runs: EvalRun[] }) {
  const height = 140;
  return (
    <figure>
      <figcaption className="mb-2 text-sm font-semibold">{metric.label}</figcaption>
      <div className="relative border-b border-line" style={{ height }}>
        {/* Target line */}
        <div
          className="absolute inset-x-0 border-t-2 border-dashed border-ink-muted"
          style={{ bottom: metric.target * height }}
          aria-hidden
        >
          <span className="absolute -top-5 right-0 bg-surface px-1 text-xs text-ink-muted">
            target {formatPercent(metric.target)}
          </span>
        </div>
        <ul className="absolute inset-0 flex items-end justify-around gap-2 px-2">
          {runs.map((run, i) => {
            const value = run[RUN_KEY[metric.key]];
            return (
              <li
                key={run.id}
                className="group relative flex h-full w-full max-w-12 flex-col justify-end"
                tabIndex={0}
                aria-label={`${run.label}: ${formatPercent(value)}`}
              >
                <span className="mb-1 text-center text-xs font-semibold tabular-nums text-ink-soft">
                  {formatPercent(value)}
                </span>
                <span
                  className="block rounded-t bg-brand-600 transition-colors group-hover:bg-brand-800 group-focus:bg-brand-800"
                  style={{ height: value * (height - 20) }}
                />
                <span
                  role="tooltip"
                  className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 hidden -translate-x-1/2 rounded-lg bg-ink px-2 py-1 text-xs whitespace-nowrap text-white group-hover:block group-focus:block"
                >
                  Run {i + 1} · {formatPercent(value)}
                </span>
              </li>
            );
          })}
        </ul>
      </div>
      <div className="mt-1 flex justify-around px-2 text-xs text-ink-muted" aria-hidden>
        {runs.map((run, i) => (
          <span key={run.id}>Run {i + 1}</span>
        ))}
      </div>
    </figure>
  );
}
