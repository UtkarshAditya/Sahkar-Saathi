import { useEffect, useRef, type ReactNode } from 'react';
import { X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
}

/** Accessible dialog built on the native <dialog> element (focus trap and Esc for free). */
export function Modal({ open, onClose, title, children, footer }: ModalProps) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDialogElement>(null);

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
      onClick={(e) => {
        // Close when the backdrop (the dialog element itself) is clicked.
        if (e.target === ref.current) onClose();
      }}
      aria-labelledby="modal-title"
      className="m-auto w-[calc(100%-2rem)] max-w-xl rounded-2xl border border-line bg-surface p-0 text-ink backdrop:bg-brand-950/40"
    >
      <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
        <h2 id="modal-title" className="text-lg font-semibold">
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
      <div className="max-h-[65vh] overflow-y-auto px-5 py-4">{children}</div>
      {footer && (
        <div className="flex flex-wrap justify-end gap-2 border-t border-line px-5 py-3">
          {footer}
        </div>
      )}
    </dialog>
  );
}
