import { useId } from 'react';
import { ChevronDown, MapPin } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { COVERED_STATE_CODE, STATES } from '@/data/options';
import { useSettings } from '@/hooks/useSettings';
import { cn } from '@/lib/format';

interface StateSelectorProps {
  /** Override the shared setting (e.g. a local form field). Defaults to the shared state. */
  value?: string | null;
  onChange?: (code: string | null) => void;
  label?: string;
  showHint?: boolean;
  className?: string;
  /** "compact" is the top bar select with a hidden label. */
  variant?: 'full' | 'compact';
}

export function StateSelector({
  value,
  onChange,
  label,
  showHint = false,
  className,
  variant = 'full',
}: StateSelectorProps) {
  const { t } = useTranslation();
  const settings = useSettings();
  const id = useId();
  const current = value !== undefined ? value : settings.stateCode;
  const change = onChange ?? settings.setStateCode;

  if (variant === 'compact') {
    return (
      <div className={cn('relative', className)}>
        <label htmlFor={id} className="sr-only">
          {label ?? t('settings.state')}
        </label>
        <MapPin
          className="pointer-events-none absolute top-1/2 left-2.5 hidden size-4 -translate-y-1/2 text-ink-muted sm:block"
          aria-hidden
        />
        <select
          id={id}
          value={current ?? ''}
          onChange={(e) => change(e.target.value || null)}
          className="min-h-11 w-[6.5rem] appearance-none truncate rounded-lg border border-line bg-surface py-1.5 pr-7 pl-3 text-sm sm:pl-8 font-medium text-ink hover:border-ink-muted/40 sm:w-44"
        >
          <option value="">{t('settings.state')}</option>
          {STATES.map((s) => (
            <option key={s.code} value={s.code}>
              {s.name}
              {s.code === COVERED_STATE_CODE ? ' ✓' : ''}
            </option>
          ))}
        </select>
        <ChevronDown
          className="pointer-events-none absolute top-1/2 right-2 size-4 -translate-y-1/2 text-ink-muted"
          aria-hidden
        />
      </div>
    );
  }

  return (
    <div className={className}>
      <label htmlFor={id} className="field-label flex items-center gap-1.5">
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
