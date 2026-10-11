import { useState } from 'react';
import { BookOpen, CircleAlert, MapPin, Phone, Volume2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge, type BadgeTone } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { StateSelector } from '@/components/common/StateSelector';
import { FeedbackButtons } from '@/components/feedback/FeedbackButtons';
import { cn } from '@/lib/format';
import type { AnswerStatus, ChatMessage } from '@/types';
import { CitationList } from './CitationPanel';
import { SuggestedQuestions } from './SuggestedQuestions';

const STATUS: Record<AnswerStatus, { label: string; tone: BadgeTone }> = {
  answered: { label: 'Answered', tone: 'brand' },
  partial: { label: 'Partial answer', tone: 'blue' },
  declined: { label: 'Not found', tone: 'red' },
};

interface MessageBubbleProps {
  message: ChatMessage;
  selected?: boolean;
  disabled?: boolean;
  onViewSources?: (messageId: string) => void;
  onFollowup?: (text: string) => void;
  onChooseState?: (messageId: string, stateCode: string) => void;
}

export function MessageBubble({
  message,
  selected,
  disabled,
  onViewSources,
  onFollowup,
  onChooseState,
}: MessageBubbleProps) {
  const { t } = useTranslation();
  const [pickedState, setPickedState] = useState<string | null>(null);

  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-brand-800 px-4 py-2.5 text-white">
          <p className="sr-only">{t('chat.you')}:</p>
          <p className="whitespace-pre-wrap">{message.text}</p>
        </div>
      </div>
    );
  }

  const response = message.response;
  if (!response) return null;
  const status = STATUS[response.status];
  const asksForState = response.needs_state && Boolean(message.pendingQuestion);

  return (
    <article
      aria-label={t('chat.assistant')}
      className={cn(
        'max-w-[95%] rounded-2xl rounded-bl-md border bg-surface px-4 py-3 sm:max-w-[85%]',
        selected ? 'border-brand-400 ring-2 ring-brand-100' : 'border-line',
      )}
    >
      <header className="mb-2 flex flex-wrap items-center gap-2">
        <span className="font-semibold text-brand-900">{t('chat.assistant')}</span>
        {response.needs_state ? (
          <Badge tone="saffron" icon={<MapPin className="size-3" aria-hidden />}>
            {t('chat.stateNeeded')}
          </Badge>
        ) : (
          <Badge tone={status.tone}>{status.label}</Badge>
        )}
      </header>

      {response.status === 'declined' && (
        <p className="mb-1 flex items-center gap-1.5 font-semibold text-red-800">
          <CircleAlert className="size-4" aria-hidden />
          {t('chat.declinedTitle')}
        </p>
      )}

      <p className="whitespace-pre-wrap">{response.answer_text}</p>

      {response.is_demo && !response.needs_state && (
        <p className="mt-2 text-xs font-semibold text-saffron-700">{t('chat.demoAnswer')}</p>
      )}

      {asksForState && onChooseState && (
        <div className="mt-3 rounded-xl border border-saffron-200 bg-saffron-50 p-3">
          <p className="mb-2 text-sm text-ink-soft">{t('chat.stateNeededBody')}</p>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
            <StateSelector
              value={pickedState}
              onChange={setPickedState}
              label={t('chat.chooseState')}
              className="flex-1"
            />
            <Button
              disabled={!pickedState || disabled}
              onClick={() => pickedState && onChooseState(message.id, pickedState)}
            >
              {t('chat.continue')}
            </Button>
          </div>
        </div>
      )}

      {response.contact && (
        <div className="mt-3 rounded-xl border border-line bg-canvas p-3 text-sm">
          <p className="flex items-center gap-1.5 font-semibold">
            <Phone className="size-4 text-brand-700" aria-hidden />
            {t('chat.contactInstead')}
          </p>
          <p className="mt-1 font-medium">{response.contact.label}</p>
          <p className="text-ink-muted">{response.contact.detail}</p>
        </div>
      )}

      <CitationList citations={response.citations} />

      {response.followups.length > 0 && onFollowup && (
        <div className="mt-3">
          <SuggestedQuestions
            title={t('chat.followups')}
            questions={response.followups}
            onSelect={onFollowup}
            disabled={disabled}
            variant="chips"
          />
        </div>
      )}

      {!response.needs_state && (
        <footer className="mt-3 flex flex-col gap-3 border-t border-line pt-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled
              title="Text to speech will be connected in Sprint 2"
              icon={<Volume2 className="size-4" aria-hidden />}
            >
              {t('chat.listenSoon')}
            </Button>
            {response.citations.length > 0 && onViewSources && (
              // Desktop only: the side panel. Phones see the inline source list above.
              <span className="hidden lg:contents">
                <Button
                  variant={selected ? 'subtle' : 'secondary'}
                  size="sm"
                  aria-pressed={selected}
                  onClick={() => onViewSources(message.id)}
                  icon={<BookOpen className="size-4" aria-hidden />}
                >
                  {t('chat.viewSources')}
                </Button>
              </span>
            )}
          </div>
          <FeedbackButtons messageId={response.message_id} />
        </footer>
      )}
    </article>
  );
}
