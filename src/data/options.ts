import type {
  CropFact,
  CropType,
  DocumentType,
  SchemeCategory,
  Season,
  StateOption,
} from '@/types';

/**
 * Options for the state selector. The backend will serve this from /meta/states.
 * The knowledge base covers the central documents plus one chosen state; the rest
 * are listed so the selector is complete, and answers say when a state is not covered.
 */
export const STATES: StateOption[] = [
  { code: 'AN', name: 'Andaman and Nicobar Islands' },
  { code: 'AP', name: 'Andhra Pradesh' },
  { code: 'AR', name: 'Arunachal Pradesh' },
  { code: 'AS', name: 'Assam' },
  { code: 'BR', name: 'Bihar' },
  { code: 'CH', name: 'Chandigarh' },
  { code: 'CT', name: 'Chhattisgarh' },
  { code: 'DH', name: 'Dadra and Nagar Haveli and Daman and Diu' },
  { code: 'DL', name: 'Delhi' },
  { code: 'GA', name: 'Goa' },
  { code: 'GJ', name: 'Gujarat' },
  { code: 'HR', name: 'Haryana' },
  { code: 'HP', name: 'Himachal Pradesh' },
  { code: 'JK', name: 'Jammu and Kashmir' },
  { code: 'JH', name: 'Jharkhand' },
  { code: 'KA', name: 'Karnataka' },
  { code: 'KL', name: 'Kerala' },
  { code: 'LA', name: 'Ladakh' },
  { code: 'LD', name: 'Lakshadweep' },
  { code: 'MP', name: 'Madhya Pradesh' },
  { code: 'MH', name: 'Maharashtra' },
  { code: 'MN', name: 'Manipur' },
  { code: 'ML', name: 'Meghalaya' },
  { code: 'MZ', name: 'Mizoram' },
  { code: 'NL', name: 'Nagaland' },
  { code: 'OD', name: 'Odisha' },
  { code: 'PY', name: 'Puducherry' },
  { code: 'PB', name: 'Punjab' },
  { code: 'RJ', name: 'Rajasthan' },
  { code: 'SK', name: 'Sikkim' },
  { code: 'TN', name: 'Tamil Nadu' },
  { code: 'TG', name: 'Telangana' },
  { code: 'TR', name: 'Tripura' },
  { code: 'UP', name: 'Uttar Pradesh' },
  { code: 'UK', name: 'Uttarakhand' },
  { code: 'WB', name: 'West Bengal' },
];

/** The one state whose Act and rules are in the knowledge base (team decision). */
export const COVERED_STATE_CODE = 'TN';

export function stateName(code: string | null | undefined): string {
  if (!code) return '';
  if (code === 'central') return 'Central (all states)';
  return STATES.find((s) => s.code === code)?.name ?? code;
}

export const SCHEME_CATEGORIES: { id: SchemeCategory; label: string }[] = [
  { id: 'cooperative-development', label: 'Cooperative development' },
  { id: 'credit', label: 'Credit' },
  { id: 'insurance', label: 'Insurance' },
  { id: 'storage-marketing', label: 'Storage & marketing' },
  { id: 'digital-services', label: 'Digital services' },
];

export const DOCUMENT_TYPES: { id: DocumentType; label: string }[] = [
  { id: 'act', label: 'Act' },
  { id: 'rules', label: 'Rules' },
  { id: 'model-bylaws', label: 'Model by-laws' },
  { id: 'circular', label: 'Circular' },
  { id: 'scheme-guideline', label: 'Scheme guideline' },
];

export function documentTypeLabel(type: DocumentType): string {
  return DOCUMENT_TYPES.find((documentType) => documentType.id === type)?.label ?? type;
}

export const SEASONS: { id: Season; label: string }[] = [
  { id: 'kharif', label: 'Kharif (monsoon season)' },
  { id: 'rabi', label: 'Rabi (winter season)' },
  { id: 'commercial', label: 'Annual commercial or horticultural' },
];

export const CROP_TYPES: { id: CropType; label: string }[] = [
  { id: 'food', label: 'Food crops (cereals, millets, pulses)' },
  { id: 'oilseed', label: 'Oilseeds' },
  { id: 'horticulture', label: 'Commercial or horticultural crops' },
];

export function factsFor(facts: CropFact[], season: Season, crop: CropType): CropFact[] {
  return facts.filter(
    (fact) =>
      (!fact.season || fact.season === season) && (!fact.crop_type || fact.crop_type === crop),
  );
}
