import type { AskRequest, AskResponse, ChatMessage, Citation } from '@/types';
import { makeId } from '@/lib/format';
import { COVERED_STATE_CODE, stateName } from './options';
import { SUGGESTED_QUESTIONS } from './suggestedQuestions';

/* Local fixture responses used only when VITE_USE_MOCKS is enabled. */

const PMFBY_CITATIONS: Citation[] = [
  {
    id: 'cit-pmfby-1',
    document_id: 'doc-pmfby-guidelines',
    title: 'PMFBY Operational Guidelines',
    publisher: '',
    published_date: '2026-01-15',
    page: 34,
    section: 'Localised calamities',
    url: null,
  },
];

function lawCitations(stateCode: string): Citation[] {
  return [
    {
      id: 'cit-law-1',
      document_id: stateCode === COVERED_STATE_CODE ? 'doc-tn-act' : 'doc-mscs-act',
      title:
        stateCode === COVERED_STATE_CODE
          ? 'Tamil Nadu Co-operative Societies Act, 1983'
          : 'Multi-State Co-operative Societies Act, 2002',
      publisher: '',
      published_date: '2024-03-01',
      page: 18,
      section: 'Management of societies',
      url: null,
    },
    {
      id: 'cit-law-2',
      document_id: 'doc-model-bylaws-en',
      title: 'Model Bye-laws for PACS',
      publisher: '',
      published_date: '2023-01-05',
      page: 12,
      section: 'Board of directors',
      url: null,
    },
  ];
}

const DEFAULT_CONTACT = {
  label: 'Your district cooperative office (Registrar of Co-operative Societies)',
  detail: '',
};

const LAW_WORDS = [
  'by-law',
  'bylaw',
  'bye-law',
  'board',
  'election',
  'elect',
  'member',
  'society',
  'pacs',
  'audit',
  'accounts',
];
const PMFBY_WORDS = ['pmfby', 'crop', 'insurance', 'fasal', 'bima', 'claim', 'damage'];
const SCHEME_WORDS = [
  'scheme',
  'yojana',
  'computeris',
  'computeriz',
  'storage',
  'kcc',
  'credit card',
];
const GRIEVANCE_WORDS = ['complain', 'grievance', 'refund', 'deposit', 'dispute', 'not paid'];
const OUT_OF_SCOPE_WORDS = ['win my', 'will i win', 'court case', 'predict', 'stock', 'cricket'];

function includesAny(text: string, words: string[]): boolean {
  return words.some((w) => text.includes(w));
}

/** Rule-based stand-in for the agent. Mirrors the shape of POST /chat/ask. */
export function buildMockAnswer(req: AskRequest): AskResponse {
  const text = req.text.toLowerCase();
  const base = {
    conversation_id: req.conversation_id ?? makeId('conv'),
    message_id: makeId('msg'),
    is_demo: true,
  };

  if (includesAny(text, OUT_OF_SCOPE_WORDS)) {
    return {
      ...base,
      status: 'declined',
      needs_state: false,
      answer_text:
        'I can explain what public cooperative documents say, but I cannot predict the outcome of a dispute or answer questions outside cooperative governance, schemes and member services.',
      citations: [],
      followups: ['Where can I file a complaint against my cooperative society?'],
      contact: DEFAULT_CONTACT,
    };
  }

  if (includesAny(text, PMFBY_WORDS)) {
    return {
      ...base,
      status: 'answered',
      needs_state: false,
      answer_text:
        'Under PMFBY, a farmer whose insured crop is damaged should report the loss as early as possible to the insurance company, their bank or the local agriculture office, with details of the crop, area and cause of loss.',
      citations: PMFBY_CITATIONS,
      followups: [
        'Which documents do I need for a crop loss claim?',
        'How do I check the status of my PMFBY claim?',
      ],
    };
  }

  if (includesAny(text, GRIEVANCE_WORDS)) {
    return {
      ...base,
      status: 'partial',
      needs_state: false,
      answer_text:
        'Complaints about a cooperative society usually start with a written request to the society itself, and can then go to the Registrar of Co-operative Societies for your district. Use the Grievance helper to get the steps, a documents checklist and a draft you can edit.',
      citations: lawCitations(req.state ?? 'central').slice(0, 1),
      followups: ['Open the Grievance helper', 'What documents should I keep for a complaint?'],
    };
  }

  if (includesAny(text, SCHEME_WORDS)) {
    return {
      ...base,
      status: 'answered',
      needs_state: false,
      answer_text:
        'The Schemes and services page lists programmes for cooperatives, such as PACS computerisation and PACS working as service centres. Each card shows any available source and date.',
      citations: [
        {
          id: 'cit-scheme-1',
          document_id: 'doc-circular-pacs',
          title: 'Scheme note: Computerisation of PACS',
          publisher: '',
          published_date: '2025-06-10',
          page: 2,
          url: null,
        },
      ],
      followups: ['Who can apply for PACS computerisation support?'],
    };
  }

  if (includesAny(text, LAW_WORDS)) {
    if (!req.state) {
      return {
        ...base,
        status: 'partial',
        needs_state: true,
        answer_text:
          'Cooperative law differs by state. Tell me which state your society is registered in, and I will answer from that state’s Act and the model by-laws.',
        citations: [],
        followups: [],
      };
    }
    const covered = req.state === COVERED_STATE_CODE;
    return {
      ...base,
      status: covered ? 'answered' : 'partial',
      needs_state: false,
      answer_text: covered
        ? `In ${stateName(req.state)}, board members of a cooperative society are generally elected by its members at the general body meeting, following the election rules in the state Act and the society’s registered by-laws. Check your society’s own by-laws for the exact number of seats and the term.`
        : `${stateName(req.state)} is not covered by the current knowledge base, so this answer uses only the central documents and the model by-laws. Check your state’s Co-operative Societies Act for the exact rules.`,
      citations: lawCitations(req.state),
      followups: [
        'Who conducts elections in a cooperative society?',
        'Can a member see the minutes of the general body meeting?',
      ],
    };
  }

  return {
    ...base,
    status: 'declined',
    needs_state: false,
    answer_text:
      'I could not find this in my sources, so I will not guess. Try rephrasing, or contact the office below.',
    citations: [],
    followups: SUGGESTED_QUESTIONS.slice(0, 2).map((q) => q.text),
    contact: DEFAULT_CONTACT,
  };
}

/** A pre-filled example conversation showing the answered, declined and ask-state states. */
export function buildDemoConversation(): ChatMessage[] {
  const q1 = SUGGESTED_QUESTIONS[2].text;
  const q2 = 'Will I win my land dispute case against the society?';
  const q3 = SUGGESTED_QUESTIONS[0].text;
  const ask = (text: string): AskRequest => ({
    conversation_id: 'conv-demo',
    text,
    language: 'en',
    state: null,
  });
  const messages: ChatMessage[] = [
    { id: 'demo-u1', role: 'user', text: q1 },
    { id: 'demo-a1', role: 'assistant', text: '', response: buildMockAnswer(ask(q1)) },
    { id: 'demo-u2', role: 'user', text: q2 },
    { id: 'demo-a2', role: 'assistant', text: '', response: buildMockAnswer(ask(q2)) },
    { id: 'demo-u3', role: 'user', text: q3 },
    {
      id: 'demo-a3',
      role: 'assistant',
      text: '',
      response: buildMockAnswer(ask(q3)),
      pendingQuestion: q3,
    },
  ];
  return messages.map((m) => ({ ...m, isExample: true }));
}
