import { useEffect, useRef, type MouseEvent } from 'react';
import { usePreferences } from '../../shared/preferences';

type AppLink = (url: string) => (event: MouseEvent<HTMLAnchorElement>) => void;

export function AppHeader({ onLink }: { onLink: AppLink }) {
  const { t } = usePreferences();
  const headerRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const header = headerRef.current;
    if (!header) return;
    const observer = new ResizeObserver(() =>
      document.documentElement.style.setProperty(
        '--header-height',
        `${header.getBoundingClientRect().height}px`,
      ),
    );
    observer.observe(header);
    return () => observer.disconnect();
  }, []);

  return (
    <header className="site-header" ref={headerRef}>
      <div className="header-inner">
        <a className="brand" href="/" onClick={onLink('/')}>
          <img className="brand-mark" src="/assets/mark.svg" alt="" width={32} height={32} />
          <strong className="brand-name">TourLens</strong>
        </a>
        <a className="header-support" href="/support" onClick={onLink('/support')}>
          {t('Hỗ trợ', 'Help')}
        </a>
      </div>
    </header>
  );
}
