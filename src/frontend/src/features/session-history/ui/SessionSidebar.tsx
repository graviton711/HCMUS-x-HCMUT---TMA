import { useRef, useState, type MouseEvent, type ReactNode } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { displaySessionTitle } from '../../../shared/lib';
import { usePreferences } from '../../../shared/preferences';
import { Icon } from '../../../shared/ui';
import { sidebarMetrics } from '../model/sidebarLayout';
import styles from './SessionSidebar.module.css';

/**
 * Presentational sidebar. Width/collapse state lives in the app shell so the
 * canvas header owns the single sidebar control.
 */
export function SessionSidebar({
  collapsed,
  width,
  onWidthChange,
  onToggle,
  onStart,
  onHome,
  children,
  footer,
  railFooter,
  supportLink,
}: {
  collapsed: boolean;
  width: number;
  onWidthChange: (width: number) => void;
  onToggle: () => void;
  onStart: () => void;
  onHome: (event: MouseEvent<HTMLAnchorElement>) => void;
  children: ReactNode;
  footer?: ReactNode;
  railFooter?: ReactNode;
  supportLink?: ReactNode;
}) {
  const { t } = usePreferences();
  const reduceMotion = useReducedMotion();
  const aside = useRef<HTMLElement>(null);
  const pointer = useRef<number | null>(null);
  const [dragging, setDragging] = useState(false);
  const label = displaySessionTitle(null, t('Các phiên tìm tour', 'Tour sessions'));

  return (
    <aside
      ref={aside}
      className={styles.root}
      data-collapsed={collapsed}
      aria-label={label}
      style={collapsed ? undefined : { width }}
    >
      {collapsed ? (
        <div className={styles.rail}>
          <a className={styles['rail-mark']} href="/" onClick={onHome} aria-label="TourLens">
            <img className={styles['brand-mark']} src="/assets/mark.svg" alt="" width={32} height={32} />
          </a>
          <button
            type="button"
            className="icon-button"
            aria-label={t('Mở lịch sử phiên', 'Expand session history')}
            title={t('Mở lịch sử phiên', 'Expand session history')}
            onClick={onToggle}
          >
            <Icon name="panel" />
          </button>
          <motion.button
            type="button"
            className="icon-button"
            aria-label={t('Tìm tour mới', 'Start a new search')}
            title={t('Tìm tour mới', 'Start a new search')}
            onClick={onStart}
            whileHover={reduceMotion ? undefined : { y: -1 }}
            whileTap={reduceMotion ? undefined : { scale: 0.94 }}
          >
            <Icon name="plus" />
          </motion.button>
          <span className={styles['rail-spacer']} />
          {railFooter && <div className={styles['rail-foot']}>{railFooter}</div>}
        </div>
      ) : (
        <>
          <div className={styles.body}>
            <a className={styles.brand} href="/" onClick={onHome} aria-label="TourLens">
              <img className={styles['brand-mark']} src="/assets/mark.svg" alt="" width={34} height={34} />
            </a>
            <motion.button
              type="button"
              className={styles['new-session']}
              onClick={onStart}
              whileHover={reduceMotion ? undefined : { y: -1 }}
              whileTap={reduceMotion ? undefined : { scale: 0.985 }}
              transition={{ type: 'spring', stiffness: 500, damping: 32 }}
            >
              <Icon name="plus" size={17} />
              <span>{t('Tìm tour mới', 'New search')}</span>
            </motion.button>
            {supportLink && <div className={styles['support-link']}>{supportLink}</div>}
            <div className={styles['history-body']}>{children}</div>
          </div>
          {footer && <div className={styles.foot}>{footer}</div>}
          <div
            className={styles.resize}
            role="separator"
            tabIndex={0}
            aria-orientation="vertical"
            aria-label={t('Độ rộng lịch sử phiên', 'Session history width')}
            aria-valuemin={sidebarMetrics.minWidth}
            aria-valuemax={Math.min(
              sidebarMetrics.maxWidth,
              Math.max(sidebarMetrics.minWidth, window.innerWidth - 680),
            )}
            aria-valuenow={width}
            aria-valuetext={`${width}px`}
            onDoubleClick={() => onWidthChange(sidebarMetrics.defaultWidth)}
            onKeyDown={(event) => {
              const steps: Record<string, number> = {
                ArrowLeft: width - 16,
                ArrowRight: width + 16,
                Home: sidebarMetrics.minWidth,
                End: sidebarMetrics.maxWidth,
              };
              if (!(event.key in steps)) return;
              event.preventDefault();
              onWidthChange(
                Math.min(
                  Math.max(steps[event.key], sidebarMetrics.minWidth),
                  sidebarMetrics.maxWidth,
                ),
              );
            }}
            onPointerDown={(event) => {
              if (event.button !== 0 || !aside.current) return;
              event.preventDefault();
              pointer.current = event.pointerId;
              setDragging(true);
              event.currentTarget.setPointerCapture(event.pointerId);
            }}
            onPointerMove={(event) => {
              if (pointer.current !== event.pointerId || !aside.current) return;
              const next = event.clientX - aside.current.getBoundingClientRect().left;
              onWidthChange(
                Math.min(
                  Math.max(next, sidebarMetrics.minWidth),
                  Math.min(
                    sidebarMetrics.maxWidth,
                    Math.max(sidebarMetrics.minWidth, window.innerWidth - 680),
                  ),
                ),
              );
            }}
            onPointerUp={(event) => {
              pointer.current = null;
              setDragging(false);
              event.currentTarget.releasePointerCapture(event.pointerId);
            }}
            onLostPointerCapture={() => {
              pointer.current = null;
              setDragging(false);
            }}
            data-dragging={dragging}
          />
        </>
      )}
    </aside>
  );
}
