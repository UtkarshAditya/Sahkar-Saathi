import { useState } from 'react';
import { BookOpen, CircleAlert, MapPin, Phone } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge, type BadgeTone } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { StateSelector } from '@/components/common/StateSelector';
import { FeedbackButtons } from '@/components/feedback/FeedbackButtons';
import { ListenButton } from '@/components/chat/ListenButton';
import type { SpeechPlaybackController } from '@/hooks/useSpeechPlayback';
import { cn } from '@/lib/format';
import type { AnswerStatus, ChatMessage, LanguageCode } from '@/types';
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
  speech: SpeechPlaybackController;
  language: LanguageCode;
}

export function MessageBubble({
  message,
  selected,
  disabled,
  onViewSources,
  onFollowup,
  onChooseState,
  speech,
  language,
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
        'max-w-[95%] rounded-2xl rounded-bl-md bg-surface px-4 py-3 shadow-sm sm:max-w-[85%]',
        selected && 'ring-2 ring-brand-200',
      )}
    >
      <header className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="font-semibold text-brand-900">{t('chat.assistant')}</span>
          {response.needs_state ? (
            <Badge tone="saffron" icon={<MapPin className="size-3" aria-hidden />}>
              {t('chat.stateNeeded')}
            </Badge>
          ) : (
            <Badge tone={status.tone}>{status.label}</Badge>
          )}
        </div>
        {!response.needs_state && response.status !== 'declined' && response.answer_text.trim() && (
          <ListenButton
            messageId={message.id}
            text={response.answer_text}
            language={message.speechLanguage ?? language}
            speech={speech}
            autoPlay={message.autoPlaySpeech}
          />
        )}
      </header>

      {response.status === 'declined' && (
        <p className="mb-1 flex items-center gap-1.5 font-semibold text-red-800">
          <CircleAlert className="size-4" aria-hidden />
          {t('chat.declinedTitle')}
        </p>
      )}

      <p className="whitespace-pre-wrap">{response.answer_text}</p>

      {response.citations.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-line pt-2 text-sm">
          <BookOpen className="size-4 shrink-0 text-brand-700" aria-hidden />
          <p className="min-w-0 flex-1 text-ink-soft">
            {t('common.source')}:{' '}
            <span className="font-medium text-ink">{response.citations[0].title}</span>
          </p>
          {onViewSources && (
            <Button
              variant="ghost"
              size="sm"
              className="min-h-12"
              onClick={() => onViewSources(message.id)}
            >
              {t('chat.showSource')}
            </Button>
          )}
        </div>
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
        <footer className="mt-3 border-t border-line pt-2">
          <FeedbackButtons messageId={response.message_id} localOnly={message.isExample} compact />
        </footer>
      )}
    </article>
  );
}
