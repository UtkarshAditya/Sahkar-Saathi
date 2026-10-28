import { ArrowRight, Sprout, Landmark, Scale, BookOpen } from 'lucide-react';
import type { QuestionTopic, SuggestedQuestion } from '@/types';
import { cn } from '@/lib/format';

const TOPIC_ICONS: Record<QuestionTopic, typeof Scale> = {
  law: BookOpen,
  pmfby: Sprout,
  schemes: Landmark,
  grievance: Scale,
};

interface SuggestedQuestionsProps {
  title: string;
  /** Full suggestions (with topic icons) or plain follow-up strings. */
  questions: SuggestedQuestion[] | string[];
  onSelect: (text: string) => void;
  disabled?: boolean;
  variant?: 'list' | 'chips';
}

export function SuggestedQuestions({
  title,
  questions,
  onSelect,
  disabled,
  variant = 'list',
}: SuggestedQuestionsProps) {
  if (questions.length === 0) return null;
  const items = questions.map((q, i) =>
    typeof q === 'string' ? { id: `f-${i}`, text: q, topic: null } : q,
  );

  return (
    <div>
      <p className="mb-2 text-sm font-semibold text-ink-soft">{title}</p>
      <ul
        className={cn(
          'min-w-0',
          variant === 'chips' ? 'flex flex-wrap gap-2' : 'grid gap-2 sm:grid-cols-2',
        )}
      >
        {items.map((q) => {
          const Icon = q.topic ? TOPIC_ICONS[q.topic] : ArrowRight;
          return (
            <li key={q.id} className="min-w-0">
              <button
                type="button"
                disabled={disabled}
                onClick={() => onSelect(q.text)}
                className={cn(
                  'flex min-w-0 w-full items-start gap-2 text-left text-sm font-medium transition-colors disabled:opacity-50',
                  variant === 'chips'
                    ? 'rounded-full border border-brand-200 bg-surface px-3 py-1.5 text-brand-800 hover:bg-brand-50'
                    : 'h-full rounded-xl border border-line bg-surface px-3 py-2.5 text-ink hover:border-brand-300 hover:bg-brand-50',
                )}
              >
                <Icon
                  className={cn(
                    'mt-0.5 size-4 shrink-0',
                    variant === 'chips' ? 'hidden' : 'text-brand-700',
                  )}
                  aria-hidden
                />
                <span className="[overflow-wrap:anywhere]">{q.text}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
