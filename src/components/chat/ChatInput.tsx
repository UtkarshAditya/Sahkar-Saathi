import {
  useCallback,
  useEffect,
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
import {
  useSpeechRecognition,
  type SpeechRecognitionErrorCode,
} from '@/hooks/useSpeechRecognition';
import { api } from '@/services/api';
import type { LanguageCode } from '@/types';

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (text: string, fromVoice: boolean) => void;
  loading: boolean;
  language: LanguageCode;
}

type SttProvider = 'auto' | 'backend' | 'browser';
type ActiveProvider = 'backend' | 'browser' | null;
type VoiceInputErrorCode = SpeechRecognitionErrorCode | 'insecure-context';

const CONFIGURED_STT_PROVIDER = import.meta.env.VITE_STT_PROVIDER;
const STT_PROVIDER: SttProvider =
  CONFIGURED_STT_PROVIDER === 'backend' || CONFIGURED_STT_PROVIDER === 'browser'
    ? CONFIGURED_STT_PROVIDER
    : 'auto';

const RECORDER_ERROR_KEYS: Record<RecorderErrorCode, string> = {
  'insecure-context': 'chat.voiceErrors.insecureContext',
  'permission-denied': 'chat.voiceErrors.permissionDenied',
  'no-microphone': 'chat.voiceErrors.noMicrophone',
  'recorder-unsupported': 'chat.voiceErrors.recorderUnsupported',
  'too-short': 'chat.voiceErrors.tooShort',
  'recording-failed': 'chat.voiceErrors.recordingFailed',
};

const RECOGNITION_ERROR_KEYS: Record<SpeechRecognitionErrorCode, string> = {
  'no-speech': 'chat.recognitionErrors.noSpeech',
  'audio-capture': 'chat.recognitionErrors.audioCapture',
  'not-allowed': 'chat.recognitionErrors.notAllowed',
  network: 'chat.recognitionErrors.network',
  'language-not-supported': 'chat.recognitionErrors.languageNotSupported',
  'recognition-stopped': 'chat.recognitionErrors.stopped',
  'recognition-failed': 'chat.recognitionErrors.failed',
  unsupported: 'chat.recognitionErrors.unsupported',
  'insecure-context': 'chat.recognitionErrors.insecureContext',
};

function combineTranscript(draft: string, spokenText: string): string {
  if (!spokenText.trim()) return draft;
  return `${draft}${draft && !/\s$/.test(draft) ? ' ' : ''}${spokenText}`;
}

