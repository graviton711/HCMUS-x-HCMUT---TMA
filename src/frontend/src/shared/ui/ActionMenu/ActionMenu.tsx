import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from 'react';
import { Icon, type IconName } from '../Icon';
import styles from './ActionMenu.module.css';

export type ActionMenuItem = {
  label: string;
  icon: IconName;
  onSelect: () => void;
  destructive?: boolean;
  separatorBefore?: boolean;
};

export function ActionMenu({ label, items }: { label: string; items: ActionMenuItem[] }) {
  const [open, setOpen] = useState(false);
  const [focusLastOnOpen, setFocusLastOnOpen] = useState(false);
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const menuItems = useRef<HTMLButtonElement[]>([]);
  const focusOnOpen = useRef(false);

  const placeMenu = useCallback(() => {
    const anchor = trigger.current;
    const panel = menu.current;
    if (!anchor || !panel) return;

    const rect = anchor.getBoundingClientRect();
    const panelWidth = panel.offsetWidth;
    const panelHeight = panel.offsetHeight;
    const edge = 8;
    const left = Math.max(
      edge,
      Math.min(rect.right - panelWidth, window.innerWidth - panelWidth - edge),
    );
    const below = rect.bottom + 6;
    const top =
      below + panelHeight <= window.innerHeight - edge
        ? below
        : Math.max(edge, rect.top - panelHeight - 6);
    panel.style.top = `${top}px`;
    panel.style.left = `${left}px`;
    setPosition({ top, left });
  }, []);

  useLayoutEffect(() => {
    const panel = menu.current;
    if (!open || !panel) return;
    const frame = window.requestAnimationFrame(placeMenu);
    window.addEventListener('resize', placeMenu);
    window.addEventListener('scroll', placeMenu, true);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener('resize', placeMenu);
      window.removeEventListener('scroll', placeMenu, true);
    };
  }, [open, placeMenu]);

  useEffect(() => {
    if (!open || !position || !focusOnOpen.current) return;
    const frame = window.requestAnimationFrame(() => {
      const index = focusLastOnOpen ? items.length - 1 : 0;
      const target = menuItems.current[index];
      target?.focus();
      if (target && document.activeElement === target) focusOnOpen.current = false;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [focusLastOnOpen, items.length, open, position]);

  function show(focusLast = false) {
    const panel = menu.current;
    if (!panel) return;
    focusOnOpen.current = true;
    setPosition(null);
    setFocusLastOnOpen(focusLast);
    if (typeof panel.showPopover === 'function' && !panel.matches(':popover-open')) {
      panel.showPopover();
    }
    placeMenu();
    setOpen(true);
    const index = focusLast ? items.length - 1 : 0;
    const target = menuItems.current[index];
    target?.focus();
    if (target && document.activeElement === target) focusOnOpen.current = false;
  }

  function toggle() {
    const panel = menu.current;
    if (!panel) return;
    if (typeof panel.hidePopover === 'function' && panel.matches(':popover-open')) {
      panel.hidePopover();
      setOpen(false);
      setPosition(null);
    } else {
      show();
    }
  }

  function close(restoreFocus = false) {
    const panel = menu.current;
    if (panel && typeof panel.hidePopover === 'function' && panel.matches(':popover-open')) {
      panel.hidePopover();
    }
    setOpen(false);
    setPosition(null);
    if (restoreFocus) trigger.current?.focus();
  }

  function onMenuKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const current = menuItems.current.indexOf(document.activeElement as HTMLButtonElement);
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      close(true);
      return;
    }
    if (event.key === 'Tab') {
      close();
      return;
    }

    let next = current;
    if (event.key === 'ArrowDown') next = (current + 1) % items.length;
    else if (event.key === 'ArrowUp') next = (current - 1 + items.length) % items.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = items.length - 1;
    else return;
    event.preventDefault();
    menuItems.current[next]?.focus();
  }

  return (
    <>
      <button
        ref={trigger}
        type="button"
        className={`icon-button ${styles.trigger}`}
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={id}
        title={label}
        onClick={toggle}
        onKeyDown={(event) => {
          if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault();
            show(event.key === 'ArrowUp');
          }
        }}
      >
        <Icon name="more" size={17} />
      </button>
      <div
        ref={menu}
        id={id}
        className={styles.menu}
        role="menu"
        aria-label={label}
        popover="auto"
        data-open={open}
        style={position ? { top: position.top, left: position.left } : undefined}
        onToggle={(event) => {
          const nextOpen = event.currentTarget.matches(':popover-open');
          setOpen(nextOpen);
          if (!nextOpen) setPosition(null);
        }}
        onKeyDown={onMenuKeyDown}
      >
        {items.map((item, index) => (
          <button
            key={item.label}
            ref={(element) => {
              if (element) menuItems.current[index] = element;
            }}
            type="button"
            role="menuitem"
            tabIndex={-1}
            className={`${styles.item}${item.destructive ? ` ${styles.destructive}` : ''}${item.separatorBefore ? ` ${styles.separated}` : ''}`}
            onClick={() => {
              close();
              item.onSelect();
            }}
          >
            <Icon name={item.icon} size={16} />
            <span>{item.label}</span>
          </button>
        ))}
      </div>
    </>
  );
}
