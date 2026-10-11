import type { CropFact, CropType, Season } from '@/types';

/*
 * PLACEHOLDER crop insurance facts. Premium shares, deadlines and helpline numbers
 * are deliberately NOT filled in. Member C adds verified values with a source URL
 * and date to schemes.yaml, served by GET /api/v1/schemes/pmfby.
 */

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

const PENDING = 'Pending: schemes.yaml (PMFBY)';

export function getCropFacts(season: Season, crop: CropType): CropFact[] {
  const seasonLabel = SEASONS.find((s) => s.id === season)?.label ?? season;
  const cropLabel = CROP_TYPES.find((c) => c.id === crop)?.label ?? crop;

  return [
    {
      id: 'eligibility',
      kind: 'eligibility',
      title: 'Who can enrol',
      body: 'Farmers growing notified crops in notified areas, including sharecroppers and tenant farmers, can generally enrol. The exact conditions will be quoted from the verified guidelines.',
      source_label: PENDING,
      source_url: null,
      as_of: null,
      is_placeholder: true,
    },
    {
      id: 'premium',
      kind: 'premium',
      title: 'Your premium share',
      body: `The farmer's premium share for ${cropLabel.toLowerCase()} in the ${seasonLabel.toLowerCase()} will appear here from the verified source. No figure is shown until it is verified.`,
      source_label: PENDING,
      source_url: null,
      as_of: null,
      is_placeholder: true,
    },
    {
      id: 'enrolment',
      kind: 'enrolment',
      title: 'How and where to enrol',
      body: 'Farmers usually enrol through their bank, PACS, a common service centre or the insurance company. The enrolment window for this season will be added from the verified source.',
      source_label: PENDING,
      source_url: null,
      as_of: null,
      is_placeholder: true,
    },
    {
      id: 'loss',
      kind: 'loss-reporting',
      title: 'Reporting crop loss',
      body: 'Report a loss as early as possible to the insurance company, your bank or the agriculture office, with crop, area and cause. The exact reporting time limit will be quoted from the guidelines, not estimated.',
      source_label: PENDING,
      source_url: null,
      as_of: null,
      is_placeholder: true,
    },
    {
      id: 'official',
      kind: 'official-info',
      title: 'Official information and helpline',
      body: 'The official PMFBY portal and helpline number will be listed here once verified. Until then, ask your bank branch, PACS or district agriculture office.',
      source_label: PENDING,
      source_url: null,
      as_of: null,
      is_placeholder: true,
    },
  ];
}
