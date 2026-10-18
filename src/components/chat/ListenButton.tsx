import { useEffect, useRef } from 'react';
import { LoaderCircle, Square, Volume2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/common/Button';
import type { SpeechPlaybackController } from '@/hooks/useSpeechPlayback';
import type { LanguageCode } from '@/types';

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

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {announcement}
      </div>
      <Button
        variant={status === 'playing' ? 'primary' : 'secondary'}
        size="md"
        className="min-h-12"
        disabled={status === 'loading'}
        loading={status === 'loading'}
        aria-label={
          status === 'loading'
            ? t('chat.listenLoading')
            : status === 'playing'
              ? t('chat.stopListening')
              : t('chat.listen')
        }
        aria-pressed={status === 'playing'}
        onClick={handleClick}
        icon={
          status === 'playing' ? (
            <Square className="size-5" aria-hidden />
          ) : status === 'loading' ? (
            <LoaderCircle className="size-5 animate-spin" aria-hidden />
          ) : (
            <Volume2 className="size-5" aria-hidden />
          )
        }
      >
        {status === 'loading'
          ? t('chat.listenLoading')
          : status === 'playing'
            ? t('chat.stopListening')
            : t('chat.listen')}
      </Button>
      {speech.error && isActive && (
        <>
          <p className="basis-full text-sm font-medium text-red-800" role="alert">
            {t(`chat.listenErrors.${speech.error.code}`)}
          </p>
          <Button
            variant="secondary"
            size="md"
            className="min-h-12"
            onClick={() => play(messageId, spokenText, language)}
          >
            {t('chat.retryListen')}
          </Button>
        </>
      )}
    </div>
  );
}
