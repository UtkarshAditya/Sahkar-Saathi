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

interface FeedbackButtonsProps {
  messageId: string;
  /** Example answers exist only in the browser, so their ratings are not sent. */
  localOnly?: boolean;
  compact?: boolean;
}

/** Thumbs up/down with a reason on "down". Sent to POST /feedback. */
export function FeedbackButtons({
  messageId,
  localOnly = false,
  compact = false,
}: FeedbackButtonsProps) {
  const { t } = useTranslation();
  const [rating, setRating] = useState<FeedbackRating | null>(null);
  const [reason, setReason] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(false);

  async function submit(r: FeedbackRating, why: string | null) {
    setSending(true);
    setError(false);
    try {
      if (!localOnly) {
        await api.sendFeedback({
          message_id: messageId,
          rating: r,
          comment: '',
          reason: why ?? undefined,
        });
      }
      setSent(true);
    } catch {
      setError(true);
    } finally {
      setSending(false);
    }
  }

  function choose(r: FeedbackRating) {
    if (sent || sending) return;
    setRating(r);
    if (r === 'up') void submit(r, null);
  }

  const toggle = (active: boolean) =>
    cn(
      'flex size-12 items-center justify-center rounded-lg border transition-colors disabled:cursor-default',
      active
        ? 'border-brand-700 bg-brand-800 text-white'
        : 'border-line bg-surface text-ink-soft hover:bg-brand-50 hover:text-brand-800',
    );

  return (
    <div
      className={compact ? 'flex flex-wrap items-center gap-x-2 gap-y-1' : 'flex flex-col gap-2'}
    >
      <div className="flex items-center gap-2">
        <span className="text-sm text-ink-muted">{t('feedback.question')}</span>
        <button
          type="button"
          className={toggle(rating === 'up')}
          aria-pressed={rating === 'up'}
          aria-label={t('feedback.helpful')}
          disabled={sent || sending}
          onClick={() => choose('up')}
        >
          <ThumbsUp className="size-4" aria-hidden />
        </button>
        <button
          type="button"
          className={toggle(rating === 'down')}
          aria-pressed={rating === 'down'}
          aria-label={t('feedback.notHelpful')}
          disabled={sent || sending}
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
                  'min-h-12 rounded-full border px-3 py-2 text-sm',
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

      {error && (
        <p role="alert" className="flex flex-wrap items-center gap-2 text-sm text-red-700">
          Could not send your rating.
          <button
            type="button"
            className="font-semibold underline"
            onClick={() => rating && void submit(rating, reason)}
          >
            {t('common.retry')}
          </button>
        </p>
      )}

      {sent && (
        <p role="status" className="text-sm text-brand-800">
          {t('feedback.thanks')}
        </p>
      )}
    </div>
  );
}
