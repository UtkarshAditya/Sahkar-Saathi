import { useCallback, useEffect, useRef, useState } from 'react';
import type { LanguageCode } from '@/types';

export type SpeechRecognitionStatus = 'idle' | 'starting' | 'listening' | 'processing' | 'error';

export type SpeechRecognitionErrorCode =
  | 'no-speech'
  | 'audio-capture'
  | 'not-allowed'
  | 'network'
  | 'language-not-supported'
  | 'recognition-stopped'
  | 'recognition-failed'
  | 'unsupported'
  | 'insecure-context';

export interface SpeechRecognitionError {
  code: SpeechRecognitionErrorCode;
}

interface UseSpeechRecognitionResult {
  status: SpeechRecognitionStatus;
  elapsedSeconds: number;
  interimText: string;
  finalText: string;
  error: SpeechRecognitionError | null;
  isSupported: boolean;
  start: (language: LanguageCode) => void;
  stop: () => void;
  cancel: () => void;
}

const RECOGNITION_LOCALES: Record<string, string> = {
  en: 'en-IN',
  hi: 'hi-IN',
  ta: 'ta-IN',
};

function getRecognitionConstructor(): SpeechRecognitionConstructorLike | undefined {
  if (typeof window === 'undefined') return undefined;
  return window.SpeechRecognition ?? window.webkitSpeechRecognition;
}

function recognitionError(code: string): SpeechRecognitionError {
  const knownErrors: SpeechRecognitionErrorCode[] = [
    'no-speech',
    'audio-capture',
    'not-allowed',
    'network',
    'language-not-supported',
  ];
  return {
    code: knownErrors.includes(code as SpeechRecognitionErrorCode)
      ? (code as SpeechRecognitionErrorCode)
      : 'recognition-failed',
  };
}

