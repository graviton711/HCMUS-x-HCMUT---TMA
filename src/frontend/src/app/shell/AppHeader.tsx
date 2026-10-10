import { useEffect, useRef, type MouseEvent } from 'react';
import { PreferencesControl } from '../../features/preferences';
import type { AuthProfile } from '../../features/session-history';
import { usePreferences } from '../../shared/preferences';
import { Icon } from '../../shared/ui';
import { isLinkClick } from '../routing';

type AppLink = (url: string) => (event: MouseEvent<HTMLAnchorElement>) => void;

export function AppHeader({
  routePath,
  profile,
  onContinueTours,
  onLink,
}: {
  routePath: string;
  profile: AuthProfile | null;
  onContinueTours: () => void;
  onLink: AppLink;
}) {
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
          <span className="brand-mark">
            <img src="/assets/mark.svg" alt="" width="25" height="25" />
          </span>
          <span>
            <strong className="brand-name">đi cùng</strong>
            <span className="brand-caption">
              {t('Một chuyến đi. Nhiều góc nhìn.', 'One trip. Many perspectives.')}
            </span>
          </span>
        </a>
        <nav className="main-nav" aria-label={t('Điều hướng chính', 'Main navigation')}>
          {[
            ['/', t('Giới thiệu', 'About')],
            ['/tours', t('Tìm tour', 'Find tours')],
            ['/contact', t('Liên hệ chúng tôi', 'Contact us')],
            ['/support', t('Hỗ trợ người dùng', 'Help')],
          ].map(([url, label]) => (
            <a
              key={url}
              href={url}
              onClick={
                url === '/tours'
                  ? (event) => {
                      if (isLinkClick(event)) {
                        event.preventDefault();
                        onContinueTours();
                      }
                    }
                  : onLink(url)
              }
              aria-current={routePath === url ? 'page' : undefined}
            >
              {label}
            </a>
          ))}
        </nav>
        <div className="account-actions">
          <PreferencesControl />
          <a
            className="account-link"
            aria-label={
              profile
                ? t(`Tài khoản của ${profile.name}`, `Account for ${profile.name}`)
                : t('Đăng nhập', 'Sign in')
            }
            title={profile?.name || t('Đăng nhập', 'Sign in')}
            href={profile ? '/account' : '/auth'}
            onClick={onLink(profile ? '/account' : '/auth')}
          >
            <Icon name="user" />
            <span>{profile?.name || t('Đăng nhập', 'Sign in')}</span>
          </a>
        </div>
      </div>
    </header>
  );
}
