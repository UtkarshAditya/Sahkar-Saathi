import {
  useCallback,
  useId,
  useRef,
  useState,
  type CSSProperties,
  type FormEvent,
  type KeyboardEvent,
} from 'react';
import { Mic, Send, Square, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/common/Button';
import { Notice } from '@/components/common/Notice';
import { useRecorder, type RecorderErrorCode } from '@/hooks/useRecorder';
import { api } from '@/services/api';
import type { LanguageCode } from '@/types';

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (text: string, fromVoice: boolean) => void;
  loading: boolean;
  language: LanguageCode;
}

const RECORDER_ERROR_KEYS: Record<RecorderErrorCode, string> = {
  'insecure-context': 'chat.voiceErrors.insecureContext',
  'permission-denied': 'chat.voiceErrors.permissionDenied',
  'no-microphone': 'chat.voiceErrors.noMicrophone',
  'recorder-unsupported': 'chat.voiceErrors.recorderUnsupported',
  'too-short': 'chat.voiceErrors.tooShort',
  'recording-failed': 'chat.voiceErrors.recordingFailed',
};

export function ChatInput({ value, onChange, onSubmit, loading, language }: ChatInputProps) {
  const { t } = useTranslation();
  const id = useId();
  const [transcribing, setTranscribing] = useState(false);
  const [transcriptionFailed, setTranscriptionFailed] = useState(false);
  const [pendingBlob, setPendingBlob] = useState<Blob | null>(null);
  const [reviewingTranscript, setReviewingTranscript] = useState(false);
  const [lowConfidence, setLowConfidence] = useState(false);
  const originalDraft = useRef('');

  const transcribe = useCallback(
    async (audio: Blob) => {
      setPendingBlob(audio);
      setTranscribing(true);
      setTranscriptionFailed(false);
      try {
        const result = await api.transcribe(audio, language);
        onChange(result.text);
        setLowConfidence(result.confidence < 0.6);
        setReviewingTranscript(true);
      } catch {
        setTranscriptionFailed(true);
      } finally {
        setTranscribing(false);
      }
    },
    [language, onChange],
  );
  const recorder = useRecorder(transcribe);
  const recordingInProgress =
    recorder.status === 'requesting' ||
    recorder.status === 'recording' ||
    recorder.status === 'processing';
  const canSend = value.trim().length > 0 && !loading && !transcribing && !recordingInProgress;
  const micDisabled =
    loading ||
    transcribing ||
    recorder.status === 'requesting' ||
    recorder.status === 'recording' ||
    recorder.status === 'processing';

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (canSend) {
      setReviewingTranscript(false);
      setPendingBlob(null);
      onSubmit(value.trim(), reviewingTranscript);
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      if (canSend) {
        setReviewingTranscript(false);
        setPendingBlob(null);
        onSubmit(value.trim(), reviewingTranscript);
      }
    }
  }

  function startRecording() {
    originalDraft.current = value;
    setTranscriptionFailed(false);
    void recorder.start();
  }

  function stopRecording() {
    void recorder
      .stop()
      .then(transcribe)
      .catch(() => undefined);
  }

  function discardTranscript() {
    onChange(originalDraft.current);
    setReviewingTranscript(false);
    setLowConfidence(false);
    setPendingBlob(null);
    setTranscriptionFailed(false);
  }

  const announcement =
    recorder.status === 'requesting'
      ? t('chat.requestingMicrophone')
      : recorder.status === 'recording'
        ? t('chat.recordingAnnouncement')
        : recorder.status === 'processing' || transcribing
          ? t('chat.transcribing')
          : '';

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {announcement}
      </div>

      {recorder.status === 'recording' && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-red-300 bg-red-50 p-3 text-red-900">
          <span className="flex min-h-12 flex-1 items-center gap-2 font-semibold">
            <span className="size-3 animate-pulse rounded-full bg-red-700" aria-hidden />
            {t('chat.recording')}{' '}
            <time>{`${Math.floor(recorder.elapsedSeconds / 60)}:${String(
              recorder.elapsedSeconds % 60,
            ).padStart(2, '0')}`}</time>
          </span>
          <Button
            type="button"
            variant="danger"
            size="md"
            icon={<Square className="size-5" aria-hidden />}
            onClick={stopRecording}
          >
            {t('chat.stopRecording')}
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="md"
            icon={<X className="size-5" aria-hidden />}
            onClick={recorder.cancel}
          >
            {t('chat.cancelRecording')}
          </Button>
        </div>
      )}

      {recorder.status === 'requesting' && (
        <p
          className="rounded-xl bg-brand-50 p-3 text-sm font-semibold text-brand-900"
          role="status"
        >
          {t('chat.requestingMicrophone')}
        </p>
      )}

      {(recorder.error || transcriptionFailed) && (
        <Notice tone="warning" role="alert">
          <p>
            {recorder.error
              ? t(RECORDER_ERROR_KEYS[recorder.error.code])
              : t('chat.voiceErrors.transcriptionFailed')}
          </p>
          {transcriptionFailed && pendingBlob && (
            <Button
              type="button"
              variant="secondary"
              size="md"
              className="mt-2"
              onClick={() => void transcribe(pendingBlob)}
            >
              {t('chat.retryTranscription')}
            </Button>
          )}
        </Notice>
      )}

      {transcribing && (
        <p
          className="rounded-xl bg-brand-50 p-3 text-sm font-semibold text-brand-900"
          role="status"
        >
          {t('chat.transcribing')}
        </p>
      )}

      {reviewingTranscript && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-brand-200 bg-brand-50 px-3 py-2">
          <p className="text-sm font-semibold text-brand-900">{t('chat.reviewTranscript')}</p>
          <Button type="button" variant="secondary" size="md" onClick={discardTranscript}>
            {t('chat.discardTranscript')}
          </Button>
        </div>
      )}
      {lowConfidence && reviewingTranscript && (
        <p className="rounded-lg bg-saffron-50 px-3 py-2 text-sm font-medium text-saffron-800">
          {t('chat.lowConfidenceTranscript')}
        </p>
      )}

      <label htmlFor={id} className="sr-only">
        {t('chat.inputLabel')}
      </label>
      <div className="flex items-end gap-2 rounded-2xl border border-line bg-surface p-2 focus-within:border-brand-600 focus-within:ring-2 focus-within:ring-brand-200">
        <button
          type="button"
          onClick={startRecording}
          disabled={micDisabled}
          aria-pressed={recorder.status === 'recording'}
          aria-label={t('chat.mic')}
          className="flex min-h-12 min-w-14 shrink-0 flex-col items-center justify-center gap-0.5 rounded-xl bg-saffron-50 px-2 py-1 text-xs font-semibold text-saffron-800 ring-1 ring-saffron-200 hover:bg-saffron-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Mic className="size-5" aria-hidden />
          <span>{t('chat.micButton')}</span>
        </button>
        <textarea
          id={id}
          rows={1}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t('chat.placeholder')}
          className="max-h-40 min-h-12 min-w-0 flex-1 resize-none bg-transparent px-2 py-2.5 text-base outline-none placeholder:text-ink-muted"
          style={{ fieldSizing: 'content' } as CSSProperties}
        />
        <Button
          type="submit"
          disabled={!canSend}
          loading={loading}
          icon={<Send className="size-5" aria-hidden />}
          className="min-h-12 shrink-0 rounded-xl px-3"
          aria-label={t('chat.send')}
        >
          {t('chat.send')}
        </Button>
      </div>
      <p className="px-1 text-xs text-ink-muted">{t('chat.keyboardHint')}</p>
    </form>
  );
}
