import { useEffect, useId, useRef, type ReactNode } from 'react';
import { Icon } from '../Icon';
import styles from './Dialog.module.css';

export function Dialog({
  open,
  onClose,
  title,
  closeLabel,
  variant = 'default',
  footer,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  closeLabel: string;
  variant?: 'default' | 'sidebar';
  footer?: ReactNode;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const closeTimer = useRef<number | null>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open) {
      if (closeTimer.current !== null) window.clearTimeout(closeTimer.current);
      closeTimer.current = null;
      dialog.removeAttribute('data-closing');
      if (!dialog.open) dialog.showModal();
      return;
    }
    if (!dialog.open) return;
    const reduceMotion =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion) {
      dialog.close();
      return;
    }
    dialog.setAttribute('data-closing', 'true');
    closeTimer.current = window.setTimeout(() => {
      if (dialog.open && dialog.dataset.closing === 'true') dialog.close();
      closeTimer.current = null;
    }, variant === 'sidebar' ? 160 : 150);
    return () => {
      if (closeTimer.current !== null) window.clearTimeout(closeTimer.current);
      closeTimer.current = null;
    };
  }, [open, variant]);
  return (
    <dialog
      ref={ref}
      className={`${styles.root}${variant === 'sidebar' ? ` ${styles.sidebar}` : ''}`}
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          const box = event.currentTarget.getBoundingClientRect();
          if (
            event.clientX < box.left ||
            event.clientX > box.right ||
            event.clientY < box.top ||
            event.clientY > box.bottom
          )
            onClose();
        }
      }}
    >
      <div className="dialog-shell">
        <header className="dialog-head">
          <h2 id={titleId}>{title}</h2>
          <button className="icon-button" onClick={onClose} aria-label={closeLabel}>
            <Icon name="close" />
          </button>
        </header>
        <div className="dialog-body">{children}</div>
        {footer}
      </div>
    </dialog>
  );
}