export function useSpeechRecognition(): UseSpeechRecognitionResult {
  const [status, setStatus] = useState<SpeechRecognitionStatus>('idle');
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [interimText, setInterimText] = useState('');
  const [finalText, setFinalText] = useState('');
  const [error, setError] = useState<SpeechRecognitionError | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const activeRef = useRef(false);
  const stoppingRef = useRef(false);
  const errorRef = useRef<SpeechRecognitionError | null>(null);
  const finalTextRef = useRef('');
  const startedAtRef = useRef<number | null>(null);
  const intervalRef = useRef<number | null>(null);
  const sessionIdRef = useRef(0);
  const mountedRef = useRef(true);
  const Constructor = getRecognitionConstructor();
  const isSupported = Boolean(Constructor);

  const clearTimer = useCallback(() => {
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const cancel = useCallback(() => {
    sessionIdRef.current += 1;
    activeRef.current = false;
    stoppingRef.current = false;
    startedAtRef.current = null;
    clearTimer();
    const recognition = recognitionRef.current;
    recognitionRef.current = null;
    if (recognition) {
      recognition.onstart = null;
      recognition.onresult = null;
      recognition.onerror = null;
      recognition.onend = null;
      try {
        recognition.abort();
      } catch {
        // The recognition session may already have ended.
      }
    }
    errorRef.current = null;
    finalTextRef.current = '';
    setElapsedSeconds(0);
    setInterimText('');
    setFinalText('');
    setError(null);
    setStatus('idle');
  }, [clearTimer]);

  const start = useCallback(
    (language: LanguageCode) => {
      if (activeRef.current) return;
      cancel();

      if (!window.isSecureContext) {
        const failure: SpeechRecognitionError = { code: 'insecure-context' };
        errorRef.current = failure;
        setError(failure);
        setStatus('error');
        return;
      }

      const Recognition = getRecognitionConstructor();
      if (!Recognition) {
        const failure: SpeechRecognitionError = { code: 'unsupported' };
        errorRef.current = failure;
        setError(failure);
        setStatus('error');
        return;
      }

      const recognition = new Recognition();
      const sessionId = sessionIdRef.current + 1;
      sessionIdRef.current = sessionId;
      recognitionRef.current = recognition;
      activeRef.current = true;
      stoppingRef.current = false;
      errorRef.current = null;
      finalTextRef.current = '';
      startedAtRef.current = Date.now();

      recognition.lang =
        RECOGNITION_LOCALES[language.toLowerCase()] ??
        `${language.toLowerCase()}-${language.toUpperCase()}`;
      recognition.interimResults = true;
      recognition.continuous = true;
      recognition.onstart = () => {
        if (sessionIdRef.current !== sessionId || !mountedRef.current) return;
        setStatus('listening');
        intervalRef.current = window.setInterval(() => {
          const startedAt = startedAtRef.current;
          if (startedAt !== null && mountedRef.current) {
            setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
          }
        }, 250);
      };
      recognition.onresult = (event) => {
        if (sessionIdRef.current !== sessionId || !mountedRef.current) return;
        const finalResults: string[] = [];
        const interimResults: string[] = [];
        for (let index = 0; index < event.results.length; index += 1) {
          const result = event.results[index];
          if (!result?.[0]?.transcript) continue;
          if (result.isFinal) finalResults.push(result[0].transcript);
          else interimResults.push(result[0].transcript);
        }
        finalTextRef.current = finalResults.join(' ').trim();
        setFinalText(finalTextRef.current);
        setInterimText(interimResults.join(' ').trim());
      };
      recognition.onerror = (event) => {
        if (sessionIdRef.current !== sessionId || !mountedRef.current) return;
        const failure = recognitionError(event.error);
        errorRef.current = failure;
        activeRef.current = false;
        clearTimer();
        setError(failure);
        setStatus('error');
      };
      recognition.onend = () => {
        if (sessionIdRef.current !== sessionId || !mountedRef.current) return;
        activeRef.current = false;
        recognitionRef.current = null;
        startedAtRef.current = null;
        clearTimer();
        if (errorRef.current) {
          setStatus('error');
          return;
        }
        if (!finalTextRef.current.trim()) {
          const failure: SpeechRecognitionError = { code: 'no-speech' };
          errorRef.current = failure;
          setError(failure);
          setStatus('error');
          return;
        }
        if (!stoppingRef.current) {
          const failure: SpeechRecognitionError = { code: 'recognition-stopped' };
          errorRef.current = failure;
          setError(failure);
          setStatus('error');
          return;
        }
        setStatus('idle');
      };

      setElapsedSeconds(0);
      setInterimText('');
      setFinalText('');
      setError(null);
      setStatus('starting');
      try {
        recognition.start();
      } catch {
        activeRef.current = false;
        recognitionRef.current = null;
        const failure: SpeechRecognitionError = { code: 'recognition-failed' };
        errorRef.current = failure;
        setError(failure);
        setStatus('error');
      }
    },
    [cancel, clearTimer],
  );

  const stop = useCallback(() => {
    const recognition = recognitionRef.current;
    if (!recognition || !activeRef.current || stoppingRef.current) return;
    stoppingRef.current = true;
    setStatus('processing');
    clearTimer();
    try {
      recognition.stop();
    } catch {
      const failure: SpeechRecognitionError = { code: 'recognition-failed' };
      errorRef.current = failure;
      activeRef.current = false;
      setError(failure);
      setStatus('error');
    }
  }, [clearTimer]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      sessionIdRef.current += 1;
      activeRef.current = false;
      clearTimer();
      const recognition = recognitionRef.current;
      recognitionRef.current = null;
      if (recognition) {
        recognition.onstart = null;
        recognition.onresult = null;
        recognition.onerror = null;
        recognition.onend = null;
        try {
          recognition.abort();
        } catch {
          // The recognition session may already have ended.
        }
      }
    };
  }, [clearTimer]);

  return {
    status,
    elapsedSeconds,
    interimText,
    finalText,
    error,
    isSupported,
    start,
    stop,
    cancel,
  };
}
