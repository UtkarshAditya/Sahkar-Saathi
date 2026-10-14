import { useId, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import {
  CircleCheck,
  ClipboardList,
  CloudRain,
  Globe,
  MessageSquareText,
  Sprout,
  Wallet,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Card } from '@/components/common/Card';
import { Notice } from '@/components/common/Notice';
import { PageHeader } from '@/components/common/PageHeader';
import { SourceMeta } from '@/components/common/SourceMeta';
import { ErrorState, LoadingState } from '@/components/common/EmptyState';
import { CROP_TYPES, factsFor, SEASONS } from '@/data/mockCropInsurance';
import { useAsync } from '@/hooks/useAsync';
import { api } from '@/services/api';
import type { CropFactKind, CropType, Season } from '@/types';

const FACT_ICONS: Record<CropFactKind, typeof Sprout> = {
  eligibility: CircleCheck,
  premium: Wallet,
  enrolment: ClipboardList,
  'loss-reporting': CloudRain,
  'official-info': Globe,
};

export default function CropInsurancePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const seasonId = useId();
  const cropId = useId();
  const [season, setSeason] = useState<Season>('kharif');
  const [crop, setCrop] = useState<CropType>('food');

  const { data: pmfby, loading, error, reload } = useAsync(() => api.getScheme('pmfby'));
  const facts = useMemo(() => factsFor(pmfby?.facts ?? [], season, crop), [pmfby, season, crop]);
  const seasonLabel = SEASONS.find((s) => s.id === season)?.label ?? '';
  const cropLabel = CROP_TYPES.find((c) => c.id === crop)?.label ?? '';

  function askFollowUp() {
    const q = `Under PMFBY, what should I know about insuring ${cropLabel.toLowerCase()} in the ${seasonLabel.toLowerCase()}?`;
    navigate(`/?q=${encodeURIComponent(q)}`);
  }

  return (
    <>
      <PageHeader
        title={t('pages.cropInsurance.title')}
        description={t('pages.cropInsurance.description')}
        icon={<Sprout className="size-6" aria-hidden />}
        breadcrumbs={[{ label: t('nav.groups.guides') }]}
        badges={<Badge tone="saffron">{t('common.placeholder')}: figures not yet verified</Badge>}
        actions={
          <Button onClick={askFollowUp} icon={<MessageSquareText className="size-5" aria-hidden />}>
            Ask a follow-up
          </Button>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[20rem_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          <Card as="section" aria-labelledby="pmfby-intro">
            <h2 id="pmfby-intro" className="text-lg font-semibold">
              About PMFBY
            </h2>
            <p className="mt-2 text-ink-soft">
              Pradhan Mantri Fasal Bima Yojana is the government’s crop insurance scheme. It helps
              protect farmers against crop loss from natural risks such as drought, flood, pests and
              disease.
            </p>
          </Card>

          <Card as="section" aria-labelledby="choose-crop">
            <h2 id="choose-crop" className="mb-3 text-lg font-semibold">
              Your season and crop
            </h2>
            <div className="flex flex-col gap-4">
              <div>
                <label htmlFor={seasonId} className="field-label">
                  Season
                </label>
                <select
                  id={seasonId}
                  className="field-input"
                  value={season}
                  onChange={(e) => setSeason(e.target.value as Season)}
                >
                  {SEASONS.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor={cropId} className="field-label">
                  Crop type
                </label>
                <select
                  id={cropId}
                  className="field-input"
                  value={crop}
                  onChange={(e) => setCrop(e.target.value as CropType)}
                >
                  {CROP_TYPES.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </Card>

          <Notice tone="warning" title="No numbers until verified">
            Premium shares, deadlines and helpline numbers are left blank on purpose. They will be
            added from the official guidelines, each with its source and date.
          </Notice>
        </div>

        <section aria-labelledby="facts-heading">
          <h2 id="facts-heading" className="mb-1 text-lg font-semibold">
            What to know
          </h2>
          <p className="mb-4 text-sm text-ink-muted" aria-live="polite">
            Showing: {seasonLabel} · {cropLabel}
          </p>
          {loading && <LoadingState />}
          {error && <ErrorState message={error.message} onRetry={reload} />}
          <ul className="grid gap-4 md:grid-cols-2">
            {facts.map((fact) => {
              const Icon = FACT_ICONS[fact.kind];
              return (
                <li key={fact.id}>
                  <Card as="article" className="flex h-full flex-col">
                    <div className="mb-3 flex items-start justify-between gap-2">
                      <span className="flex items-center gap-2">
                        <span className="flex size-10 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
                          <Icon className="size-5" aria-hidden />
                        </span>
                        <h3 className="font-semibold">{fact.title}</h3>
                      </span>
                      {fact.is_placeholder && (
                        <Badge tone="saffron">{t('common.placeholder')}</Badge>
                      )}
                    </div>
                    <p className="flex-1 text-ink-soft">{fact.body}</p>
                    <div className="mt-4 border-t border-line pt-3">
                      <SourceMeta
                        sourceLabel={fact.source_label}
                        sourceUrl={fact.source_url}
                        asOf={fact.as_of}
                      />
                    </div>
                  </Card>
                </li>
              );
            })}
          </ul>
          <div className="mt-6 flex flex-col items-start gap-3 rounded-2xl border border-brand-200 bg-brand-50 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-semibold text-brand-900">Still have a question about your crop?</p>
              <p className="text-sm text-ink-soft">
                We’ll open Ask with your season and crop filled in.
              </p>
            </div>
            <Button
              onClick={askFollowUp}
              icon={<MessageSquareText className="size-5" aria-hidden />}
            >
              Ask a follow-up
            </Button>
          </div>
        </section>
      </div>
    </>
  );
}
