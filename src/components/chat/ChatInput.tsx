import { useId, useState, type CSSProperties, type FormEvent, type KeyboardEvent } from 'react';
import { Mic, Send } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/common/Button';
import { Notice } from '@/components/common/Notice';

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (text: string) => void;
  loading: boolean;
}

/**
 * Text box, microphone and send button.
 * Sprint 2: replace the mic notice with a useRecorder hook that records, calls
 * /speech/transcribe and puts the editable transcript into this text box.
 */
export function ChatInput({ value, onChange, onSubmit, loading }: ChatInputProps) {
  const { t } = useTranslation();
  const id = useId();
  const [showMicNotice, setShowMicNotice] = useState(false);
  const canSend = value.trim().length > 0 && !loading;

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (canSend) onSubmit(value.trim());
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends, Shift+Enter adds a new line.
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      if (canSend) onSubmit(value.trim());
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      {showMicNotice && (
        <Notice tone="info" role="status">
          {t('chat.micNotice')}
        </Notice>
      )}
      <label htmlFor={id} className="sr-only">
        {t('chat.inputLabel')}
      </label>
      <div className="flex items-end gap-2 rounded-2xl border border-line bg-surface p-2 focus-within:border-brand-600 focus-within:ring-2 focus-within:ring-brand-200">
        <button
          type="button"
          onClick={() => setShowMicNotice((v) => !v)}
          aria-pressed={showMicNotice}
          aria-label={`${t('chat.mic')} (${t('common.demo')})`}
          title={t('chat.micNotice')}
          className="relative flex size-11 shrink-0 items-center justify-center rounded-xl bg-saffron-50 text-saffron-700 ring-1 ring-saffron-200 hover:bg-saffron-100"
        >
          <Mic className="size-5" aria-hidden />
          <span className="absolute -top-1 -right-1 rounded-full bg-saffron-500 px-1 text-[10px] leading-4 font-bold text-white">
            soon
          </span>
        </button>
        <textarea
          id={id}
          rows={1}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t('chat.placeholder')}
          className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-2 py-2.5 text-base outline-none placeholder:text-ink-muted"
          style={{ fieldSizing: 'content' } as CSSProperties}
        />
        <Button
          type="submit"
          disabled={!canSend}
          loading={loading}
          icon={<Send className="size-5" aria-hidden />}
          className="shrink-0 rounded-xl"
          aria-label={t('chat.send')}
        >
          <span className="hidden sm:inline">{t('chat.send')}</span>
        </Button>
      </div>
      <p className="px-1 text-xs text-ink-muted">Enter to send · Shift + Enter for a new line</p>
    </form>
  );
}
