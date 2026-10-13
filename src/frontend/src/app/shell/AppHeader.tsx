import type { MouseEvent } from 'react';
import { usePreferences } from '../../shared/preferences';

type AppLink = (url: string) => (event: MouseEvent<HTMLAnchorElement>) => void;

export function AppHeader({ onLink }: { onLink: AppLink }) {
  const { t } = usePreferences();

  return (
    <header className="site-header">
      <div className="header-inner">
        <a className="brand" href="/" onClick={onLink('/')} aria-label="TourLens">
          <img className="brand-mark" src="/assets/mark.svg" alt="" width={36} height={36} />
          <span className="brand-name">TourLens</span>
        </a>
        <a className="header-support" href="/support" onClick={onLink('/support')}>
          {t('Hỗ trợ', 'Help')}
        </a>
      </div>
    </header>
  );
}
