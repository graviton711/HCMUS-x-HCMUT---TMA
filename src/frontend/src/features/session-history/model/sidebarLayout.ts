import { useCallback, useEffect, useState } from 'react';

const key = 'di-cung:sidebar:v1';

const MIN_WIDTH = 240;
const MAX_WIDTH = 520;
const DEFAULT_WIDTH = 248;
const RAIL_WIDTH = 64;

function clamp(width: number) {
  return Math.min(
    Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, window.innerWidth - 680)),
    Math.max(MIN_WIDTH, width),
  );
}

interface SidebarLayout {
  collapsed: boolean;
  width: number;
}

function readLayout(): SidebarLayout {
  const fallback: SidebarLayout = { collapsed: false, width: DEFAULT_WIDTH };
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(key) || '{}');
    if (!saved || typeof saved !== 'object' || !('width' in saved)) return fallback;
    const record = saved as { width?: unknown; collapsed?: unknown };
    if (typeof record.width !== 'number' || !Number.isFinite(record.width)) return fallback;
    return {
      collapsed: record.collapsed === true,
      width:
        window.innerWidth > 1000
          ? clamp(record.width)
          : Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, record.width)),
    };
  } catch {
    return fallback;
  }
}

/** Sidebar width/collapse state. Storage key and clamp behaviour are preserved. */
export function useSidebarLayout() {
  const [layout, setLayout] = useState<SidebarLayout>(readLayout);

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(layout));
    } catch {
      /* layout still works without persistence */
    }
  }, [layout]);

  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth > 1000) setLayout((old) => ({ ...old, width: clamp(old.width) }));
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const setWidth = useCallback((width: number) => setLayout((old) => ({ ...old, width })), []);
  const toggle = useCallback(() => setLayout((old) => ({ ...old, collapsed: !old.collapsed })), []);

  return {
    collapsed: layout.collapsed,
    width: layout.collapsed ? RAIL_WIDTH : layout.width,
    expandedWidth: layout.width,
    toggle,
    setWidth,
  };
}

export const sidebarMetrics = {
  minWidth: MIN_WIDTH,
  maxWidth: MAX_WIDTH,
  defaultWidth: DEFAULT_WIDTH,
};
