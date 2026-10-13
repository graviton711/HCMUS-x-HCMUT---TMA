import { useEffect, useId, useRef, type ReactNode, type RefObject } from 'react';
import { Icon } from '../Icon';
import styles from './Dialog.module.css';

export function Dialog({
  open,
  onClose,
  title,
  description,
  closeLabel,
  variant = 'default',
  size = 'default',
  tone = 'default',
  role,
  initialFocusRef,
  footer,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: ReactNode;
  closeLabel: string;
  variant?: 'default' | 'sidebar';
  size?: 'default' | 'wide';
  tone?: 'default' | 'danger';
  role?: 'dialog' | 'alertdialog';
  initialFocusRef?: RefObject<HTMLElement | null>;
  footer?: ReactNode;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const closeTimer = useRef<number | null>(null);
  const titleId = useId();
  const descriptionId = useId();
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open) {
      if (closeTimer.current !== null) window.clearTimeout(closeTimer.current);
      closeTimer.current = null;
      dialog.removeAttribute('data-closing');
      if (!dialog.open) {
        dialog.showModal();
        initialFocusRef?.current?.focus();
      }
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
    closeTimer.current = window.setTimeout(
      () => {
        if (dialog.open && dialog.dataset.closing === 'true') dialog.close();
        closeTimer.current = null;
      },
      variant === 'sidebar' ? 160 : 150,
    );
    return () => {
      if (closeTimer.current !== null) window.clearTimeout(closeTimer.current);
      closeTimer.current = null;
    };
  }, [initialFocusRef, open, variant]);
  return (
    <dialog
      ref={ref}
      className={`${styles.root}${variant === 'sidebar' ? ` ${styles.sidebar}` : ''}${size === 'wide' ? ` ${styles.wide}` : ''}`}
      data-tone={tone}
      role={role}
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
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
          <div className="dialog-heading">
            <h2 id={titleId}>{title}</h2>
            {description && <p id={descriptionId}>{description}</p>}
          </div>
          <button
            className="icon-button dialog-close"
            type="button"
            onClick={onClose}
            aria-label={closeLabel}
          >
            <Icon name="close" />
          </button>
        </header>
        <div className="dialog-body">{children}</div>
        {footer}
      </div>
    </dialog>
  );
}
