import { useEffect, useId, useRef, type ReactNode } from 'react';
import { X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  presentation?: 'center' | 'drawer';
}

/** Accessible dialog built on the native <dialog> element (focus trap and Esc for free). */
export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  presentation = 'center',
}: ModalProps) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          event.preventDefault();
          onClose();
        }
      }}
      onClick={(e) => {
        // Close when the backdrop (the dialog element itself) is clicked.
        if (e.target === ref.current) onClose();
      }}
      aria-labelledby={titleId}
      aria-modal="true"
      className={
        presentation === 'drawer'
          ? 'fixed inset-x-0 top-auto bottom-0 m-0 max-h-[min(82dvh,42rem)] w-full max-w-none rounded-t-2xl border border-line bg-surface p-0 text-ink backdrop:bg-brand-950/40 lg:inset-y-0 lg:top-0 lg:right-0 lg:bottom-0 lg:left-auto lg:h-dvh lg:max-h-dvh lg:w-[min(32rem,90vw)] lg:rounded-none lg:border-y-0 lg:border-r-0 lg:border-l'
          : 'm-auto w-[calc(100%-2rem)] max-w-xl rounded-2xl border border-line bg-surface p-0 text-ink backdrop:bg-brand-950/40'
      }
    >
      <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
        <h2 id={titleId} className="text-lg font-semibold">
          {title}
        </h2>
        <button
          type="button"
          onClick={onClose}
          className="-m-1 flex size-12 shrink-0 items-center justify-center rounded-lg text-ink-muted hover:bg-canvas hover:text-ink"
          aria-label={t('common.close')}
        >
          <X className="size-5" aria-hidden />
        </button>
      </div>
      <div
        className={
          presentation === 'drawer'
            ? 'max-h-[min(82dvh,42rem)] overflow-y-auto px-5 py-4 lg:max-h-[calc(100dvh-5rem)]'
            : 'max-h-[65vh] overflow-y-auto px-5 py-4'
        }
      >
        {children}
      </div>
      {footer && (
        <div className="flex flex-wrap justify-end gap-2 border-t border-line px-5 py-3">
          {footer}
        </div>
      )}
    </dialog>
  );
}
