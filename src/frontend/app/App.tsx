import { useCallback, useEffect, useId, useRef, useState, type MouseEvent } from 'react';
import { readAuthProfile, type AuthProfile } from './AuthPages';
import { LandingPage, SupportPage } from './PublicPages';
import { PreferencesControl, usePreferences } from './preferences';
import {
  loadSessions,
  newSession,
  normalizeSearch,
  removeAccess,
  saveSessions,
  type LocalSession,
} from './storage';
import { Dialog } from '../components/Dialog';
import { Icon } from '../components/Icon';
import { SessionSidebar } from '../components/SessionSidebar';
import { CurrentWorkspace } from '../features/workspace/CurrentWorkspace';

function locationState() {
  return {
    path: window.location.pathname.replace(/\/$/, '') || '/',
    session: new URLSearchParams(window.location.search).get('session'),
    hash: window.location.hash,
  };
}
function isLinkClick(event: MouseEvent<HTMLAnchorElement>) {
  return event.button === 0 && !event.ctrlKey && !event.metaKey && !event.altKey && !event.shiftKey;
}

export function App() {
  const { t, locale } = usePreferences();
  const [route, setRoute] = useState(locationState);
  const [sessions, setSessions] = useState(() => loadSessions(readAuthProfile()?.id));
  const [profile] = useState<AuthProfile | null>(readAuthProfile);
  const [drawer, setDrawer] = useState(false);
  const [filter, setFilter] = useState('');
  const [rename, setRename] = useState<LocalSession | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [remove, setRemove] = useState<LocalSession | null>(null);
  const [storageError, setStorageError] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const searchId = useId();
  const headerRef = useRef<HTMLElement>(null);
  const current =
    sessions.find((s) => s.id === route.session) ||
    (route.path === '/tours' ? sessions[0] || null : null);
  const patchSession = useCallback(
    (id: string, update: Partial<LocalSession> | ((s: LocalSession) => Partial<LocalSession>)) => {
      setSessions((all) =>
        all.map((s) =>
          s.id === id
            ? {
                ...s,
                ...(typeof update === 'function' ? update(s) : update),
                updatedAt: new Date().toISOString(),
              }
            : s,
        ),
      );
    },
    [],
  );
  useEffect(() => {
    setStorageError(!saveSessions(sessions, profile?.id));
  }, [sessions, profile?.id]);
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
  useEffect(() => {
    const back = () => setRoute(locationState());
    window.addEventListener('popstate', back);
    return () => window.removeEventListener('popstate', back);
  }, []);
  useEffect(() => {
    document.title = `${route.path === '/tours' ? t('Tìm tour', 'Find tours') : route.path === '/auth' ? t('Tài khoản', 'Account') : 'Đi cùng'} · Đi cùng`;
  }, [route.path, t]);
  useEffect(() => {
    if (route.hash)
      document
        .getElementById(route.hash.slice(1))
        ?.scrollIntoView({ block: 'start', behavior: 'instant' });
  }, [route.path, route.hash]);
  const navigate = (url: string) => {
    window.history.pushState(null, '', url);
    setRoute(locationState());
    setDrawer(false);
    if (locationState().path !== '/tours' && !locationState().hash)
      window.scrollTo({ top: 0, behavior: 'instant' });
  };
  const startSession = () => {
    const next = newSession();
    setSessions((all) => [next, ...all]);
    navigate(`/tours?session=${next.id}`);
  };
  const continueTours = () => {
    if (sessions.length) navigate(`/tours?session=${sessions[0].id}`);
    else startSession();
  };
  const onStart = () => continueTours();
  const updateMetadata = (session: LocalSession, changes: { title?: string; pinned?: boolean }) =>
    patchSession(session.id, changes);
  const archive = async (session: LocalSession) => {
    setSessions((all) => all.filter((s) => s.id !== session.id));
    removeAccess(session.id);
  };
  const link = (url: string) => (event: MouseEvent<HTMLAnchorElement>) => {
    if (isLinkClick(event)) {
      event.preventDefault();
      navigate(url);
    }
  };
  const sorted = [...sessions].sort(
    (a, b) =>
      Number(b.pinned) - Number(a.pinned) || Date.parse(b.updatedAt) - Date.parse(a.updatedAt),
  );
  const terms = normalizeSearch(filter).split(/\s+/).filter(Boolean);
  const matching = sorted.filter((s) =>
    terms.every((term) => normalizeSearch(s.title).includes(term)),
  );
  const sessionName = (s: LocalSession) => s.title || t('Chuyến đi mới', 'New trip');
  const sidebar = (suffix: string) => (
    <div className="sidebar-content">
      <div className="sidebar-heading">
        <button className="btn" onClick={startSession}>
          <Icon name="plus" />
          {t('Phiên mới', 'New session')}
        </button>
      </div>
      <label className="sidebar-search" htmlFor={`${searchId}-${suffix}`}>
        <Icon name="search" />
        <span className="sr-only">{t('Tìm phiên', 'Search sessions')}</span>
        <input
          id={`${searchId}-${suffix}`}
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder={t('Tìm trong lịch sử', 'Search history')}
        />
      </label>
      <nav aria-label={t('Lịch sử phiên', 'Session history')} className="session-list">
        {matching.length === 0 && (
          <p className="form-hint">
            {sessions.length
              ? t('Không tìm thấy phiên phù hợp.', 'No matching sessions.')
              : t('Chuyến đi đầu tiên đang chờ bạn.', 'Your first trip is waiting.')}
          </p>
        )}
        {matching.map((s, index) => {
          const today = new Date(s.updatedAt).toDateString() === new Date().toDateString();
          const previous = matching[index - 1];
          const groupLabel = s.pinned
            ? t('Đã ghim', 'Pinned')
            : today
              ? t('Hôm nay', 'Today')
              : t('Trước đó', 'Earlier');
          const previousGroup = previous
            ? previous.pinned
              ? t('Đã ghim', 'Pinned')
              : new Date(previous.updatedAt).toDateString() === new Date().toDateString()
                ? t('Hôm nay', 'Today')
                : t('Trước đó', 'Earlier')
            : null;
          return (
            <div key={s.id}>
              {groupLabel !== previousGroup && (
                <h2 className="session-group-label">{groupLabel}</h2>
              )}
              <div
                className={`session-item ${current?.id === s.id && route.path === '/tours' ? 'selected' : ''}`}
              >
                <a
                  href={`/tours?session=${s.id}`}
                  onClick={link(`/tours?session=${s.id}`)}
                  aria-current={
                    current?.id === s.id && route.path === '/tours' ? 'page' : undefined
                  }
                >
                  <span title={sessionName(s)}>{sessionName(s)}</span>
                  <small>
                    {new Date(s.updatedAt).toLocaleDateString(locale === 'vi' ? 'vi-VN' : 'en-GB', {
                      day: 'numeric',
                      month: 'short',
                    })}
                  </small>
                </a>
                <div className="session-actions">
                  <button
                    className="icon-button"
                    aria-label={s.pinned ? t('Bỏ ghim', 'Unpin') : t('Ghim phiên', 'Pin session')}
                    aria-pressed={s.pinned}
                    onClick={() => void updateMetadata(s, { pinned: !s.pinned })}
                  >
                    <Icon name="pin" size={15} />
                  </button>
                  <button
                    className="icon-button"
                    aria-label={t('Đổi tên phiên', 'Rename session')}
                    onClick={() => {
                      setRename(s);
                      setRenameValue(s.title);
                    }}
                  >
                    <Icon name="edit" size={15} />
                  </button>
                  <button
                    className="icon-button"
                    aria-label={t('Xóa phiên khỏi lịch sử', 'Remove session from history')}
                    onClick={() => setRemove(s)}
                  >
                    <Icon name="trash" size={15} />
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </nav>
      {profile && (
        <p className="form-hint">
          {t(
            'Đồng bộ tài khoản chưa được nối với backend hiện tại; các phiên guest vẫn lưu trong trình duyệt.',
            'Account sync is not connected to the current backend; guest sessions remain in this browser.',
          )}
        </p>
      )}
      <div className="sidebar-foot">
        <Icon name="user" />
        <div>
          <strong>{profile?.name || t('Phiên ẩn danh', 'Anonymous session')}</strong>
          <p>
            {profile
              ? t('Phiên guest trên trình duyệt', 'Guest sessions in this browser')
              : t('Lịch sử trên trình duyệt này', 'History on this browser')}
          </p>
        </div>
        <a
          className="icon-button"
          href="/account"
          onClick={link('/account')}
          aria-label={t('Tài khoản', 'Account')}
        >
          <Icon name="chevron" />
        </a>
      </div>
    </div>
  );

  return (
    <>
      <a className="skip-link" href="#main-content">
        {t('Đến nội dung chính', 'Skip to main content')}
      </a>
      <header className="site-header" ref={headerRef}>
        <div className="header-inner">
          <a className="brand" href="/" onClick={link('/')}>
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
            ].map(([url, text]) => (
              <a
                key={url}
                href={url}
                onClick={
                  url === '/tours'
                    ? (event) => {
                        if (isLinkClick(event)) {
                          event.preventDefault();
                          continueTours();
                        }
                      }
                    : link(url)
                }
                aria-current={route.path === url ? 'page' : undefined}
              >
                {text}
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
              onClick={link(profile ? '/account' : '/auth')}
            >
              <Icon name="user" />
              <span>{profile?.name || t('Đăng nhập', 'Sign in')}</span>
            </a>
          </div>
        </div>
      </header>
      <div className={`app-shell ${route.path === '/tours' ? 'workspace-open' : ''}`}>
        {route.path === '/tours' && <SessionSidebar>{sidebar('desktop')}</SessionSidebar>}
        <main
          id="main-content"
          className={route.path === '/tours' ? 'workspace-content' : 'page-content'}
          tabIndex={-1}
        >
          {storageError && (
            <p className="notice" role="status">
              {t(
                'Trình duyệt chưa lưu được lịch sử. Giữ tab này mở để tiếp tục phiên.',
                'History could not be saved. Keep this tab open to continue.',
              )}
            </p>
          )}
          {historyError && (
            <p className="notice notice-error" role="alert">
              {historyError}
            </p>
          )}
          {route.path === '/' && <LandingPage onStart={onStart} />}
          {route.path === '/auth' && (
            <section className="empty-state">
              <h1>{t('Đăng nhập chưa được nối.', 'Sign-in is not connected yet.')}</h1>
              <p>
                {t(
                  'Bạn vẫn có thể tìm tour bằng phiên guest; tài khoản sẽ được port sau với backend hiện tại.',
                  'You can search using a guest session; account support will be ported against the current backend later.',
                )}
              </p>
              <button className="btn btn-primary" onClick={continueTours}>
                {t('Tiếp tục với guest', 'Continue as guest')}
              </button>
            </section>
          )}
          {route.path === '/account' && (
            <section className="empty-state">
              <h1>{t('Tài khoản chưa khả dụng.', 'Account features are not available yet.')}</h1>
              <p>
                {t(
                  'Auth, đồng bộ lịch sử và quản lý dữ liệu tài khoản chưa có API runtime trên backend hiện tại.',
                  'Auth, history sync and account data management do not yet have runtime APIs on the current backend.',
                )}
              </p>
              <button className="btn btn-primary" onClick={continueTours}>
                {t('Tiếp tục với guest', 'Continue as guest')}
              </button>
            </section>
          )}
          {route.path === '/contact' && (
            <section className="empty-state">
              <h1>{t('Liên hệ chưa khả dụng.', 'Contact is not available yet.')}</h1>
              <p>
                {t(
                  'Form liên hệ sẽ chỉ được bật sau khi backend hiện tại có route tiếp nhận và lưu ticket.',
                  'The contact form will be enabled when the current backend has a ticket submission route.',
                )}
              </p>
              <button className="btn btn-primary" onClick={continueTours}>
                {t('Quay lại tìm tour', 'Return to tour search')}
              </button>
            </section>
          )}
          {route.path === '/support' && <SupportPage onStart={continueTours} />}
          {route.path === '/tours' && (
            <>
              <div className="workspace-toolbar">
                <button
                  className="icon-button history-toggle"
                  aria-label={t('Ẩn / hiện lịch sử phiên', 'Toggle session history')}
                  aria-expanded={drawer}
                  onClick={() => setDrawer(true)}
                >
                  <Icon name="menu" />
                </button>
                <span>{current ? sessionName(current) : t('Tìm tour', 'Find tours')}</span>
                <small>{profile ? profile.name : t('Phiên ẩn danh', 'Anonymous session')}</small>
              </div>
              {current ? (
                <CurrentWorkspace
                  session={current}
                  onChangeSession={(changes) => patchSession(current.id, changes)}
                />
              ) : (
                <section className="empty-state">
                  <h1>{t('Bắt đầu chuyến đi của bạn.', 'Start your trip.')}</h1>
                  <p>
                    {t(
                      'Tạo một phiên để lưu nhu cầu và các lượt so sánh.',
                      'Create a session for your requirements and comparisons.',
                    )}
                  </p>
                  <button className="btn btn-primary" onClick={startSession}>
                    {t('Phiên mới', 'New session')}
                    <Icon name="plus" />
                  </button>
                </section>
              )}
            </>
          )}
          {!['/', '/tours', '/auth', '/account', '/contact', '/support'].includes(route.path) && (
            <section className="empty-state">
              <h1>{t('Trang này không tồn tại.', 'This page could not be found.')}</h1>
              <a className="btn" href="/" onClick={link('/')}>
                {t('Về Giới thiệu', 'Back to About')}
                <Icon name="arrow" />
              </a>
            </section>
          )}
        </main>
      </div>
      <footer className="page-footer">
        <div className="footer-brand">
          <strong>đi cùng</strong>
          <p>
            {t('So sánh có nguồn, lựa chọn có cơ sở.', 'Sourced comparisons. Informed choices.')}
          </p>
        </div>
        {[
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
        ].map((group) => (
          <nav key={group.title} aria-label={group.title}>
            <h2>{group.title}</h2>
            {group.links.map(([url, label]) => (
              <a key={url} href={url} onClick={link(url)}>
                {label}
              </a>
            ))}
          </nav>
        ))}
      </footer>
      <Dialog
        open={drawer}
        onClose={() => setDrawer(false)}
        title={t('Lịch sử phiên', 'Session history')}
      >
        {sidebar('mobile')}
      </Dialog>
      <Dialog
        open={!!rename}
        onClose={() => setRename(null)}
        title={t('Đổi tên phiên', 'Rename session')}
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (rename) void updateMetadata(rename, { title: renameValue.trim() });
            setRename(null);
          }}
        >
          <label className="field">
            {t('Tên phiên', 'Session name')}
            <input
              required
              autoFocus
              maxLength={100}
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
            />
          </label>
          <button className="btn btn-primary">{t('Lưu tên', 'Save name')}</button>
        </form>
      </Dialog>
      <Dialog
        open={!!remove}
        onClose={() => setRemove(null)}
        title={t('Xóa khỏi lịch sử?', 'Remove from history?')}
      >
        <p>
          {t('Xóa bản lưu trên trình duyệt của phiên', 'Remove this browser’s saved session')} “
          {remove ? sessionName(remove) : ''}”.{' '}
          {t(
            'Tác vụ đang xử lý trên dịch vụ không bị hủy.',
            'Running service tasks will continue.',
          )}
        </p>
        <button
          className="btn danger"
          onClick={() => {
            if (remove)
              void archive(remove)
                .then(() => {
                  if (current?.id === remove.id) navigate('/tours');
                })
                .catch((cause: unknown) =>
                  setHistoryError(cause instanceof Error ? cause.message : 'Chưa ẩn được phiên.'),
                );
            setRemove(null);
          }}
        >
          {t('Xóa bản lưu', 'Remove saved session')}
        </button>
      </Dialog>
    </>
  );
}
