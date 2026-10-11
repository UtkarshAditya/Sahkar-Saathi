import { Link } from 'react-router';
import { useTranslation } from 'react-i18next';

/** Logo mark plus name. Two linked rings: members joined in a cooperative. */
export function Brand({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation();
  return (
    <Link to="/" className="flex items-center gap-2.5 rounded-lg" aria-label={t('app.name')}>
      <svg viewBox="0 0 64 64" className="size-10 shrink-0" aria-hidden>
        <rect width="64" height="64" rx="14" fill="var(--color-brand-800)" />
        <circle cx="24" cy="28" r="9" fill="none" stroke="#fff" strokeWidth="4" />
        <circle
          cx="40"
          cy="28"
          r="9"
          fill="none"
          stroke="var(--color-saffron-400)"
          strokeWidth="4"
        />
        <path d="M16 48h32" stroke="#fff" strokeWidth="4" strokeLinecap="round" />
      </svg>
      <span className="min-w-0 leading-tight">
        <span className="block text-lg font-bold whitespace-nowrap text-brand-900">
          {t('app.name')}
        </span>
        {!compact && <span className="block text-xs text-ink-muted">{t('app.tagline')}</span>}
      </span>
    </Link>
  );
}
