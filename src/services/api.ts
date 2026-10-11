/**
 * API client for /api/v1. One function per endpoint in the architecture contract.
 *
 * While VITE_USE_MOCKS is "true" (the default), every function resolves local mock
 * data after a short delay so loading states are visible. No network calls are made.
 * When the backend exists, set VITE_USE_MOCKS=false; the `request` helper then calls
 * the real endpoints. Speech endpoints are intentionally not implemented yet.
 */
import { buildMockAnswer } from '@/data/mockChat';
import { MOCK_DOCUMENTS } from '@/data/mockDocuments';
import { MOCK_EVAL_SUMMARY } from '@/data/mockEvaluation';
import { buildMockGuide } from '@/data/mockGrievance';
import { MOCK_LESSONS } from '@/data/mockLessons';
import { MOCK_SCHEMES } from '@/data/mockSchemes';
import type {
  ApiErrorBody,
  AskRequest,
  AskResponse,
  DocumentFilters,
  EvalSummary,
  FeedbackRequest,
  GrievanceGuide,
  GrievanceRequest,
  LibraryDocument,
  Lesson,
  Scheme,
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    ...init,
  });
  if (!response.ok) {
    let body: ApiErrorBody = { code: `http_${response.status}`, message: response.statusText };
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      // Keep the status-based error when the body is not JSON.
    }
    throw new ApiError(body);
  }
  return (await response.json()) as T;
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

  /** POST /grievance/guide */
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

  /** GET /documents */
  async listDocuments(filters: DocumentFilters = {}): Promise<LibraryDocument[]> {
    if (!USE_MOCKS) {
      return request(
        `/documents${toQuery({ state: filters.state, language: filters.language, type: filters.doc_type || undefined })}`,
      );
    }
    return delay(MOCK_DOCUMENTS, 400);
  },

  /** GET /lessons */
  async listLessons(): Promise<Lesson[]> {
    if (!USE_MOCKS) return request('/lessons');
    return delay(MOCK_LESSONS, 300);
  },

  /** POST /feedback. Mock mode keeps nothing; the UI shows local state only. */
  async sendFeedback(body: FeedbackRequest): Promise<{ ok: true }> {
    if (!USE_MOCKS) return request('/feedback', { method: 'POST', body: JSON.stringify(body) });
    return delay({ ok: true as const }, 300);
  },

  /** GET /eval/latest (staff token, to be added by member A). */
  async latestEval(): Promise<EvalSummary> {
    if (!USE_MOCKS) return request('/eval/latest');
    return delay(MOCK_EVAL_SUMMARY, 500);
  },

  /** POST /speech/transcribe and /speech/synthesize: planned for Sprint 2. */
  async transcribe(): Promise<never> {
    throw new ApiError({ code: 'not_implemented', message: 'Speech input is not connected yet.' });
  },
  async synthesize(): Promise<never> {
    throw new ApiError({ code: 'not_implemented', message: 'Speech output is not connected yet.' });
  },
};
