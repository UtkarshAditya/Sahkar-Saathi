import { useState } from 'react';
import { ThumbsDown, ThumbsUp } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/common/Button';
import { cn } from '@/lib/format';
import { api } from '@/services/api';
import type { FeedbackRating } from '@/types';

const REASONS = [
  'Wrong information',
  'Not clear',
  'Missing or wrong source',
  'Wrong state',
  'Other',
];

/** Thumbs up/down with a reason on "down". Mock mode keeps the rating on screen only. */
export function FeedbackButtons({ messageId }: { messageId: string }) {
  const { t } = useTranslation();
  const [rating, setRating] = useState<FeedbackRating | null>(null);
  const [reason, setReason] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [sending, setSending] = useState(false);

  async function submit(r: FeedbackRating, why: string | null) {
    setSending(true);
    try {
      await api.sendFeedback({
        message_id: messageId,
        rating: r,
        comment: '',
        reason: why ?? undefined,
      });
      setSent(true);
    } finally {
      setSending(false);
    }
  }

  function choose(r: FeedbackRating) {
    if (sent) return;
    setRating(r);
    if (r === 'up') void submit(r, null);
  }

  const toggle = (active: boolean) =>
    cn(
      'flex size-10 items-center justify-center rounded-lg border transition-colors disabled:cursor-default',
      active
        ? 'border-brand-700 bg-brand-800 text-white'
        : 'border-line bg-surface text-ink-soft hover:bg-brand-50 hover:text-brand-800',
    );

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <span className="text-sm text-ink-muted">{t('feedback.question')}</span>
        <button
          type="button"
          className={toggle(rating === 'up')}
          aria-pressed={rating === 'up'}
          aria-label={t('feedback.helpful')}
          disabled={sent}
          onClick={() => choose('up')}
        >
          <ThumbsUp className="size-4" aria-hidden />
        </button>
        <button
          type="button"
          className={toggle(rating === 'down')}
          aria-pressed={rating === 'down'}
          aria-label={t('feedback.notHelpful')}
          disabled={sent}
          onClick={() => choose('down')}
        >
          <ThumbsDown className="size-4" aria-hidden />
        </button>
      </div>

      {rating === 'down' && !sent && (
        <fieldset className="rounded-xl border border-line bg-canvas p-3">
          <legend className="px-1 text-sm font-semibold">{t('feedback.reasonPrompt')}</legend>
          <div className="flex flex-wrap gap-2">
            {REASONS.map((r) => (
              <button
                key={r}
                type="button"
                aria-pressed={reason === r}
                onClick={() => setReason(r)}
                className={cn(
                  'rounded-full border px-3 py-1 text-sm',
                  reason === r
                    ? 'border-brand-700 bg-brand-800 text-white'
                    : 'border-line bg-surface hover:bg-brand-50',
                )}
              >
                {r}
              </button>
            ))}
          </div>
          <Button
            size="sm"
            className="mt-3"
            disabled={!reason}
            loading={sending}
            onClick={() => void submit('down', reason)}
          >
            Send feedback
          </Button>
        </fieldset>
      )}

      {sent && (
        <p role="status" className="text-sm text-brand-800">
          {t('feedback.thanks')}
        </p>
      )}
    </div>
  );
}
