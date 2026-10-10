import { useEffect, useId, useRef, type ReactNode } from 'react';
import { Icon } from '../Icon';
import styles from './Dialog.module.css';

export function Dialog({
  open,
  onClose,
  title,
  closeLabel,
  variant = 'default',
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  closeLabel: string;
  variant?: 'default' | 'sidebar';
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    else if (!open && dialog.open) dialog.close();
  }, [open]);
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
      </div>
    </dialog>
  );
}
