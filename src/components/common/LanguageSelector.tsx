import { useId } from 'react';
import { Check, Languages } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useSettings } from '@/hooks/useSettings';
import { LANGUAGES } from '@/i18n';
import { cn } from '@/lib/format';

interface LanguageSelectorProps {
  /** "full" shows a visible label (sidebar), "compact" is for the phone header. */
  variant?: 'full' | 'compact';
  className?: string;
}

export function LanguageSelector({ variant = 'full', className }: LanguageSelectorProps) {
  const { t } = useTranslation();
  const { language, setLanguage } = useSettings();
  const id = useId();

  if (variant === 'compact') {
    return (
      <div className={cn('relative', className)}>
        <label htmlFor={id} className="sr-only">
          {t('settings.language')}
        </label>
        <Languages
          className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-brand-800"
          aria-hidden
        />
        <select
          id={id}
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          className="min-h-12 appearance-none rounded-lg border-2 border-line bg-surface py-1.5 pr-3 pl-8 text-sm font-semibold text-ink"
        >
          {LANGUAGES.map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.label}
            </option>
          ))}
        </select>
      </div>
    );
  }

  return (
    <fieldset className={className}>
      <legend className="field-label flex items-center gap-1.5">
        <Languages className="size-4 text-brand-700" aria-hidden />
        {t('settings.language')}
      </legend>
      <div className="grid grid-cols-3 gap-1 rounded-xl bg-canvas p-1 ring-1 ring-line">
        {LANGUAGES.map((lang) => {
          const active = lang.code === language;
          return (
            <button
              key={lang.code}
              type="button"
              lang={lang.code}
              aria-pressed={active}
              title={lang.englishLabel}
              onClick={() => setLanguage(lang.code)}
              className={cn(
                'flex min-h-12 items-center justify-center gap-1 rounded-lg border-2 px-1 text-sm font-semibold transition-colors',
                active
                  ? 'border-brand-800 bg-brand-800 text-white'
                  : 'border-transparent text-ink-soft hover:border-line hover:bg-surface',
              )}
            >
              {active && <Check className="size-3.5 shrink-0" aria-hidden />}
              {lang.label}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
