/**
 * API client for /api/v1. One function per endpoint in the architecture contract.
 *
 * While VITE_USE_MOCKS is "true" (the default), every function resolves local mock
 * data after a short delay so loading states are visible. No network calls are made.
 * Set VITE_USE_MOCKS=false to call the real backend (run it with uvicorn; Vite proxies
 * /api to it). Every endpoint in the frozen contract, backend/openapi.json, is here, and
 * src/types/contract-check.ts fails the build if the types drift from it.
 */
import { buildMockAnswer } from '@/data/mockChat';
import { CROP_FACTS } from '@/data/mockCropInsurance';
import { MOCK_DOCUMENTS } from '@/data/mockDocuments';
import { MOCK_EVAL_SUMMARY } from '@/data/mockEvaluation';
import { buildMockGuide, GRIEVANCE_CATEGORIES } from '@/data/mockGrievance';
import { MOCK_LESSONS, MOCK_QUIZ } from '@/data/mockLessons';
import { MOCK_SCHEMES } from '@/data/mockSchemes';
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
export const USE_MOCKS = (import.meta.env.VITE_USE_MOCKS ?? 'true') !== 'false';

/** Typing this exact text in Ask triggers the error state, to test it in the UI. */
export const MOCK_ERROR_TRIGGER = '/error';

export class ApiError extends Error {
  readonly code: string;

  constructor(body: ApiErrorBody) {
    super(body.message);
    this.name = 'ApiError';
    this.code = body.code;
  }
}

function delay<T>(value: T, ms = 600): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

/** fetch() that turns any non-2xx response into an ApiError with the contract's error shape. */
async function send(path: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, init);
  } catch {
    throw new ApiError({ code: 'network_error', message: 'Could not reach the server.' });
  }
  if (!response.ok) {
    let body: ApiErrorBody = { code: `http_${response.status}`, message: response.statusText };
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      // Keep the status-based error when the body is not JSON.
    }
    throw new ApiError(body);
  }
  return response;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await send(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', Accept: 'application/json', ...init?.headers },
  });
  return (await response.json()) as T;
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
  async ask(body: AskRequest): Promise<AskResponse> {
    if (!USE_MOCKS) return request('/chat/ask', { method: 'POST', body: JSON.stringify(body) });
    if (body.text.trim() === MOCK_ERROR_TRIGGER) {
      await delay(null, 400);
      throw new ApiError({ code: 'mock_error', message: 'Simulated error for testing the UI.' });
    }
    return delay(buildMockAnswer(body), 900);
  },

  /** GET /meta/languages */
  async listLanguages(): Promise<MetaLanguage[]> {
    if (!USE_MOCKS) return request('/meta/languages');
    return delay(
      LANGUAGES.map((l) => ({ code: l.code, label: l.label, english_label: l.englishLabel })),
      100,
    );
  },

  /** GET /meta/states */
  async listStates(): Promise<StateOption[]> {
    if (!USE_MOCKS) return request('/meta/states');
    return delay(
      STATES.map((s) => ({ ...s, covered: s.code === COVERED_STATE_CODE })),
      100,
    );
  },

  /** GET /grievance/categories */
  async grievanceCategories(): Promise<GrievanceCategory[]> {
    if (!USE_MOCKS) return request('/grievance/categories');
    return delay(
      GRIEVANCE_CATEGORIES.map(({ id, label, description }) => ({ id, label, description })),
      100,
    );
  },

  /** POST /grievance/guide. Never files anything. */
  async grievanceGuide(body: GrievanceRequest): Promise<GrievanceGuide> {
    if (!USE_MOCKS) {
      return request('/grievance/guide', { method: 'POST', body: JSON.stringify(body) });
    }
    return delay(buildMockGuide(body), 800);
  },

  /** GET /schemes */
  async listSchemes(): Promise<Scheme[]> {
    if (!USE_MOCKS) return request('/schemes');
    return delay(MOCK_SCHEMES, 400);
  },

  /** GET /schemes/{slug}. `pmfby` carries the crop insurance guide facts. */
  async getScheme(slug: string): Promise<SchemeDetail> {
    if (!USE_MOCKS) return request(`/schemes/${encodeURIComponent(slug)}`);
    const scheme = MOCK_SCHEMES.find((s) => s.slug === slug);
    if (!scheme) {
      await delay(null, 200);
      throw new ApiError({ code: 'scheme_not_found', message: 'That scheme was not found.' });
    }
    return delay({ ...scheme, facts: slug === 'pmfby' ? CROP_FACTS : [] }, 400);
  },

  /**
   * GET /documents. Retired versions are included because the Library page filters on
   * the client; pass filters to narrow on the server.
   */
  async listDocuments(filters: DocumentFilters = {}): Promise<LibraryDocument[]> {
    if (!USE_MOCKS) {
      const query = toQuery({
        state: filters.state,
        language: filters.language,
        type: filters.doc_type || undefined,
        include_retired: 'true',
      });
      return request(`/documents${query}`);
    }
    return delay(MOCK_DOCUMENTS, 400);
  },

  /** GET /lessons. Falls back to English when there is no translation yet. */
  async listLessons(language: LanguageCode = 'en'): Promise<LessonsResponse> {
    if (!USE_MOCKS) return request(`/lessons${toQuery({ language })}`);
    return delay({ language: 'en', lessons: MOCK_LESSONS, quiz: MOCK_QUIZ }, 300);
  },

  /** POST /feedback. Mock mode keeps nothing; the UI shows local state only. */
  async sendFeedback(body: FeedbackRequest): Promise<{ ok: boolean; id?: number }> {
    if (!USE_MOCKS) return request('/feedback', { method: 'POST', body: JSON.stringify(body) });
    return delay({ ok: true }, 300);
  },

  /** GET /eval/latest. Staff only: log in at /admin/ first (session cookie). */
  async latestEval(): Promise<EvalSummary> {
    if (!USE_MOCKS) return request('/eval/latest');
    return delay(MOCK_EVAL_SUMMARY, 500);
  },

  /**
   * POST /speech/transcribe (multipart). Send the MediaRecorder blob; show the returned
   * text as an editable transcript before calling ask().
   */
  async transcribe(audio: Blob, languageHint?: LanguageCode): Promise<TranscribeResponse> {
    if (!USE_MOCKS) {
      const form = new FormData();
      form.append('audio', audio, 'question.webm');
      if (languageHint) form.append('language_hint', languageHint);
      const response = await send('/speech/transcribe', { method: 'POST', body: form });
      return (await response.json()) as TranscribeResponse;
    }
    return delay(
      {
        text: 'What should I do if my insured crop is damaged under PMFBY?',
        language: 'en',
        confidence: 0.9,
        is_demo: true,
      },
      700,
    );
  },

  /** POST /speech/synthesize. Returns WAV audio for the Listen button. */
  async synthesize(body: SynthesizeRequest): Promise<Blob> {
    if (!USE_MOCKS) {
      const response = await send('/speech/synthesize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'audio/wav' },
        body: JSON.stringify(body),
      });
      return response.blob();
    }
    return delay(silentWav(), 500);
  },
};
