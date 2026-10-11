import type { GrievanceCategory, GrievanceGuide, GrievanceRequest } from '@/types';
import { stateName } from './options';

/*
 * SAMPLE grievance guidance. Forums and steps are general patterns used to exercise
 * the UI; verified forums and contacts will come from forums.yaml (member C) through
 * POST /api/v1/grievance/guide. Nothing is ever filed automatically.
 */

export const GRIEVANCE_CATEGORIES: GrievanceCategory[] = [
  {
    id: 'deposit-refund',
    label: 'Deposit or share money not returned',
    description: 'The society has not refunded a deposit, share capital or dividend.',
    keywords: ['deposit', 'refund', 'share', 'dividend', 'money back'],
  },
  {
    id: 'membership',
    label: 'Membership refused or removed',
    description: 'You were refused membership or removed without a proper reason.',
    keywords: ['membership', 'member', 'expelled', 'removed', 'refused'],
  },
  {
    id: 'election',
    label: 'Election of the board',
    description: 'Concerns about how a board election was announced or conducted.',
    keywords: ['election', 'vote', 'board', 'director'],
  },
  {
    id: 'records',
    label: 'Accounts or records not shared',
    description: 'You asked to see accounts, audit reports or minutes and were refused.',
    keywords: ['accounts', 'audit', 'records', 'minutes', 'balance sheet'],
  },
  {
    id: 'loan',
    label: 'Loan or dues dispute',
    description: 'Disagreement about a loan, interest charged or dues recovered.',
    keywords: ['loan', 'interest', 'dues', 'recovery', 'kcc'],
  },
  {
    id: 'crop-insurance',
    label: 'Crop insurance claim',
    description: 'A PMFBY claim was delayed, rejected or wrongly calculated.',
    keywords: ['crop', 'insurance', 'pmfby', 'claim', 'bima'],
  },
];

export function detectCategory(description: string, hint?: string | null): GrievanceCategory {
  if (hint) {
    const chosen = GRIEVANCE_CATEGORIES.find((c) => c.id === hint);
    if (chosen) return chosen;
  }
  const text = description.toLowerCase();
  return (
    GRIEVANCE_CATEGORIES.find((c) => c.keywords.some((k) => text.includes(k))) ??
    GRIEVANCE_CATEGORIES[0]
  );
}

const FORUM_BY_CATEGORY: Record<string, { forum: string; note: string }> = {
  'crop-insurance': {
    forum: 'Insurance company grievance cell, then the district grievance committee (sample forum)',
    note: 'Sample forum. The verified PMFBY grievance route and helpline will be added from forums.yaml.',
  },
  default: {
    forum: 'Registrar of Co-operative Societies, district office (sample forum)',
    note: 'Sample forum. The exact authority depends on your state Act and will be confirmed from forums.yaml.',
  },
};

export function buildMockGuide(req: GrievanceRequest): GrievanceGuide {
  const category = detectCategory(req.description, req.category_hint);
  const forum = FORUM_BY_CATEGORY[category.id] ?? FORUM_BY_CATEGORY.default;
  const state = req.state ? stateName(req.state) : '[Your state]';

  const draft = `To,
${forum.forum.replace(' (sample forum)', '')}
${state}

Subject: Complaint regarding ${category.label.toLowerCase()}

Respected Sir/Madam,

I am a member of [name of cooperative society], [village/taluka], ${state}, with membership number [membership number].

${req.description.trim() || '[Describe what happened, with dates.]'}

I first raised this with the society on [date] but have not received a resolution. I request you to look into this matter and take appropriate action.

Copies of the relevant documents are enclosed.

Yours faithfully,
[Your name]
[Address]
[Date]`;

  return {
    category,
    forum: forum.forum,
    forum_note: forum.note,
    steps: [
      'Write to the secretary or board of your society first, and keep a dated copy or receipt.',
      'Wait for a reply for a reasonable period. Note the date if there is no response.',
      `If unresolved, send the complaint below to the ${forum.forum.replace(' (sample forum)', '')}.`,
      'Attach copies (never originals) of the documents in the checklist.',
      'Keep the acknowledgement or receipt number and follow up in person if needed.',
    ],
    documents_needed: [
      'Proof of membership (pass book or share certificate)',
      'Copy of your earlier letter to the society, with date',
      'Receipts, statements or notices related to the problem',
      'Any reply received from the society',
      'Identity proof (show only, do not leave originals)',
    ],
    draft_text: draft,
    is_demo: true,
  };
}
