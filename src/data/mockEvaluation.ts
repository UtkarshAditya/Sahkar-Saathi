import type { EvalRun, EvalSummary } from '@/types';

/*
 * SAMPLE evaluation numbers to lay out the dashboard. These are NOT real results.
 * Member B's eval runner will produce real runs, served by GET /api/v1/eval/latest
 * (staff token required).
 */

const RUNS: EvalRun[] = [
  {
    id: 'run-sample-1',
    run_at: '2026-10-17T18:00:00+05:30',
    label: 'Pilot configuration',
    config: {
      embedding_model: 'multilingual-e5-small',
      llm: 'model-a',
      top_k: 4,
      threshold: 0.5,
      prompt_version: 'v1',
    },
    hit_rate: 0.62,
    faithfulness: 0.7,
    correct_refusal: 0.55,
    questions: 40,
  },
  {
    id: 'run-sample-2',
    run_at: '2026-10-24T18:00:00+05:30',
    label: 'Full corpus configuration',
    config: {
      embedding_model: 'multilingual-e5-base',
      llm: 'model-a',
      top_k: 4,
      threshold: 0.55,
      prompt_version: 'v2',
    },
    hit_rate: 0.78,
    faithfulness: 0.84,
    correct_refusal: 0.8,
    questions: 80,
  },
  {
    id: 'run-sample-3',
    run_at: '2026-10-27T18:00:00+05:30',
    label: 'Tuned configuration',
    config: {
      embedding_model: 'bge-m3',
      llm: 'model-b',
      top_k: 4,
      threshold: 0.6,
      prompt_version: 'v3',
    },
    hit_rate: 0.86,
    faithfulness: 0.88,
    correct_refusal: 0.92,
    questions: 80,
  },
];

const latest = RUNS[RUNS.length - 1];

export const MOCK_EVAL_SUMMARY: EvalSummary = {
  latest,
  runs: RUNS,
  is_sample: true,
  // Targets from the architecture document, section 5.
  metrics: [
    {
      key: 'hit_rate',
      label: 'Retrieval hit rate',
      value: latest.hit_rate,
      target: 0.85,
      description: 'Correct passage in the top 4 results, over 80 questions.',
    },
    {
      key: 'faithfulness',
      label: 'Answer faithfulness',
      value: latest.faithfulness,
      target: 0.9,
      description: 'Every claim supported by the cited passage, manual check of 30 answers.',
    },
    {
      key: 'correct_refusal',
      label: 'Correct refusal',
      value: latest.correct_refusal,
      target: 0.9,
      description: 'Declines and redirects on 20 out-of-scope questions.',
    },
  ],
  failed_questions: [
    {
      id: 'fq-1',
      question: 'What is the quorum for a general body meeting?',
      language: 'hi',
      failure: 'retrieval-miss',
      note: 'Correct by-law section ranked 6th.',
    },
    {
      id: 'fq-2',
      question: 'Can a defaulting member contest the board election?',
      language: 'en',
      failure: 'wrong-state',
      note: 'Answered from central Act; state not asked.',
    },
    {
      id: 'fq-3',
      question: 'How much premium do I pay for cotton?',
      language: 'ta',
      failure: 'unfaithful',
      note: 'Number in answer not present in cited passage.',
    },
    {
      id: 'fq-4',
      question: 'Which lawyer should I hire for my case?',
      language: 'en',
      failure: 'should-decline',
      note: 'Gave general advice instead of declining.',
    },
  ],
};
