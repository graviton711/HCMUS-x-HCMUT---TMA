import type { MouseEvent } from 'react';
import { usePreferences } from '../../shared/preferences';

type AppLink = (url: string) => (event: MouseEvent<HTMLAnchorElement>) => void;

const LEGAL: [string, string][] = [
  ['/support#privacy', 'Dữ liệu & quyền riêng tư'],
  ['/support#security', 'Quyền truy cập phiên'],
  ['/support#scope', 'Phạm vi sử dụng'],
];

export function AppFooter({ onLink }: { onLink: AppLink }) {
  const { t } = usePreferences();
  return (
    <footer className="page-footer">
      <span className="footer-brand">TourLens</span>
      <nav aria-label={t('Liên kết', 'Links')}>
        {LEGAL.map(([url, label]) => (
          <a key={url} href={url} onClick={onLink(url)}>
            {t(label, label)}
          </a>
        ))}
      </nav>
    </footer>
  );
}
