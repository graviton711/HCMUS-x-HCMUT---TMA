import { useEffect, useRef, useState, type ReactNode } from 'react';
import { usePreferences } from '../app/preferences';
import { Icon } from './Icon';

const key = 'di-cung:sidebar:v1';
const clamp = (width: number) =>
  Math.min(Math.min(520, Math.max(240, window.innerWidth - 680)), Math.max(240, width));
function storedLayout() {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(key) || '{}');
    if (
      saved &&
      typeof saved === 'object' &&
      'width' in saved &&
      typeof saved.width === 'number' &&
      Number.isFinite(saved.width)
    )
      return {
        width:
          window.innerWidth > 1000 ? clamp(saved.width) : Math.min(520, Math.max(240, saved.width)),
        collapsed: 'collapsed' in saved && saved.collapsed === true,
      };
  } catch {
    /* use the default layout when browser storage is unavailable */
  }
  return { width: window.innerWidth > 1000 ? clamp(300) : 300, collapsed: false };
}
export function SessionSidebar({ children }: { children: ReactNode }) {
  const { t } = usePreferences();
  const [layout, setLayout] = useState(storedLayout);
  const aside = useRef<HTMLElement>(null);
  const pointer = useRef<number | null>(null);
  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(layout));
    } catch {
      /* layout still works */
    }
  }, [layout]);
  useEffect(() => {
    const resize = () => {
      if (window.innerWidth > 1000) setLayout((old) => ({ ...old, width: clamp(old.width) }));
    };
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, []);
  return (
    <aside
      ref={aside}
      className={`session-sidebar ${layout.collapsed ? 'sidebar-minimized' : ''}`}
      aria-label={t('Các phiên tìm tour', 'Tour sessions')}
      style={{ width: layout.collapsed ? 64 : layout.width }}
    >
      {layout.collapsed ? (
        <button
          className="sidebar-rail"
          type="button"
          aria-expanded={false}
          aria-label={t('Mở lịch sử phiên', 'Expand session history')}
          title={t('Mở lịch sử phiên', 'Expand session history')}
          onClick={() => setLayout((old) => ({ ...old, collapsed: false }))}
        >
          <span className="rail-mark">
            <img src="/assets/mark.svg" alt="" width={22} height={22} />
          </span>
          <Icon name="edit" size={23} />
          <Icon name="search" size={23} />
          <Icon name="history" size={23} />
          <span className="rail-spacer" />
          <span className="rail-account">
            <Icon name="user" size={23} />
          </span>
        </button>
      ) : (
        <>
          <div className="sidebar-topbar">
            <span>{t('Chuyến đi của bạn', 'Your trips')}</span>
            <button
              type="button"
              className="icon-button"
              aria-expanded={true}
              aria-label={t('Thu gọn lịch sử phiên', 'Collapse session history')}
              onClick={() => setLayout((old) => ({ ...old, collapsed: true }))}
            >
              <Icon name="menu" />
            </button>
          </div>
          {children}
          <div
            className="sidebar-resize"
            role="separator"
            tabIndex={0}
            aria-orientation="vertical"
            aria-label={t('Độ rộng lịch sử phiên', 'Session history width')}
            aria-valuemin={240}
            aria-valuemax={Math.min(520, Math.max(240, window.innerWidth - 680))}
            aria-valuenow={layout.width}
            onDoubleClick={() => setLayout((old) => ({ ...old, width: clamp(300) }))}
            onKeyDown={(event) => {
              const widths: Record<string, number> = {
                ArrowLeft: layout.width - 16,
                ArrowRight: layout.width + 16,
                Home: 240,
                End: 520,
              };
              if (!(event.key in widths)) return;
              event.preventDefault();
              setLayout((old) => ({ ...old, width: clamp(widths[event.key]) }));
            }}
            onPointerDown={(event) => {
              if (event.button !== 0) return;
              event.preventDefault();
              pointer.current = event.pointerId;
              event.currentTarget.setPointerCapture(event.pointerId);
            }}
            onPointerMove={(event) => {
              if (pointer.current !== event.pointerId || !aside.current) return;
              const width = clamp(event.clientX - aside.current.getBoundingClientRect().left);
              setLayout((old) => ({ ...old, width }));
            }}
            onPointerUp={(event) => {
              pointer.current = null;
              event.currentTarget.releasePointerCapture(event.pointerId);
            }}
            onLostPointerCapture={() => {
              pointer.current = null;
            }}
          />
        </>
      )}
    </aside>
  );
}
