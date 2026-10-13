import { usePreferences } from '../../../shared/preferences';
import { Icon } from '../../../shared/ui';
import type { MouseEvent } from 'react';

type UnavailableRoute = 'auth' | 'account' | 'contact' | 'not-found';
type AppLink = (url: string) => (event: MouseEvent<HTMLAnchorElement>) => void;

export function UnavailablePage({
  route,
  onContinue,
  onLink,
}: {
  route: UnavailableRoute;
  onContinue: () => void;
  onLink: AppLink;
}) {
  const { t } = usePreferences();
  const content: Record<UnavailableRoute, { title: string; body: string }> = {
    auth: {
      title: t('Đăng nhập chưa được kết nối.', 'Sign-in is not connected yet.'),
      body: t(
        'Bạn vẫn có thể tìm tour bằng phiên guest; tài khoản sẽ được tích hợp sau với backend hiện tại.',
        'You can search using a guest session; account support will be connected against the current backend later.',
      ),
    },
    account: {
      title: t('Tài khoản chưa khả dụng.', 'Account features are not available yet.'),
      body: t(
        'Auth, đồng bộ lịch sử và quản lý dữ liệu tài khoản chưa có API runtime trên backend hiện tại.',
        'Auth, history sync and account data management do not yet have runtime APIs on the current backend.',
      ),
    },
    contact: {
      title: t('Liên hệ chưa khả dụng.', 'Contact is not available yet.'),
      body: t(
        'Form liên hệ sẽ chỉ được bật sau khi backend hiện tại có route tiếp nhận và lưu ticket.',
        'The contact form will be enabled when the current backend has a ticket submission route.',
      ),
    },
    'not-found': {
      title: t('Trang này không tồn tại.', 'This page could not be found.'),
      body: '',
    },
  };
  const page = content[route];

  return (
    <section className="empty-state" aria-labelledby="unavailable-heading">
      <div className="empty-state-icon" aria-hidden="true">
        <Icon name={route === 'not-found' ? 'search' : 'help'} size={24} />
      </div>
      <h1 id="unavailable-heading">{page.title}</h1>
      {page.body && <p>{page.body}</p>}
      {route === 'not-found' ? (
        <a className="btn" href="/" onClick={onLink('/')}>
          {t('Về Tìm tour', 'Back to Find tours')}
          <Icon name="arrow" />
        </a>
      ) : (
        <button className="btn btn-primary" onClick={onContinue}>
          {t('Tiếp tục với guest', 'Continue as guest')}
        </button>
      )}
    </section>
  );
}
