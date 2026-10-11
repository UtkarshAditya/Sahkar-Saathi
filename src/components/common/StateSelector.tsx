import { useId } from 'react';
import { MapPin } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { COVERED_STATE_CODE, STATES } from '@/data/options';
import { useSettings } from '@/hooks/useSettings';

interface StateSelectorProps {
  /** Override the shared setting (e.g. a local form field). Defaults to the shared state. */
  value?: string | null;
  onChange?: (code: string | null) => void;
  label?: string;
  showHint?: boolean;
  className?: string;
}

export function StateSelector({
  value,
  onChange,
  label,
  showHint = false,
  className,
}: StateSelectorProps) {
  const { t } = useTranslation();
  const settings = useSettings();
  const id = useId();
  const current = value !== undefined ? value : settings.stateCode;
  const change = onChange ?? settings.setStateCode;

  return (
    <div className={className}>
      <label htmlFor={id} className="field-label flex items-center gap-1.5">
        <MapPin className="size-4 text-brand-700" aria-hidden />
        {label ?? t('settings.state')}
      </label>
      <select
        id={id}
        className="field-input"
        value={current ?? ''}
        onChange={(e) => change(e.target.value || null)}
        aria-describedby={showHint ? `${id}-hint` : undefined}
      >
        <option value="">{t('settings.stateNone')}</option>
        {STATES.map((s) => (
          <option key={s.code} value={s.code}>
            {s.name}
            {s.code === COVERED_STATE_CODE ? ' ✓' : ''}
          </option>
        ))}
      </select>
      {showHint && (
        <p id={`${id}-hint`} className="field-hint">
          {t('settings.stateHint')}
        </p>
      )}
    </div>
  );
}
