/**
 * Compile-time contract check. `npm run build` (tsc) fails if the hand-written types in
 * ./index.ts drift from the frozen API contract in backend/openapi.json.
 *
 * - Responses: what the API returns must fit the type the UI reads.
 * - Requests: what the UI sends must fit what the API accepts.
 *
 * After a contract change: `npm run gen:api`, then fix whatever this file reports.
 */
import type { components } from './api.gen';
import type {
  AskRequest,
  AskResponse,
  EvalSummary,
  FeedbackRequest,
  GrievanceCategory,
  GrievanceGuide,
  GrievanceRequest,
  LessonsResponse,
  LibraryDocument,
  MetaLanguage,
  Scheme,
  SchemeDetail,
  StateOption,
  SynthesizeRequest,
  TranscribeResponse,
} from './index';

type S = components['schemas'];
type Fits<A, B> = [A] extends [B] ? true : false;
type Assert<T extends true> = T;

export type ContractChecks = [
  // Responses: contract -> UI type
  Assert<Fits<S['AskOut'], AskResponse>>,
  Assert<Fits<S['TranscriptOut'], TranscribeResponse>>,
  Assert<Fits<S['GrievanceCategoryOut'], GrievanceCategory>>,
  Assert<Fits<S['GrievanceGuideOut'], GrievanceGuide>>,
  Assert<Fits<S['SchemeOut'], Scheme>>,
  Assert<Fits<S['SchemeDetailOut'], SchemeDetail>>,
  Assert<Fits<S['LessonsOut'], LessonsResponse>>,
  Assert<Fits<S['DocumentOut'], LibraryDocument>>,
  Assert<Fits<S['LanguageOut'], MetaLanguage>>,
  Assert<Fits<S['StateOut'], StateOption>>,
  Assert<Fits<S['EvalSummaryOut'], EvalSummary>>,
  // Requests: UI type -> contract
  Assert<Fits<AskRequest, S['AskIn']>>,
  Assert<Fits<SynthesizeRequest, S['SynthesizeIn']>>,
  Assert<Fits<FeedbackRequest, S['FeedbackIn']>>,
  Assert<Fits<GrievanceRequest, S['GrievanceIn']>>,
];
