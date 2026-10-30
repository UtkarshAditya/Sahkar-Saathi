import { useEffect, useRef } from 'react';
import { LoaderCircle, Square, Volume2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/common/Button';
import type { SpeechPlaybackController } from '@/hooks/useSpeechPlayback';
import { cn } from '@/lib/format';
import type { LanguageCode } from '@/types';
import { TOOLBAR_BUTTON } from './toolbar';

interface ListenButtonProps {
  messageId: string;
  text: string;
  language: LanguageCode;
  speech: SpeechPlaybackController;
  autoPlay?: boolean;
}

function cleanForSpeech(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/\[(?:\d+[\s,;–-]*)+\]/g, ' ')
    .replace(/^\s{0,3}#{1,6}\s*/gm, '')
    .replace(/^\s*[-*+]\s+/gm, '')
    .replace(/^\s*\d+[.)]\s+/gm, '')
    .replace(/[>*_~`]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

export function ListenButton({
  messageId,
  text,
  language,
  speech,
  autoPlay = false,
}: ListenButtonProps) {
  const { t } = useTranslation();
  const play = speech.play;
  const autoPlayedRef = useRef<string | null>(null);
  const isActive = speech.activeMessageId === messageId;
  const status = isActive ? speech.status : 'idle';
  const spokenText = cleanForSpeech(text);

  useEffect(() => {
    const autoPlayKey = `${messageId}:${language}`;
    if (autoPlay && autoPlayedRef.current !== autoPlayKey) {
      autoPlayedRef.current = autoPlayKey;
      play(messageId, spokenText, language, true);
    }
  }, [autoPlay, language, messageId, play, spokenText]);

  if (!spokenText) return null;

  const announcement =
    status === 'loading'
      ? t('chat.listenLoadingAnnouncement')
      : status === 'playing'
        ? t('chat.listenPlayingAnnouncement')
        : status === 'error'
          ? t('chat.listenErrorAnnouncement')
          : t('chat.listenStoppedAnnouncement');

  const handleClick = () => {
    if (status === 'playing') {
      speech.stop();
    } else {
      play(messageId, spokenText, language);
    }
  };

  const label =
    status === 'loading'
      ? t('chat.listenLoading')
      : status === 'playing'
        ? t('chat.stopListening')
        : t('chat.listen');

  return (
    <>
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {announcement}
      </div>
      <button
        type="button"
        className={cn(TOOLBAR_BUTTON, status === 'playing' && 'bg-brand-50 text-brand-800')}
        disabled={status === 'loading'}
        aria-busy={status === 'loading' || undefined}
        aria-label={label}
        title={label}
        aria-pressed={status === 'playing'}
        onClick={handleClick}
      >
        {status === 'playing' ? (
          <Square className="size-4" aria-hidden />
        ) : status === 'loading' ? (
          <LoaderCircle className="size-4 animate-spin" aria-hidden />
        ) : (
          <Volume2 className="size-4" aria-hidden />
        )}
      </button>
      {speech.error && isActive && (
        <div className="flex basis-full flex-wrap items-center gap-2 px-2 pb-1">
          <p className="text-sm font-medium text-red-800" role="alert">
            {t(`chat.listenErrors.${speech.error.code}`)}
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => play(messageId, spokenText, language)}
          >
            {t('chat.retryListen')}
          </Button>
        </div>
      )}
    </>
  );
}
