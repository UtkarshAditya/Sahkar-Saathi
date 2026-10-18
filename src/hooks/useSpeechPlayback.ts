import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '@/services/api';
import type { LanguageCode } from '@/types';

export type SpeechPlaybackStatus = 'idle' | 'loading' | 'playing' | 'error';
export type SpeechPlaybackErrorCode = 'api' | 'api-no-voice' | 'no-voice' | 'playback';

export interface SpeechPlaybackError {
  code: SpeechPlaybackErrorCode;
}

export interface SpeechPlaybackController {
  status: SpeechPlaybackStatus;
  activeMessageId: string | null;
  error: SpeechPlaybackError | null;
  play: (messageId: string, text: string, language: LanguageCode, autoPlay?: boolean) => void;
  stop: () => void;
  clear: () => void;
}

const SPEECH_LANGUAGES: Record<string, string> = {
  en: 'en-IN',
  hi: 'hi-IN',
  ta: 'ta-IN',
};

function cacheKey(messageId: string, language: LanguageCode): string {
  return JSON.stringify([messageId, language]);
}

function hasSpeechData(blob: Blob): Promise<boolean> {
  if (blob.size < 44) return Promise.resolve(false);

  return blob.arrayBuffer().then((buffer) => {
    const bytes = new Uint8Array(buffer);
    const view = new DataView(buffer);
    if (view.getUint32(0, false) !== 0x52494646 || view.getUint32(8, false) !== 0x57415645) {
      return false;
    }

    let offset = 12;
    while (offset + 8 <= bytes.length) {
      const chunkId = String.fromCharCode(
        bytes[offset],
        bytes[offset + 1],
        bytes[offset + 2],
        bytes[offset + 3],
      );
      const chunkLength = view.getUint32(offset + 4, true);
      const start = offset + 8;
      const end = Math.min(start + chunkLength, bytes.length);

      if (chunkId === 'data') {
        for (let index = start; index < end; index += 1) {
          if (bytes[index] !== 0) return true;
        }
        return false;
      }
      offset = start + chunkLength + (chunkLength % 2);
    }
    return false;
  });
}

function selectVoice(language: LanguageCode): SpeechSynthesisVoice | undefined {
  if (typeof window === 'undefined' || !window.speechSynthesis) return undefined;
  const requestedLocale =
    SPEECH_LANGUAGES[language.toLowerCase()] ??
    `${language.toLowerCase()}-${language.toUpperCase()}`;
  const voices = window.speechSynthesis.getVoices();
  const matchingVoices = voices.filter(
    (voice) => voice.lang.toLowerCase().split('-')[0] === language.toLowerCase(),
  );
  return (
    matchingVoices.find((voice) => voice.lang.toLowerCase() === requestedLocale.toLowerCase()) ??
    matchingVoices[0]
  );
}

function waitForVoice(language: LanguageCode): Promise<SpeechSynthesisVoice | undefined> {
  if (typeof window === 'undefined' || !window.speechSynthesis) {
    return Promise.resolve(undefined);
  }
  const currentVoice = selectVoice(language);
  if (currentVoice) return Promise.resolve(currentVoice);

  const synthesis = window.speechSynthesis;
  return new Promise((resolve) => {
    const finish = () => {
      window.clearTimeout(timeoutId);
      synthesis.removeEventListener('voiceschanged', handleVoicesChanged);
      resolve(selectVoice(language));
    };
    const handleVoicesChanged = () => {
      if (selectVoice(language)) finish();
    };
    const timeoutId = window.setTimeout(finish, 1000);
    synthesis.addEventListener('voiceschanged', handleVoicesChanged);
  });
}

