import { useTranslation } from 'react-i18next';
import { splitContacts } from '@/lib/grievance';

/** Text from the API with its phone numbers, e-mail addresses and https links made tappable. */
export function ContactText({ text, className }: { text: string; className?: string }) {
  const { t } = useTranslation();
  return (
    <p className={className}>
      {splitContacts(text).map((part, i) =>
        part.kind === 'text' ? (
          <span key={i}>{part.value}</span>
        ) : (
          <a
            key={i}
            href={part.href}
            {...(part.external ? { target: '_blank', rel: 'noreferrer' } : {})}
            className="font-semibold whitespace-nowrap text-brand-800 underline underline-offset-2"
          >
            {part.value}
            {part.external && <span className="sr-only"> ({t('chat.opensInNewTab')})</span>}
          </a>
        ),
      )}
    </p>
  );
}
