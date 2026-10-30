import { Link } from 'react-router';
import { useTranslation } from 'react-i18next';

/** Logo mark plus name. Two linked rings: members joined in a cooperative. */
export function Brand({ iconOnly = false }: { iconOnly?: boolean }) {
  const { t } = useTranslation();
  return (
    <Link
      to="/"
      className="flex min-h-11 items-center gap-2.5 rounded-lg"
      aria-label={t('app.name')}
      title={iconOnly ? t('app.name') : undefined}
    >
      <svg viewBox="0 0 64 64" className="size-8 shrink-0" aria-hidden>
        <rect width="64" height="64" rx="16" fill="var(--color-brand-800)" />
        <circle cx="25" cy="30" r="10" fill="none" stroke="#fff" strokeWidth="4.5" />
        <circle
          cx="39"
          cy="30"
          r="10"
          fill="none"
          stroke="var(--color-saffron-300)"
          strokeWidth="4.5"
        />
      </svg>
      {!iconOnly && (
        <span className="text-base font-semibold tracking-tight whitespace-nowrap text-ink">
          {t('app.name')}
        </span>
      )}
    </Link>
  );
}
