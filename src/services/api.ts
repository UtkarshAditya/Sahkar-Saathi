/**
 * API client for /api/v1. One function per endpoint in the architecture contract.
 *
 * While VITE_USE_MOCKS is "true", every function resolves local mock
 * data after a short delay so loading states are visible. No network calls are made.
 * Set VITE_USE_MOCKS=false to call the real backend (run it with uvicorn; Vite proxies
 * /api to it). Every endpoint in the frozen contract, backend/openapi.json, is here, and
 * src/types/contract-check.ts fails the build if the types drift from it.
 */
import { COVERED_STATE_CODE, STATES } from '@/data/options';
import { LANGUAGES } from '@/i18n';
import type {
  ApiErrorBody,
  AskRequest,
  AskResponse,
  DocumentFilters,
  EvalSummary,
  FeedbackRequest,
  GrievanceCategory,
  GrievanceGuide,
  GrievanceRequest,
  LanguageCode,
  LessonsResponse,
  LibraryDocument,
  MetaLanguage,
  Scheme,
  SchemeDetail,
  StateOption,
  SynthesizeRequest,
  TranscribeResponse,
} from '@/types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';
/** Mock data is opt-in (VITE_USE_MOCKS=true); by default the app calls the real API. */
export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true';

/** Typing this exact text in Ask triggers the error state, to test it in the UI. */
export const MOCK_ERROR_TRIGGER = '/error';

export class ApiError extends Error {
  readonly code: string;
  readonly status: number | null;
  readonly kind: ApiErrorKind;

  constructor(body: ApiErrorBody, status: number | null, kind: ApiErrorKind) {
    super(body.message);
    this.name = 'ApiError';
    this.code = body.code;
    this.status = status;
    this.kind = kind;
  }
}

export type ApiErrorKind = 'offline' | 'timeout' | 'rate-limited' | 'client' | 'server' | 'unknown';

export function apiErrorTranslationKey(error: unknown): string {
  if (!(error instanceof ApiError)) return 'common.errors.general';
  if (error.kind === 'offline') return 'common.errors.offline';
  if (error.kind === 'timeout') return 'common.errors.timeout';
  if (error.kind === 'rate-limited') return 'common.errors.rateLimited';
  if (error.status === 401 || error.status === 403) return 'common.errors.permission';
  if (error.kind === 'client') return 'common.errors.request';
  if (error.kind === 'server') return 'common.errors.server';
  return 'common.errors.general';
}

const REQUEST_TIMEOUT_MS = 60_000;

function delay<T>(value: T, ms = 600): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

function errorKind(status: number): ApiErrorKind {
  if (status === 429) return 'rate-limited';
  if (status >= 500) return 'server';
  if (status >= 400) return 'client';
  return 'unknown';
}

function isErrorBody(value: unknown): value is ApiErrorBody {
  return (
    typeof value === 'object' &&
    value !== null &&
    'code' in value &&
    typeof value.code === 'string' &&
    'message' in value &&
    typeof value.message === 'string'
  );
}

/** Runs the fetch and body parsing under one timeout and an optional caller signal. */
async function send<T>(
  path: string,
  init: RequestInit | undefined,
  parseResponse: (response: Response) => Promise<T>,
): Promise<T> {
  const controller = new AbortController();
  const callerSignal = init?.signal;
  let timedOut = false;
  const timeout = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, REQUEST_TIMEOUT_MS);
  const abortFromCaller = () => controller.abort();

  if (callerSignal?.aborted) controller.abort();
  else callerSignal?.addEventListener('abort', abortFromCaller, { once: true });

  try {
    const response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
    });
    if (!response.ok) {
      let body: ApiErrorBody = {
        code: `http_${response.status}`,
        message: response.statusText || 'Request failed.',
      };
      try {
        const parsed: unknown = await response.json();
        if (isErrorBody(parsed)) body = parsed;
      } catch (cause) {
        if (timedOut || callerSignal?.aborted) throw cause;
        // Use the HTTP status when the response body is absent or invalid.
      }
      throw new ApiError(body, response.status, errorKind(response.status));
    }
    return await parseResponse(response);
  } catch (cause) {
    if (cause instanceof ApiError) throw cause;
    if (callerSignal?.aborted) throw cause;
    if (timedOut) {
      throw new ApiError(
        { code: 'request_timeout', message: 'The request took too long.' },
        null,
        'timeout',
      );
    }
    const offline = typeof navigator !== 'undefined' && navigator.onLine === false;
    throw new ApiError(
      {
        code: offline ? 'offline' : 'network_error',
        message: offline ? 'The device appears to be offline.' : 'Could not reach the server.',
      },
      null,
      offline ? 'offline' : 'unknown',
    );
  } finally {
    window.clearTimeout(timeout);
    callerSignal?.removeEventListener('abort', abortFromCaller);
  }
}