export function ChatInput({ value, onChange, onSubmit, loading, language }: ChatInputProps) {
  const { t } = useTranslation();
  const id = useId();
  const [transcribing, setTranscribing] = useState(false);
  const [transcriptionFailed, setTranscriptionFailed] = useState(false);
  const [pendingBlob, setPendingBlob] = useState<Blob | null>(null);
  const [reviewingTranscript, setReviewingTranscript] = useState(false);
  const [lowConfidence, setLowConfidence] = useState(false);
  const [activeProvider, setActiveProvider] = useState<ActiveProvider>(null);
  const [voiceInputError, setVoiceInputError] = useState<VoiceInputErrorCode | null>(null);
  const originalDraft = useRef('');
  const previousLanguage = useRef(language);
  const transcriptionRequestId = useRef(0);
  const recognition = useSpeechRecognition();
  const cancelRecognition = recognition.cancel;

  const transcribe = useCallback(
    async (audio: Blob) => {
      const requestId = transcriptionRequestId.current;
      setPendingBlob(audio);
      setTranscribing(true);
      setTranscriptionFailed(false);
      try {
        const result = await api.transcribe(audio, language);
        if (requestId !== transcriptionRequestId.current) return;
        onChange(combineTranscript(originalDraft.current, result.text));
        setLowConfidence(result.confidence < 0.6);
        setReviewingTranscript(true);
      } catch {
        if (requestId === transcriptionRequestId.current) setTranscriptionFailed(true);
      } finally {
        if (requestId === transcriptionRequestId.current) {
          setTranscribing(false);
          setActiveProvider(null);
        }
      }
    },
    [language, onChange],
  );
  const recorder = useRecorder(transcribe);
  const cancelRecorder = recorder.cancel;
  const isBrowserProvider =
    STT_PROVIDER === 'browser' || (STT_PROVIDER === 'auto' && recognition.isSupported);
  const isActive =
    (activeProvider === 'backend' &&
      ['requesting', 'recording', 'processing'].includes(recorder.status)) ||
    (activeProvider === 'browser' &&
      ['starting', 'listening', 'processing'].includes(recognition.status));
  const elapsedSeconds =
    activeProvider === 'browser' ? recognition.elapsedSeconds : recorder.elapsedSeconds;
  const isListening =
    (activeProvider === 'browser' &&
      ['starting', 'listening', 'processing'].includes(recognition.status)) ||
    (activeProvider === 'backend' &&
      ['requesting', 'recording', 'processing'].includes(recorder.status));
  const canSend = value.trim().length > 0 && !loading && !transcribing && !isActive;
  const micDisabled = loading || transcribing || isActive;

  useEffect(() => {
    if (previousLanguage.current === language) return;
    previousLanguage.current = language;
    transcriptionRequestId.current += 1;
    cancelRecorder();
    cancelRecognition();
    if (activeProvider === 'browser') onChange(originalDraft.current);
    setActiveProvider(null);
    setTranscribing(false);
    setTranscriptionFailed(false);
    setPendingBlob(null);
    setReviewingTranscript(false);
    setLowConfidence(false);
    setVoiceInputError(null);
  }, [activeProvider, cancelRecognition, cancelRecorder, language, onChange]);

  useEffect(() => {
    if (activeProvider !== 'browser') return;
    const spokenText = [recognition.finalText, recognition.interimText].filter(Boolean).join(' ');
    if (spokenText) onChange(combineTranscript(originalDraft.current, spokenText));

    if (recognition.status === 'idle') {
      setActiveProvider(null);
      if (recognition.finalText.trim()) setReviewingTranscript(true);
    } else if (recognition.status === 'error') {
      setActiveProvider(null);
      if (recognition.finalText.trim()) setReviewingTranscript(true);
    }
  }, [
    activeProvider,
    language,
    onChange,
    recognition.finalText,
    recognition.interimText,
    recognition.status,
  ]);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canSend) return;
    const fromVoice = reviewingTranscript;
    setReviewingTranscript(false);
    setPendingBlob(null);
    onSubmit(value.trim(), fromVoice);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      if (canSend) {
        const fromVoice = reviewingTranscript;
        setReviewingTranscript(false);
        setPendingBlob(null);
        onSubmit(value.trim(), fromVoice);
      }
    }
  }

  function startRecording() {
    if (micDisabled) return;
    originalDraft.current = value;
    setVoiceInputError(null);
    setTranscriptionFailed(false);
    setReviewingTranscript(false);
    setLowConfidence(false);
    transcriptionRequestId.current += 1;
    if (!window.isSecureContext) {
      setVoiceInputError('insecure-context');
      return;
    }
    if (isBrowserProvider) {
      if (!recognition.isSupported) return;
      cancelRecorder();
      setActiveProvider('browser');
      recognition.start(language);
    } else {
      cancelRecognition();
      setActiveProvider('backend');
      void recorder.start();
    }
  }

  function stopRecording() {
    if (activeProvider === 'browser') recognition.stop();
    if (activeProvider === 'backend') {
      void recorder
        .stop()
        .then(transcribe)
        .catch(() => undefined);
    }
  }

  function cancelRecording() {
    transcriptionRequestId.current += 1;
    if (activeProvider === 'browser') cancelRecognition();
    if (activeProvider === 'backend') cancelRecorder();
    setActiveProvider(null);
    setTranscribing(false);
    setReviewingTranscript(false);
    setLowConfidence(false);
    setTranscriptionFailed(false);
    setPendingBlob(null);
    setVoiceInputError(null);
    onChange(originalDraft.current);
  }

  function discardTranscript() {
    onChange(originalDraft.current);
    setReviewingTranscript(false);
    setLowConfidence(false);
    setPendingBlob(null);
    setTranscriptionFailed(false);
  }

  const recordingStatus =
    activeProvider === 'browser'
      ? recognition.status === 'processing'
        ? t('chat.transcribing')
        : t('chat.listening')
      : recorder.status === 'processing' || transcribing
        ? t('chat.transcribing')
        : t('chat.recording');
  const errorMessage = voiceInputError
    ? t(RECOGNITION_ERROR_KEYS[voiceInputError])
    : recognition.error
      ? t(RECOGNITION_ERROR_KEYS[recognition.error.code])
      : recorder.error
        ? t(RECORDER_ERROR_KEYS[recorder.error.code])
        : transcriptionFailed
          ? t('chat.voiceErrors.transcriptionFailed')
          : '';
  const announcement = isListening
    ? recordingStatus
    : errorMessage
      ? errorMessage
      : transcribing || recorder.status === 'processing' || recognition.status === 'processing'
        ? t('chat.transcribing')
        : '';

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {announcement}
      </div>

      {isListening && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-red-300 bg-red-50 p-3 text-red-900">
          <span className="flex min-h-12 min-w-0 flex-1 items-center gap-2 font-semibold">
            <span className="size-3 animate-pulse rounded-full bg-red-700" aria-hidden />
            {recordingStatus}{' '}
            <time>{`${Math.floor(elapsedSeconds / 60)}:${String(elapsedSeconds % 60).padStart(2, '0')}`}</time>
          </span>
          <Button
            type="button"
            variant="danger"
            size="md"
            disabled={activeProvider === 'browser' && recognition.status === 'processing'}
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
            onClick={cancelRecording}
          >
            {t('chat.cancelRecording')}
          </Button>
        </div>
      )}

      {activeProvider === 'backend' && recorder.status === 'requesting' && (
        <p
          className="rounded-xl bg-brand-50 p-3 text-sm font-semibold text-brand-900"
          role="status"
        >
          {t('chat.requestingMicrophone')}
        </p>
      )}

      {STT_PROVIDER === 'browser' && !recognition.isSupported && (
        <Notice tone="info" role="status">
          {t('chat.recognitionUnsupportedHint')}
        </Notice>
      )}

      {errorMessage && (
        <Notice tone="warning" role="alert">
          <p>{errorMessage}</p>
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

      {(transcribing || recorder.status === 'processing') && (
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
          aria-pressed={isListening}
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
          onChange={(event) => onChange(event.target.value)}
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
