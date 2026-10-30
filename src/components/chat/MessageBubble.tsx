import { useState, type ReactNode } from 'react';
import { Check, CircleCheck, CircleDot, Copy, MapPin, Phone, SearchX } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge, type BadgeTone } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { StateSelector } from '@/components/common/StateSelector';
import { FeedbackButtons } from '@/components/feedback/FeedbackButtons';
import { ListenButton } from '@/components/chat/ListenButton';
import { useCopyToClipboard } from '@/hooks/useCopyToClipboard';
import type { SpeechPlaybackController } from '@/hooks/useSpeechPlayback';
import type { AnswerStatus, ChatMessage, LanguageCode } from '@/types';
import { SourceList } from './SourceList';
import { SuggestedQuestions } from './SuggestedQuestions';
import { TOOLBAR_BUTTON } from './toolbar';

/** Status is shown with an icon and a word, never by colour alone. */
const STATUS: Record<AnswerStatus, { labelKey: string; tone: BadgeTone; icon: ReactNode }> = {
  answered: {
    labelKey: 'chat.status.answered',
    tone: 'brand',
    icon: <CircleCheck className="size-3.5" aria-hidden />,
  },
  partial: {
    labelKey: 'chat.status.partial',
    tone: 'blue',
    icon: <CircleDot className="size-3.5" aria-hidden />,
  },
  declined: {
    labelKey: 'chat.status.declined',
    tone: 'neutral',
    icon: <SearchX className="size-3.5" aria-hidden />,
  },
};

function CopyButton({ text }: { text: string }) {
  const { t } = useTranslation();
  const { copied, error, copy } = useCopyToClipboard();
  return (
    <>
      <button
        type="button"
        className={TOOLBAR_BUTTON}
        onClick={() => void copy(text)}
        aria-label={copied ? t('common.copied') : t('common.copy')}
        title={t('common.copy')}
      >
        {copied ? (
          <Check className="size-4 text-brand-700" aria-hidden />
        ) : (
          <Copy className="size-4" aria-hidden />
        )}
      </button>
      <span className="sr-only" role="status">
        {copied ? t('common.copied') : ''}
      </span>
      {error && (
        <p role="alert" className="basis-full px-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </>
  );
}

interface MessageBubbleProps {
  message: ChatMessage;
  disabled?: boolean;
  onFollowup?: (text: string) => void;
  onChooseState?: (messageId: string, stateCode: string) => void;
  speech: SpeechPlaybackController;
  language: LanguageCode;
}

export function MessageBubble({
  message,
  disabled,
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
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-brand-50 px-4 py-2.5 text-ink ring-1 ring-brand-100">
          <p className="sr-only">{t('chat.you')}:</p>
          <p className="whitespace-pre-wrap">{message.text}</p>
        </div>
      </div>
    );
  }

  const response = message.response;
  if (!response) return null;
  const declined = response.status === 'declined';
  const status = STATUS[response.status];
  const asksForState = response.needs_state && Boolean(message.pendingQuestion);

  return (
    <article aria-label={t('chat.assistant')} className="min-w-0">
      <header className="mb-1.5 flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-ink">{t('chat.assistant')}</span>
        {response.needs_state ? (
          <Badge tone="saffron" icon={<MapPin className="size-3.5" aria-hidden />}>
            {t('chat.stateNeeded')}
          </Badge>
        ) : (
          !declined && (
            <Badge tone={status.tone} icon={status.icon}>
              {t(status.labelKey)}
            </Badge>
          )
        )}
      </header>

      {declined && (
        <p className="mb-1 flex items-center gap-1.5 font-semibold text-ink">
          <SearchX className="size-4 text-ink-muted" aria-hidden />
          {t('chat.declinedTitle')}
        </p>
      )}

      <p className={declined ? 'whitespace-pre-wrap text-ink-soft' : 'whitespace-pre-wrap'}>
        {response.answer_text}
      </p>

      {response.is_demo && !response.needs_state && (
        <p className="mt-2 text-xs font-medium text-saffron-700">{t('chat.demoAnswer')}</p>
      )}

      {asksForState && onChooseState && (
        <div className="mt-3 rounded-xl border border-line bg-subtle p-3">
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
        <p className="mt-3 flex gap-2 text-sm text-ink-soft">
          <Phone className="mt-0.5 size-4 shrink-0 text-ink-muted" aria-hidden />
          <span>
            <span className="font-semibold text-ink">{t('chat.contactInstead')}:</span>{' '}
            {response.contact.label}
            {response.contact.detail && (
              <span className="text-ink-muted"> · {response.contact.detail}</span>
            )}
          </span>
        </p>
      )}

      <SourceList citations={response.citations} />

      {response.followups.length > 0 && onFollowup && (
        <div className="mt-4">
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
        <div className="mt-2 -ml-2 flex flex-wrap items-center">
          {response.answer_text.trim() && <CopyButton text={response.answer_text} />}
          {!declined && response.answer_text.trim() && (
            <ListenButton
              messageId={message.id}
              text={response.answer_text}
              language={message.speechLanguage ?? language}
              speech={speech}
              autoPlay={message.autoPlaySpeech}
            />
          )}
          <FeedbackButtons messageId={response.message_id} localOnly={message.isExample} />
        </div>
      )}
    </article>
  );
}