async function request<T>(path: string, init?: RequestInit, signal?: AbortSignal): Promise<T> {
  return send(
    path,
    {
      ...init,
      signal,
      headers: { 'Content-Type': 'application/json', Accept: 'application/json', ...init?.headers },
    },
    (response) => response.json() as Promise<T>,
  );
}

/** A short silent 16 kHz mono WAV, so mock mode exercises the same code path as the API. */
function silentWav(seconds = 0.5): Blob {
  const rate = 16_000;
  const samples = Math.round(rate * seconds);
  const view = new DataView(new ArrayBuffer(44 + samples * 2));
  const ascii = (offset: number, s: string) =>
    [...s].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
  ascii(0, 'RIFF');
  view.setUint32(4, 36 + samples * 2, true);
  ascii(8, 'WAVEfmt ');
  view.setUint32(16, 16, true); // fmt chunk size
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true); // byte rate
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  ascii(36, 'data');
  view.setUint32(40, samples * 2, true);
  return new Blob([view], { type: 'audio/wav' });
}

function toQuery(params: Record<string, string | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) search.set(key, value);
  });
  const query = search.toString();
  return query ? `?${query}` : '';
}

export const api = {
  /** POST /chat/ask */
  async ask(body: AskRequest, signal?: AbortSignal): Promise<AskResponse> {
    if (!USE_MOCKS)
      return request('/chat/ask', { method: 'POST', body: JSON.stringify(body) }, signal);
    if (body.text.trim() === MOCK_ERROR_TRIGGER) {
      await delay(null, 400);
      throw new ApiError(
        { code: 'mock_error', message: 'Simulated error for testing the UI.' },
        null,
        'unknown',
      );
    }
    const { buildMockAnswer } = await import('@/data/mockChat');
    return delay(buildMockAnswer(body), 900);
  },

  /** GET /meta/languages */
  async listLanguages(signal?: AbortSignal): Promise<MetaLanguage[]> {
    if (!USE_MOCKS) return request('/meta/languages', undefined, signal);
    return delay(
      LANGUAGES.map((l) => ({ code: l.code, label: l.label, english_label: l.englishLabel })),
      100,
    );
  },

  /** GET /meta/states */
  async listStates(signal?: AbortSignal): Promise<StateOption[]> {
    if (!USE_MOCKS) return request('/meta/states', undefined, signal);
    return delay(
      STATES.map((s) => ({ ...s, covered: s.code === COVERED_STATE_CODE })),
      100,
    );
  },

  /** GET /grievance/categories */
  async grievanceCategories(signal?: AbortSignal): Promise<GrievanceCategory[]> {
    if (!USE_MOCKS) return request('/grievance/categories', undefined, signal);
    const { GRIEVANCE_CATEGORIES } = await import('@/data/mockGrievance');
    return delay(
      GRIEVANCE_CATEGORIES.map(({ id, label, description }) => ({ id, label, description })),
      100,
    );
  },

  /** POST /grievance/guide. Never files anything. */
  async grievanceGuide(body: GrievanceRequest, signal?: AbortSignal): Promise<GrievanceGuide> {
    if (!USE_MOCKS) {
      return request('/grievance/guide', { method: 'POST', body: JSON.stringify(body) }, signal);
    }
    const { buildMockGuide } = await import('@/data/mockGrievance');
    return delay(buildMockGuide(body), 800);
  },

  /** GET /schemes */
  async listSchemes(signal?: AbortSignal): Promise<Scheme[]> {
    if (!USE_MOCKS) return request('/schemes', undefined, signal);
    const { MOCK_SCHEMES } = await import('@/data/mockSchemes');
    return delay(MOCK_SCHEMES, 400);
  },

  /** GET /schemes/{slug}. `pmfby` carries the crop insurance guide facts. */
  async getScheme(slug: string, signal?: AbortSignal): Promise<SchemeDetail> {
    if (!USE_MOCKS) return request(`/schemes/${encodeURIComponent(slug)}`, undefined, signal);
    const [{ MOCK_SCHEMES }, { CROP_FACTS }] = await Promise.all([
      import('@/data/mockSchemes'),
      import('@/data/mockCropInsurance'),
    ]);
    const scheme = MOCK_SCHEMES.find((s) => s.slug === slug);
    if (!scheme) {
      await delay(null, 200);
      throw new ApiError(
        { code: 'scheme_not_found', message: 'That scheme was not found.' },
        404,
        'client',
      );
    }
    return delay({ ...scheme, facts: slug === 'pmfby' ? CROP_FACTS : [] }, 400);
  },

  /**
   * GET /documents. Retired versions are included because the Library page filters on
   * the client; pass filters to narrow on the server.
   */
  async listDocuments(
    filters: DocumentFilters = {},
    signal?: AbortSignal,
  ): Promise<LibraryDocument[]> {
    if (!USE_MOCKS) {
      const query = toQuery({
        state: filters.state,
        language: filters.language,
        type: filters.doc_type || undefined,
        include_retired: 'true',
      });
      return request(`/documents${query}`, undefined, signal);
    }
    const { MOCK_DOCUMENTS } = await import('@/data/mockDocuments');
    return delay(MOCK_DOCUMENTS, 400);
  },

  /** GET /lessons. Falls back to English when there is no translation yet. */
  async listLessons(language: LanguageCode = 'en', signal?: AbortSignal): Promise<LessonsResponse> {
    if (!USE_MOCKS) return request(`/lessons${toQuery({ language })}`, undefined, signal);
    const { MOCK_LESSONS, MOCK_QUIZ } = await import('@/data/mockLessons');
    return delay({ language: 'en', lessons: MOCK_LESSONS, quiz: MOCK_QUIZ }, 300);
  },

  /** POST /feedback. Mock mode keeps nothing; the UI shows local state only. */
  async sendFeedback(
    body: FeedbackRequest,
    signal?: AbortSignal,
  ): Promise<{ ok: boolean; id?: number }> {
    if (!USE_MOCKS)
      return request('/feedback', { method: 'POST', body: JSON.stringify(body) }, signal);
    return delay({ ok: true }, 300);
  },

  /** GET /eval/latest. Staff only: log in at /admin/ first (session cookie). */
  async latestEval(signal?: AbortSignal): Promise<EvalSummary> {
    if (!USE_MOCKS) return request('/eval/latest', undefined, signal);
    const { MOCK_EVAL_SUMMARY } = await import('@/data/mockEvaluation');
    return delay(MOCK_EVAL_SUMMARY, 500);
  },

  /**
   * POST /speech/transcribe (multipart). Send the MediaRecorder blob; show the returned
   * text as an editable transcript before calling ask().
   */
  async transcribe(
    audio: Blob,
    languageHint: LanguageCode,
    signal?: AbortSignal,
  ): Promise<TranscribeResponse> {
    if (!USE_MOCKS) {
      const form = new FormData();
      const extension = audio.type.includes('mp4')
        ? 'mp4'
        : audio.type.includes('wav')
          ? 'wav'
          : 'webm';
      form.append('audio', audio, `question.${extension}`);
      form.append('language_hint', languageHint);
      return send(
        '/speech/transcribe',
        { method: 'POST', body: form, signal },
        (response) => response.json() as Promise<TranscribeResponse>,
      );
    }
    const mockTranscripts: Record<string, string> = {
      en: 'What should I do if my insured crop is damaged under PMFBY?',
      hi: 'प्रधानमंत्री फसल बीमा योजना में मेरी फसल खराब हो गई है। मुझे क्या करना चाहिए?',
      ta: 'பயிர் காப்பீட்டுத் திட்டத்தில் என் பயிர் சேதமடைந்தால் நான் என்ன செய்ய வேண்டும்?',
    };
    return delay(
      {
        text: mockTranscripts[languageHint] ?? mockTranscripts.en,
        language: languageHint,
        confidence: 0.9,
      },
      700,
    );
  },

  /** POST /speech/synthesize. Returns WAV audio for the Listen button. */
  async synthesize(body: SynthesizeRequest, signal?: AbortSignal): Promise<Blob> {
    if (!USE_MOCKS) {
      return send(
        '/speech/synthesize',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'audio/wav' },
          body: JSON.stringify(body),
          signal,
        },
        (response) => response.blob(),
      );
    }
    return delay(silentWav(), 500);
  },
};
