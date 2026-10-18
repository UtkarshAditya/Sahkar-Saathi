import { useCallback, useEffect, useRef, useState } from 'react';

export type RecorderStatus = 'idle' | 'requesting' | 'recording' | 'processing' | 'error';

export type RecorderErrorCode =
  | 'insecure-context'
  | 'permission-denied'
  | 'no-microphone'
  | 'recorder-unsupported'
  | 'too-short'
  | 'recording-failed';

export interface RecorderError {
  code: RecorderErrorCode;
}

interface UseRecorderResult {
  status: RecorderStatus;
  elapsedSeconds: number;
  error: RecorderError | null;
  start: () => Promise<void>;
  stop: () => Promise<Blob>;
  cancel: () => void;
}

const MAX_DURATION_SECONDS = 60;

function recorderError(error: unknown): RecorderError {
  if (error instanceof DOMException) {
    if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
      return { code: 'permission-denied' };
    }
    if (
      error.name === 'NotFoundError' ||
      error.name === 'DevicesNotFoundError' ||
      error.name === 'OverconstrainedError'
    ) {
      return { code: 'no-microphone' };
    }
  }
  return { code: 'recording-failed' };
}

function stopTracks(stream: MediaStream | null) {
  stream?.getTracks().forEach((track) => track.stop());
}

export function useRecorder(onAutoStop: (blob: Blob) => void): UseRecorderResult {
  const [status, setStatus] = useState<RecorderStatus>('idle');
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [error, setError] = useState<RecorderError | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef<number | null>(null);
  const intervalRef = useRef<number | null>(null);
  const resolveStopRef = useRef<((blob: Blob) => void) | null>(null);
  const rejectStopRef = useRef<((error: RecorderError) => void) | null>(null);
  const autoStopRef = useRef(onAutoStop);
  const mountedRef = useRef(true);

  useEffect(() => {
    autoStopRef.current = onAutoStop;
  }, [onAutoStop]);

  const clearTimer = useCallback(() => {
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const releaseStream = useCallback(() => {
    stopTracks(streamRef.current);
    streamRef.current = null;
  }, []);

  const stop = useCallback((): Promise<Blob> => {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state !== 'recording') {
      return Promise.reject<Blob>({ code: 'recording-failed' } satisfies RecorderError);
    }

    setStatus('processing');
    clearTimer();

    return new Promise<Blob>((resolve, reject) => {
      resolveStopRef.current = resolve;
      rejectStopRef.current = reject;
      try {
        recorder.stop();
      } catch {
        const failure: RecorderError = { code: 'recording-failed' };
        releaseStream();
        recorderRef.current = null;
        rejectStopRef.current = null;
        resolveStopRef.current = null;
        setError(failure);
        setStatus('error');
        reject(failure);
      } finally {
        releaseStream();
      }
    });
  }, [clearTimer, releaseStream]);

  const cancel = useCallback(() => {
    clearTimer();
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== 'inactive') {
      recorder.onstop = null;
      recorder.onerror = null;
      try {
        recorder.stop();
      } catch {
        // The tracks are still stopped below if stop races with browser teardown.
      }
    }
    recorderRef.current = null;
    resolveStopRef.current = null;
    rejectStopRef.current = null;
    chunksRef.current = [];
    startedAtRef.current = null;
    releaseStream();
    setElapsedSeconds(0);
    setError(null);
    setStatus('idle');
  }, [clearTimer, releaseStream]);

  const start = useCallback(async () => {
    setError(null);
    setElapsedSeconds(0);
    setStatus('requesting');

    if (!window.isSecureContext) {
      const failure: RecorderError = { code: 'insecure-context' };
      setError(failure);
      setStatus('error');
      return;
    }
    if (typeof MediaRecorder === 'undefined') {
      const failure: RecorderError = { code: 'recorder-unsupported' };
      setError(failure);
      setStatus('error');
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      const failure: RecorderError = { code: 'recorder-unsupported' };
      setError(failure);
      setStatus('error');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!mountedRef.current) {
        stopTracks(stream);
        return;
      }
      streamRef.current = stream;
      const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'].find((candidate) =>
        MediaRecorder.isTypeSupported(candidate),
      );
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      chunksRef.current = [];
      startedAtRef.current = Date.now();
      recorderRef.current = recorder;
      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onerror = () => {
        const failure: RecorderError = { code: 'recording-failed' };
        clearTimer();
        releaseStream();
        recorderRef.current = null;
        rejectStopRef.current?.(failure);
        rejectStopRef.current = null;
        resolveStopRef.current = null;
        if (mountedRef.current) {
          setError(failure);
          setStatus('error');
        }
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || chunksRef.current[0]?.type || 'application/octet-stream',
        });
        const duration =
          startedAtRef.current === null ? 0 : (Date.now() - startedAtRef.current) / 1000;
        recorderRef.current = null;
        startedAtRef.current = null;
        releaseStream();

        if (duration < 1 || blob.size === 0) {
          const failure: RecorderError = { code: 'too-short' };
          if (mountedRef.current) {
            setError(failure);
            setStatus('error');
          }
          rejectStopRef.current?.(failure);
        } else {
          if (mountedRef.current) setStatus('idle');
          resolveStopRef.current?.(blob);
        }
        resolveStopRef.current = null;
        rejectStopRef.current = null;
      };

      recorder.start();
      setStatus('recording');
      intervalRef.current = window.setInterval(() => {
        const startedAt = startedAtRef.current;
        if (startedAt === null) return;
        const elapsed = Math.floor((Date.now() - startedAt) / 1000);
        setElapsedSeconds(Math.min(elapsed, MAX_DURATION_SECONDS));
        if (elapsed >= MAX_DURATION_SECONDS) {
          void stop()
            .then((blob) => autoStopRef.current(blob))
            .catch(() => undefined);
        }
      }, 250);
    } catch (cause) {
      const failure = recorderError(cause);
      releaseStream();
      recorderRef.current = null;
      if (mountedRef.current) {
        setError(failure);
        setStatus('error');
      }
    }
  }, [clearTimer, releaseStream, stop]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      clearTimer();
      const recorder = recorderRef.current;
      if (recorder && recorder.state !== 'inactive') {
        recorder.onstop = null;
        recorder.onerror = null;
        try {
          recorder.stop();
        } catch {
          // Always release the stream, even if the recorder has already stopped.
        }
      }
      releaseStream();
    };
  }, [clearTimer, releaseStream]);

  return { status, elapsedSeconds, error, start, stop, cancel };
}
