import { useState } from 'react';
import {
  ArrowLeft,
  CircleCheck,
  CircleX,
  Clock,
  CreditCard,
  GraduationCap,
  PiggyBank,
  ShieldAlert,
  Wallet,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Card, CardTitle } from '@/components/common/Card';
import { EmptyState, ErrorState, LoadingState } from '@/components/common/EmptyState';
import { Notice } from '@/components/common/Notice';
import { PageHeader } from '@/components/common/PageHeader';

import { useAsync } from '@/hooks/useAsync';
import { cn } from '@/lib/format';
import { api } from '@/services/api';
import type { Lesson, LessonIcon, QuizQuestion } from '@/types';

const ICONS: Record<LessonIcon, typeof Wallet> = {
  loan: Wallet,
  card: CreditCard,
  savings: PiggyBank,
  fraud: ShieldAlert,
};

export default function FinancialLiteracyPage() {
  const { t } = useTranslation();
  const { data, loading, error, reload } = useAsync((signal) => api.listLessons(undefined, signal));
  const [openSlug, setOpenSlug] = useState<string | null>(null);
  const openLesson = data?.lessons.find((l) => l.slug === openSlug) ?? null;

  return (
    <>
      <PageHeader
        title={t('pages.learn.title')}
        description={t('pages.learn.description')}
        icon={<GraduationCap className="size-6" aria-hidden />}
        breadcrumbs={[{ label: t('nav.groups.guides') }]}
        badges={<Badge tone="blue">Introductory learning material</Badge>}
      />

      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : openLesson ? (
        <LessonDetail lesson={openLesson} onBack={() => setOpenSlug(null)} />
      ) : data?.lessons.length === 0 ? (
        <EmptyState title={t('common.noResults')} />
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2">
          {(data?.lessons ?? []).map((lesson) => {
            const Icon = ICONS[lesson.icon];
            return (
              <li key={lesson.slug}>
                <Card as="article" className="flex h-full flex-col">
                  <div className="mb-3 flex items-center justify-between">
                    <span className="flex size-12 items-center justify-center rounded-2xl bg-saffron-50 text-saffron-700 ring-1 ring-saffron-200">
                      <Icon className="size-6" aria-hidden />
                    </span>
                    <span className="flex items-center gap-1 text-sm text-ink-muted">
                      <Clock className="size-4" aria-hidden />
                      {lesson.reading_minutes} min read
                    </span>
                  </div>
                  <h2 className="text-lg font-semibold">{lesson.title}</h2>
                  <p className="mt-1 flex-1 text-ink-soft">{lesson.summary}</p>
                  <Button
                    variant="secondary"
                    className="mt-4 self-start"
                    onClick={() => setOpenSlug(lesson.slug)}
                  >
                    Read lesson
                  </Button>
                </Card>
              </li>
            );
          })}
        </ul>
      )}

      {data && data.quiz.length > 0 && <Quiz questions={data.quiz} />}
    </>
  );
}

