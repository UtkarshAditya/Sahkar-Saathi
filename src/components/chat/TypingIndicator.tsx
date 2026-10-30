import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

/** After this many seconds the status changes from searching to writing. */
const WRITING_AFTER = 4;
/** After this many seconds the elapsed time is shown, since answers can take up to a minute. */
const SHOW_ELAPSED_AFTER = 8;

/** Shown while an answer is on its way. Mount it only while waiting. */
export function TypingIndicator() {
  const { t } = useTranslation();
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const id = window.setInterval(
      () => setSeconds(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    return () => window.clearInterval(id);
  }, []);

  return (
    <div className="flex items-start gap-3">
      <span className="mt-2 flex gap-1" aria-hidden>
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="size-1.5 animate-bounce rounded-full bg-brand-600"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </span>
      <div className="text-sm">
        <p role="status" className="font-medium text-ink-soft">
          {seconds < WRITING_AFTER ? t('chat.statusSearching') : t('chat.statusWriting')}
        </p>
        {seconds >= SHOW_ELAPSED_AFTER && (
          <p className="text-ink-muted">{t('chat.elapsed', { seconds })}</p>
        )}
      </div>
    </div>
  );
}