export function useSpeechPlayback(): SpeechPlaybackController {
  const [status, setStatus] = useState<SpeechPlaybackStatus>('idle');
  const [activeMessageId, setActiveMessageId] = useState<string | null>(null);
  const [error, setError] = useState<SpeechPlaybackError | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const speechUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const cacheRef = useRef(new Map<string, Blob>());
  const runIdRef = useRef(0);
  const mountedRef = useRef(true);
  const apiFallbackRef = useRef(false);
  const fallbackRunRef = useRef(0);

  const releaseActivePlayback = useCallback(() => {
    const audio = audioRef.current;
    if (audio) {
      audio.onended = null;
      audio.onerror = null;
      audio.onplaying = null;
      audio.pause();
      audio.removeAttribute('src');
      audio.load();
      audioRef.current = null;
    }
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
    if (speechUtteranceRef.current && window.speechSynthesis) {
      window.speechSynthesis.cancel();
      speechUtteranceRef.current = null;
    }
  }, []);

  const stop = useCallback(() => {
    runIdRef.current += 1;
    releaseActivePlayback();
    setStatus('idle');
    setActiveMessageId(null);
    setError(null);
    apiFallbackRef.current = false;
  }, [releaseActivePlayback]);

  const clear = useCallback(() => {
    stop();
    cacheRef.current.clear();
  }, [stop]);

  const play = useCallback(
    (messageId: string, text: string, language: LanguageCode, autoPlay = false) => {
      const runId = runIdRef.current + 1;
      runIdRef.current = runId;
      releaseActivePlayback();
      apiFallbackRef.current = false;
      fallbackRunRef.current = 0;
      setActiveMessageId(messageId);
      setError(null);
      setStatus('loading');

      const key = cacheKey(messageId, language);
      const isCurrentRun = () => runIdRef.current === runId && mountedRef.current;

      const fail = (code: SpeechPlaybackErrorCode) => {
        if (!isCurrentRun()) return;
        releaseActivePlayback();
        if (autoPlay) {
          setStatus('idle');
          setActiveMessageId(null);
          setError(null);
          return;
        }
        setError({ code });
        setStatus('error');
      };

      const speakWithBrowser = (voice: SpeechSynthesisVoice) => {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = SPEECH_LANGUAGES[language.toLowerCase()] ?? voice.lang;
        utterance.voice = voice;
        utterance.onstart = () => {
          if (isCurrentRun()) setStatus('playing');
        };
        utterance.onend = () => {
          if (!isCurrentRun()) return;
          speechUtteranceRef.current = null;
          if (apiFallbackRef.current && !autoPlay) {
            setStatus('error');
            setError({ code: 'api' });
          } else {
            setStatus('idle');
            setActiveMessageId(null);
            setError(null);
          }
        };
        utterance.onerror = () => fail('playback');
        speechUtteranceRef.current = utterance;
        window.speechSynthesis.speak(utterance);
      };

      const playBlob = (blob: Blob) => {
        if (!isCurrentRun()) return;
        if (blob.size === 0) {
          fallbackToBrowserSpeech(false);
          return;
        }

        const objectUrl = URL.createObjectURL(blob);
        objectUrlRef.current = objectUrl;
        const audio = new Audio(objectUrl);
        audioRef.current = audio;
        audio.onplaying = () => {
          if (isCurrentRun()) setStatus('playing');
        };
        audio.onended = () => {
          if (!isCurrentRun()) return;
          releaseActivePlayback();
          setStatus('idle');
          setActiveMessageId(null);
          setError(null);
        };
        audio.onerror = () => {
          if (!isCurrentRun()) return;
          releaseActivePlayback();
          fallbackToBrowserSpeech(false);
        };

        void audio.play().then(
          () => {
            if (!isCurrentRun()) return;
            cacheRef.current.set(key, blob);
            setStatus('playing');
          },
          () => {
            if (!isCurrentRun()) return;
            releaseActivePlayback();
            fallbackToBrowserSpeech(false);
          },
        );
      };

      const fallbackToBrowserSpeech = async (apiFailed: boolean) => {
        if (!isCurrentRun() || fallbackRunRef.current === runId) return;
        fallbackRunRef.current = runId;
        const voice = await waitForVoice(language);
        if (!isCurrentRun()) return;
        if (!voice || !window.speechSynthesis) {
          fail(apiFailed ? 'api-no-voice' : 'no-voice');
          return;
        }
        if (apiFailed && !autoPlay) {
          apiFallbackRef.current = true;
          setError({ code: 'api' });
        }
        speakWithBrowser(voice);
      };

      const run = async () => {
        const cached = cacheRef.current.get(key);
        if (cached) {
          if (await hasSpeechData(cached)) {
            if (isCurrentRun()) playBlob(cached);
          } else {
            fallbackToBrowserSpeech(false);
          }
          return;
        }

        let audio: Blob;
        try {
          audio = await api.synthesize({ text, language });
        } catch {
          fallbackToBrowserSpeech(true);
          return;
        }
        if (!isCurrentRun()) return;
        cacheRef.current.set(key, audio);

        if (!(await hasSpeechData(audio))) {
          fallbackToBrowserSpeech(false);
          return;
        }
        if (isCurrentRun()) playBlob(audio);
      };

      void run().catch(() => fallbackToBrowserSpeech(false));
    },
    [releaseActivePlayback],
  );

  useEffect(() => {
    mountedRef.current = true;
    const cache = cacheRef.current;
    return () => {
      mountedRef.current = false;
      runIdRef.current += 1;
      releaseActivePlayback();
      cache.clear();
    };
  }, [releaseActivePlayback]);

  return { status, activeMessageId, error, play, stop, clear };
}
