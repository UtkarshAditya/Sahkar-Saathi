import type { CropFact, CropType, Season } from '@/types';

/*
 * PLACEHOLDER crop insurance facts, mirroring backend/data/schemes.yaml (pmfby). Premium
 * shares, deadlines and helpline numbers are deliberately NOT filled in. Member C adds
 * verified values with a source URL and date to schemes.yaml, served by
 * GET /api/v1/schemes/pmfby.
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

/** Facts that apply to the chosen season and crop type (null or absent means "all"). */
export function factsFor(facts: CropFact[], season: Season, crop: CropType): CropFact[] {
  return facts.filter(
    (f) => (!f.season || f.season === season) && (!f.crop_type || f.crop_type === crop),
  );
}

const PENDING = 'Pending: schemes.yaml (PMFBY)';

const placeholder = (
  id: string,
  kind: CropFact['kind'],
  title: string,
  body: string,
): CropFact => ({
  id,
  kind,
  title,
  body,
  source_label: PENDING,
  source_url: null,
  as_of: null,
  is_placeholder: true,
});

export const CROP_FACTS: CropFact[] = [
  placeholder(
    'eligibility',
    'eligibility',
    'Who can enrol',
    'Farmers growing notified crops in notified areas, including sharecroppers and tenant farmers, can generally enrol. The exact conditions will be quoted from the verified guidelines.',
  ),
  placeholder(
    'premium',
    'premium',
    'Your premium share',
    "The farmer's premium share for your season and crop type will appear here from the verified source. No figure is shown until it is verified.",
  ),
  placeholder(
    'enrolment',
    'enrolment',
    'How and where to enrol',
    'Farmers usually enrol through their bank, PACS, a common service centre or the insurance company. The enrolment window for this season will be added from the verified source.',
  ),
  placeholder(
    'loss',
    'loss-reporting',
    'Reporting crop loss',
    'Report a loss as early as possible to the insurance company, your bank or the agriculture office, with crop, area and cause. The exact reporting time limit will be quoted from the guidelines, not estimated.',
  ),
  placeholder(
    'official',
    'official-info',
    'Official information and helpline',
    'The official PMFBY portal and helpline number will be listed here once verified. Until then, ask your bank branch, PACS or district agriculture office.',
  ),
];
