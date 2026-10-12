/**
 * Shared types.
 *
 * API-shaped types use the snake_case field names from the API contract in the
 * architecture document (section 4). Once the backend freezes openapi.json, generate
 * types with openapi-typescript and re-export the generated ones from here, so the
 * front end cannot drift from the contract.
 */

/* ----- Settings ----- */

/** 'en', 'hi' or the configured regional code. */
export type LanguageCode = string;

export interface LanguageOption {
  code: LanguageCode;
  /** Name in its own script, e.g. "हिन्दी". */
  label: string;
  /** Name in English, for staff and screen readers. */
  englishLabel: string;
}

export interface StateOption {
  code: string;
  name: string;
}

/* ----- Chat (/chat/ask) ----- */

export type AnswerStatus = 'answered' | 'partial' | 'declined';

export interface Citation {
  id: string;
  document_id: string;
  title: string;
  publisher: string;
  published_date: string;
  page: number | null;
  section?: string;
  /** Null until a verified source URL is recorded for the document. */
  url: string | null;
  excerpt?: string;
}

export interface Contact {
  label: string;
  detail: string;
}

export interface AskRequest {
  conversation_id: string | null;
  text: string;
  language: LanguageCode;
  state: string | null;
  /** Limits retrieval to one library document ("Ask about this document"). */
  document_id?: string | null;
}

export interface AskResponse {
  conversation_id: string;
  message_id: string;
  answer_text: string;
  status: AnswerStatus;
  needs_state: boolean;
  citations: Citation[];
  followups: string[];
  /** Declined answers name who to contact instead. */
  contact?: Contact;
  /** True for mock or cached demo answers. */
  is_demo: boolean;
}

export type ChatRole = 'user' | 'assistant';

export interface ChatMessage {
  id: string;
  role: ChatRole;
  text: string;
  /** Present on assistant messages. */
  response?: AskResponse;
  /** For needs_state prompts: the question to re-ask once a state is chosen. */
  pendingQuestion?: string;
  /** Part of the built-in example conversation: never sent to or stored by the API. */
  isExample?: boolean;
}

export type QuestionTopic = 'law' | 'pmfby' | 'schemes' | 'grievance';

export interface SuggestedQuestion {
  id: string;
  topic: QuestionTopic;
  text: string;
}

/* ----- Speech (/speech/transcribe, /speech/synthesize) ----- */

export interface TranscribeResponse {
  /** Show as an editable transcript before sending to /chat/ask. */
  text: string;
  language: LanguageCode;
  /** 0..1 */
  confidence: number;
  is_demo: boolean;
}

export interface SynthesizeRequest {
  text: string;
  language: LanguageCode;
}

/* ----- Feedback (/feedback) ----- */

export type FeedbackRating = 'up' | 'down';

export interface FeedbackRequest {
  message_id: string | null;
  rating: FeedbackRating | null;
  comment: string;
  reason?: string;
}

/* ----- Grievance (/grievance/guide) ----- */

export interface GrievanceCategory {
  id: string;
  label: string;
  description: string;
  keywords: string[];
}

export interface GrievanceRequest {
  description: string;
  state: string | null;
  category_hint?: string | null;
}

export interface GrievanceGuide {
  category: GrievanceCategory;
  forum: string;
  forum_note: string;
  steps: string[];
  documents_needed: string[];
  draft_text: string;
  is_demo: boolean;
}

/* ----- Schemes (/schemes) ----- */

export type SchemeCategory =
  'cooperative-development' | 'credit' | 'insurance' | 'storage-marketing' | 'digital-services';

export interface Scheme {
  slug: string;
  title: string;
  category: SchemeCategory;
  summary: string;
  eligibility: string;
  how_to_access: string;
  source_label: string;
  source_url: string | null;
  as_of: string;
  is_sample: boolean;
}

/* ----- Crop insurance guide (/schemes/pmfby) ----- */

export type Season = 'kharif' | 'rabi' | 'commercial';
export type CropType = 'food' | 'oilseed' | 'horticulture';

export type CropFactKind =
  'eligibility' | 'enrolment' | 'premium' | 'loss-reporting' | 'official-info';

export interface CropFact {
  id: string;
  kind: CropFactKind;
  title: string;
  body: string;
  source_label: string;
  source_url: string | null;
  as_of: string | null;
  /** True when the value waits for a verified figure. */
  is_placeholder: boolean;
}

/* ----- Law library (/documents) ----- */

export type DocumentType = 'act' | 'rules' | 'model-bylaws' | 'circular' | 'scheme-guideline';
export type DocumentStatus = 'active' | 'retired';

export interface LibraryDocument {
  id: string;
  title: string;
  publisher: string;
  doc_type: DocumentType;
  /** 'central' for national documents, otherwise a state code. */
  state: string;
  language: LanguageCode;
  published_date: string;
  version: string;
  status: DocumentStatus;
  source_url: string | null;
  is_sample: boolean;
}

export interface DocumentFilters {
  search?: string;
  state?: string;
  language?: string;
  doc_type?: DocumentType | '';
}

/* ----- Lessons (/lessons) ----- */

export type LessonIcon = 'loan' | 'card' | 'savings' | 'fraud';

export interface Lesson {
  slug: string;
  title: string;
  summary: string;
  reading_minutes: number;
  icon: LessonIcon;
  sections: { heading: string; body: string }[];
  key_points: string[];
}

export interface QuizQuestion {
  id: string;
  question: string;
  options: string[];
  correct_index: number;
  explanation: string;
}

/* ----- Evaluation (/eval/latest) ----- */

export type EvalMetricKey = 'hit_rate' | 'faithfulness' | 'correct_refusal';

export interface EvalMetric {
  key: EvalMetricKey;
  label: string;
  /** 0..1 */
  value: number;
  /** 0..1 */
  target: number;
  description: string;
}

export interface EvalRun {
  id: string;
  run_at: string;
  label: string;
  config: {
    embedding_model: string;
    llm: string;
    top_k: number;
    threshold: number;
    prompt_version: string;
  };
  hit_rate: number;
  faithfulness: number;
  correct_refusal: number;
  questions: number;
}

export type FailureKind = 'retrieval-miss' | 'unfaithful' | 'should-decline' | 'wrong-state';

export interface FailedQuestion {
  id: string;
  question: string;
  language: LanguageCode;
  failure: FailureKind;
  note: string;
}

export interface EvalSummary {
  latest: EvalRun;
  metrics: EvalMetric[];
  runs: EvalRun[];
  failed_questions: FailedQuestion[];
  is_sample: boolean;
}

/* ----- Errors ----- */

/** Every API error uses this one shape. */
export interface ApiErrorBody {
  code: string;
  message: string;
}
