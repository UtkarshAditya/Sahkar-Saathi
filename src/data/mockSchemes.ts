import type { Scheme, SchemeCategory } from '@/types';

/*
 * SAMPLE scheme cards for the UI. Titles name real programmes so the page reads
 * naturally, but summaries are simplified and eligibility and access steps are
 * placeholders. Verified text, source URLs and dates will come from schemes.yaml
 * (owned by member C) through GET /api/v1/schemes.
 */

export const SCHEME_CATEGORIES: { id: SchemeCategory; label: string }[] = [
  { id: 'cooperative-development', label: 'Cooperative development' },
  { id: 'credit', label: 'Credit' },
  { id: 'insurance', label: 'Insurance' },
  { id: 'storage-marketing', label: 'Storage & marketing' },
  { id: 'digital-services', label: 'Digital services' },
];

const SOURCE_PENDING = 'Official scheme page (link to be verified)';

export const MOCK_SCHEMES: Scheme[] = [
  {
    slug: 'pacs-computerisation',
    title: 'Computerisation of PACS',
    category: 'digital-services',
    summary:
      'Support for primary agricultural credit societies to move accounts and services onto a common software system.',
    eligibility: 'Placeholder: which PACS qualify will be quoted from the verified scheme note.',
    how_to_access:
      'Placeholder: steps will be added from the official source. Ask your PACS secretary or district cooperative office in the meantime.',
    source_label: SOURCE_PENDING,
    source_url: null,
    as_of: '2026-10-01',
    is_sample: true,
  },
  {
    slug: 'pacs-common-service-centres',
    title: 'PACS as Common Service Centres',
    category: 'digital-services',
    summary:
      'Lets PACS offer common digital services to villagers, such as applications and payments, from the society office.',
    eligibility: 'Placeholder: eligibility will be confirmed from the official source.',
    how_to_access: 'Placeholder: access steps will be added after verification.',
    source_label: SOURCE_PENDING,
    source_url: null,
    as_of: '2026-10-01',
    is_sample: true,
  },
  {
    slug: 'grain-storage-plan',
    title: 'Grain storage plan in the cooperative sector',
    category: 'storage-marketing',
    summary:
      'Builds storage and allied agri-infrastructure at the PACS level so members can store produce closer to home.',
    eligibility: 'Placeholder: which societies can take part will be quoted from the scheme note.',
    how_to_access: 'Placeholder: process to be added from the official source.',
    source_label: SOURCE_PENDING,
    source_url: null,
    as_of: '2026-10-01',
    is_sample: true,
  },
  {
    slug: 'kisan-credit-card',
    title: 'Kisan Credit Card (KCC)',
    category: 'credit',
    summary:
      'A credit facility that helps farmers meet crop and allied expenses, available through banks and cooperative credit institutions.',
    eligibility: 'Placeholder: eligibility and limits will be quoted from the verified source.',
    how_to_access: 'Placeholder: ask at your bank branch or PACS; exact steps to be verified.',
    source_label: SOURCE_PENDING,
    source_url: null,
    as_of: '2026-10-01',
    is_sample: true,
  },
  {
    slug: 'pmfby',
    title: 'Pradhan Mantri Fasal Bima Yojana (PMFBY)',
    category: 'insurance',
    summary:
      'Crop insurance that protects farmers against crop loss from natural risks. See the Crop insurance guide for step-by-step help.',
    eligibility:
      'Placeholder: see the Crop insurance guide; figures will be added after verification.',
    how_to_access: 'Placeholder: enrolment routes will be quoted from the verified guidelines.',
    source_label: SOURCE_PENDING,
    source_url: null,
    as_of: '2026-10-01',
    is_sample: true,
  },
  {
    slug: 'model-bylaws-pacs',
    title: 'Model by-laws for multipurpose PACS',
    category: 'cooperative-development',
    summary:
      'Model by-laws that states can adopt so PACS can take up more business activities beyond credit.',
    eligibility: 'Placeholder: adoption depends on each state; to be confirmed.',
    how_to_access:
      'Placeholder: open the Law library to see the document, or ask a question about it.',
    source_label: SOURCE_PENDING,
    source_url: null,
    as_of: '2026-10-01',
    is_sample: true,
  },
];
