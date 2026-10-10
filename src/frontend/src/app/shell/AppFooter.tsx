import type { MouseEvent } from 'react';
import { usePreferences } from '../../shared/preferences';

type AppLink = (url: string) => (event: MouseEvent<HTMLAnchorElement>) => void;

export function AppFooter({ onLink }: { onLink: AppLink }) {
  const { t } = usePreferences();

  const groups = [
    {
      title: t('Sản phẩm & Công cụ', 'Product & Tools'),
      links: [
        ['/', t('Giới thiệu', 'About')],
        ['/tours', t('Tìm tour', 'Find tours')],
        ['/support', t('Cách so sánh tour', 'How to compare tours')],
      ],
    },
    {
      title: t('Tài khoản & Hỗ trợ', 'Account & Support'),
      links: [
        ['/account', t('Tài khoản', 'Account')],
        ['/support', t('Hỗ trợ người dùng', 'User support')],
        ['/contact', t('Liên hệ chúng tôi', 'Contact us')],
      ],
    },
    {
      title: t('Pháp lý & Bảo mật', 'Legal & Security'),
      links: [
        ['/support#privacy', t('Dữ liệu & quyền riêng tư', 'Data & privacy')],
        ['/support#security', t('Quyền truy cập phiên', 'Session access')],
        ['/support#scope', t('Phạm vi sử dụng', 'Scope of use')],
      ],
    },
  ];

  return (
    <footer className="page-footer">
      <div className="footer-brand">
        <strong>đi cùng</strong>
        <p>{t('So sánh có nguồn, lựa chọn có cơ sở.', 'Sourced comparisons. Informed choices.')}</p>
      </div>
      {groups.map((group) => (
        <nav key={group.title} aria-label={group.title}>
          <h2>{group.title}</h2>
          {group.links.map(([url, label]) => (
            <a key={url} href={url} onClick={onLink(url)}>
              {label}
            </a>
          ))}
        </nav>
      ))}
    </footer>
  );
}
