import type { MouseEventHandler } from 'react';
import { usePreferences } from './preferences';

export function Footer({ link }: { link: (url: string) => MouseEventHandler<HTMLAnchorElement> }) {
  const { t } = usePreferences();
  const groups = [
    {
      title: t('Khám phá', 'Explore'),
      links: [
        ['/', t('Giới thiệu', 'About')],
        ['/tours', t('Tìm tour', 'Find tours')],
        ['/support#compare', t('Cách so sánh và xem đánh đổi', 'Compare and explore trade-offs')],
      ],
    },
    {
      title: t('Tài khoản & Hỗ trợ', 'Account & Support'),
      links: [
        ['/account', t('Tài khoản', 'Account')],
        ['/support#faq', t('Câu hỏi thường gặp', 'Frequently asked questions')],
        [
          '/contact?category=data_issue',
          t('Báo thông tin tour sai', 'Report incorrect tour information'),
        ],
        ['/contact', t('Liên hệ chúng tôi', 'Contact us')],
      ],
    },
    {
      title: t('Thông tin & Quyền riêng tư', 'Information & Privacy'),
      links: [
        ['/support#sources', t('Nguồn dữ liệu và AI', 'Data sources and AI')],
        ['/support#privacy', t('Dữ liệu & quyền riêng tư', 'Data & privacy')],
        ['/support#security', t('Quyền truy cập phiên', 'Session access')],
        ['/support#scope', t('Phạm vi sử dụng', 'Scope of use')],
      ],
    },
  ];
  return (
    <footer className="page-footer">
      <div className="footer-inner">
        <div className="footer-brand">
          <a className="footer-brand-link" href="/" onClick={link('/')}>
            <span className="brand-mark">
              <img src="/assets/mark.svg" alt="" width="25" height="25" />
            </span>
            <strong>đi cùng</strong>
          </a>
          <p>
            {t('So sánh có nguồn, lựa chọn có cơ sở.', 'Sourced comparisons. Informed choices.')}
          </p>
        </div>
        {groups.map((group) => (
          <nav key={group.title} aria-label={group.title}>
            <h2>{group.title}</h2>
            {group.links.map(([url, label]) => (
              <a key={url} href={url} onClick={link(url)}>
                {label}
              </a>
            ))}
          </nav>
        ))}
        <div className="footer-bottom">
          <p>{t('Một chuyến đi. Nhiều góc nhìn.', 'One trip. Many perspectives.')}</p>
          <p>
            {t(
              'Hỗ trợ so sánh tour. Bạn quyết định và đặt với nhà cung cấp.',
              'Compare here. Decide and book with the supplier.',
            )}
          </p>
        </div>
      </div>
    </footer>
  );
}
