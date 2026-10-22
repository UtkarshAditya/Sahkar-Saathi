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

const SOURCE_PENDING = 'Source: being added';

export const MOCK_SCHEMES: Scheme[] = [
  {
    slug: 'pacs-computerisation',
    title: 'Computerisation of PACS',
    category: 'digital-services',
    summary:
      'Support for primary agricultural credit societies to move accounts and services onto a common software system.',
    eligibility: 'Eligibility details are being added from the official scheme guidance.',
    how_to_access:
      'Access steps are being added from the official source. Ask your PACS secretary or district cooperative office for current guidance.',
    source_label: SOURCE_PENDING,
    source_url: null,
    as_of: '',
    is_sample: true,
  },
  {
    slug: 'pacs-common-service-centres',
    title: 'PACS as Common Service Centres',
    category: 'digital-services',
    summary:
      'Lets PACS offer common digital services to villagers, such as applications and payments, from the society office.',
    eligibility: 'Eligibility details are being added from the official source.',
    how_to_access: 'Access steps are being added from the official source.',
    source_label: SOURCE_PENDING,
    source_url: null,
    as_of: '',
    is_sample: true,
  },
  {
    slug: 'grain-storage-plan',
    title: 'Grain storage plan in the cooperative sector',
    category: 'storage-marketing',
    summary:
      'Builds storage and allied agri-infrastructure at the PACS level so members can store produce closer to home.',
    eligibility: 'Eligibility details are being added from the scheme guidance.',
    how_to_access: 'The application process is being added from the official source.',
    source_label: SOURCE_PENDING,
    source_url: null,
    as_of: '',
    is_sample: true,
  },
  {
    slug: 'kisan-credit-card',
    title: 'Kisan Credit Card (KCC)',
    category: 'credit',
    summary:
      'A credit facility that helps farmers meet crop and allied expenses, available through banks and cooperative credit institutions.',
    eligibility: 'Eligibility and credit limits are being added from the official source.',
    how_to_access:
      'Ask at your bank branch or PACS while the current access steps are being added.',
    source_label: SOURCE_PENDING,
    source_url: null,
    as_of: '',
    is_sample: true,
  },
  {
    slug: 'pmfby',
    title: 'Pradhan Mantri Fasal Bima Yojana (PMFBY)',
    category: 'insurance',
    summary:
      'Crop insurance that protects farmers against crop loss from natural risks. See the Crop insurance guide for step-by-step help.',
    eligibility: 'See the Crop insurance guide. Current eligibility details are being added.',
    how_to_access: 'Enrolment routes are being added from the official guidelines.',
    source_label: SOURCE_PENDING,
    source_url: null,
    as_of: '',
    is_sample: true,
  },
  {
    slug: 'model-bylaws-pacs',
    title: 'Model by-laws for multipurpose PACS',
    category: 'cooperative-development',
    summary:
      'Model by-laws that states can adopt so PACS can take up more business activities beyond credit.',
    eligibility: 'Adoption depends on each state. Further details are being added.',
    how_to_access: 'Open the Law library to see related documents, or ask a question about them.',
    source_label: SOURCE_PENDING,
    source_url: null,
    as_of: '',
    is_sample: true,
  },
];