function LessonDetail({ lesson, onBack }: { lesson: Lesson; onBack: () => void }) {
  const Icon = ICONS[lesson.icon];
  return (
    <Card as="article" aria-labelledby="lesson-title">
      <Button
        variant="ghost"
        size="sm"
        onClick={onBack}
        icon={<ArrowLeft className="size-4" aria-hidden />}
      >
        All lessons
      </Button>
      <div className="mt-3 flex items-start gap-3">
        <span className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-saffron-50 text-saffron-700 ring-1 ring-saffron-200">
          <Icon className="size-6" aria-hidden />
        </span>
        <div>
          <h2 id="lesson-title" className="text-2xl font-bold">
            {lesson.title}
          </h2>
          <p className="text-sm text-ink-muted">
            {lesson.reading_minutes} min read · Introductory learning material
          </p>
        </div>
      </div>
      <div className="mt-6 grid gap-8 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="flex max-w-prose flex-col gap-5">
          {lesson.sections.map((section) => (
            <section key={section.heading}>
              <h3 className="text-lg font-semibold">{section.heading}</h3>
              <p className="mt-1 text-ink-soft">{section.body}</p>
            </section>
          ))}
        </div>
        <aside className="self-start rounded-2xl bg-brand-50 p-4 ring-1 ring-brand-100">
          <h3 className="font-semibold text-brand-900">Remember</h3>
          <ul className="mt-2 flex flex-col gap-2">
            {lesson.key_points.map((point) => (
              <li key={point} className="flex gap-2 text-sm">
                <CircleCheck className="mt-0.5 size-4 shrink-0 text-brand-700" aria-hidden />
                {point}
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </Card>
  );
}

function Quiz({ questions }: { questions: QuizQuestion[] }) {
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [submitted, setSubmitted] = useState(false);
  const score = questions.filter((q) => answers[q.id] === q.correct_index).length;
  const allAnswered = questions.every((q) => answers[q.id] !== undefined);

  function reset() {
    setAnswers({});
    setSubmitted(false);
  }

  return (
    <Card as="section" aria-labelledby="quiz-heading" className="mt-8">
      <CardTitle
        icon={<GraduationCap className="size-5" aria-hidden />}
        title={<span id="quiz-heading">Quick quiz (optional)</span>}
        description="Three questions to check what you learned. Nothing is recorded."
      />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (allAnswered) setSubmitted(true);
        }}
        className="flex flex-col gap-6"
      >
        {questions.map((q, qi) => {
          const chosen = answers[q.id];
          const correct = chosen === q.correct_index;
          return (
            <fieldset key={q.id}>
              <legend className="mb-2 font-semibold">
                {qi + 1}. {q.question}
              </legend>
              <div className="flex flex-col gap-2">
                {q.options.map((option, oi) => {
                  const isChosen = chosen === oi;
                  const isRight = oi === q.correct_index;
                  return (
                    <label
                      key={option}
                      className={cn(
                        'flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border px-3 py-2',
                        !submitted &&
                          (isChosen
                            ? 'border-brand-600 bg-brand-50'
                            : 'border-line hover:bg-canvas'),
                        submitted && isRight && 'border-brand-600 bg-brand-50',
                        submitted && isChosen && !isRight && 'border-red-300 bg-red-50',
                        submitted && !isChosen && !isRight && 'border-line opacity-70',
                        submitted && 'cursor-default',
                      )}
                    >
                      <input
                        type="radio"
                        name={q.id}
                        checked={isChosen}
                        disabled={submitted}
                        onChange={() => setAnswers((prev) => ({ ...prev, [q.id]: oi }))}
                        className="size-4 accent-brand-700"
                      />
                      <span className="flex-1">{option}</span>
                      {submitted && isRight && (
                        <CircleCheck
                          className="size-5 text-brand-700"
                          aria-label="Correct answer"
                        />
                      )}
                      {submitted && isChosen && !isRight && (
                        <CircleX
                          className="size-5 text-red-700"
                          aria-label="Your answer, incorrect"
                        />
                      )}
                    </label>
                  );
                })}
              </div>
              {submitted && (
                <p className={cn('mt-2 text-sm', correct ? 'text-brand-800' : 'text-red-800')}>
                  {correct ? 'Correct. ' : 'Not quite. '}
                  {q.explanation}
                </p>
              )}
            </fieldset>
          );
        })}

        {submitted ? (
          <div className="flex flex-col items-start gap-3">
            <Notice
              tone={score === questions.length ? 'success' : 'info'}
              role="status"
              title={`You scored ${score} out of ${questions.length}`}
            >
              {score === questions.length
                ? 'Well done!'
                : 'Read the lessons again and try once more.'}
            </Notice>
            <Button variant="secondary" onClick={reset}>
              Try again
            </Button>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" disabled={!allAnswered}>
              Check my answers
            </Button>
            {!allAnswered && (
              <span className="text-sm text-ink-muted">Answer all three questions to check.</span>
            )}
          </div>
        )}
      </form>
    </Card>
  );
}
