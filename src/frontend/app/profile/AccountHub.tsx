import { useEffect, useState, type ReactNode } from 'react';
import { Dialog } from '../../components/Dialog';
import { Icon } from '../../components/Icon';
import { authRequest, clearAuth, currentProfile, readAuthProfile, type AuthProfile } from '../auth';
import { PreferencesControl, usePreferences } from '../preferences';
import { Avatar } from './Avatar';
import { ProfileEditor } from './ProfileEditor';
import type { HubView } from './ProfileHub';

type View = Exclude<HubView, 'data'> | 'profile' | 'settings';
const views: View[] = ['overview', 'saved', 'preferences', 'templates', 'profile', 'settings'];
function initialView(): View {
  const section = new URLSearchParams(window.location.search).get('section') as View;
  if (!readAuthProfile() && section !== 'settings') return 'overview';
  return views.includes(section) ? section : 'overview';
}
export interface AccountPageProps {
  hub?: (view: HubView) => ReactNode;
  onContinue: () => void;
  onSignedOut?: () => void;
  onProfileChanged?: (profile: AuthProfile) => void;
  onSignIn?: () => void;
  onExportHistory?: () => void;
  onDeleteHistory?: () => void;
  sessionCount?: number;
  onLinkGuestHistory?: () => void;
  historyBusy?: boolean;
}
export function AccountPage({
  hub,
  onContinue,
  onSignedOut,
  onProfileChanged,
  onSignIn,
  onExportHistory,
  onDeleteHistory,
  sessionCount = 0,
  onLinkGuestHistory,
  historyBusy = false,
}: AccountPageProps) {
  const { t } = usePreferences();
  const [profile, setProfile] = useState<AuthProfile | null>(readAuthProfile);
  const [view, setView] = useState<View>(initialView);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [deleteOpen, setDeleteOpen] = useState(false);
  useEffect(() => {
    const changed = () => setView(initialView());
    window.addEventListener('popstate', changed);
    return () => window.removeEventListener('popstate', changed);
  }, []);
  useEffect(() => {
    if (!readAuthProfile()) return;
    const controller = new AbortController();
    void currentProfile(controller.signal)
      .then((p) => {
        setProfile(p);
        onProfileChanged?.(p);
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted)
          setError(
            cause instanceof Error
              ? cause.message
              : t('Chưa tải được hồ sơ.', 'Unable to load your profile.'),
          );
      });
    return () => controller.abort();
  }, [t, onProfileChanged]);
  const select = (next: View) => {
    setView(next);
    const url = new URL(window.location.href);
    url.searchParams.set('section', next);
    window.history.replaceState(null, '', url);
  };
  async function logout() {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      await authRequest('/auth/logout', {}, 'POST');
      clearAuth();
      setProfile(null);
      onSignedOut?.();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : t('Chưa đăng xuất được.', 'Sign-out failed.'),
      );
    } finally {
      setBusy(false);
    }
  }
  const labels = {
    overview: t('Tổng quan', 'Overview'),
    saved: t('Tour lưu', 'Saved tours'),
    preferences: t('Sở thích', 'Preferences'),
    templates: t('Mẫu nhu cầu', 'Templates'),
    profile: t('Hồ sơ', 'Profile'),
    settings: t('Cài đặt', 'Settings'),
  };
  const icons = {
    overview: 'history',
    saved: 'pin',
    preferences: 'sliders',
    templates: 'route',
    profile: 'user',
    settings: 'more',
  };
  const exportProfile = () => {
    if (!profile) return;
    const information = Object.fromEntries(
      Object.entries(profile).filter(([key]) => key !== 'avatar_url'),
    );
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(information, null, 2)], { type: 'application/json' }),
    );
    const a = document.createElement('a');
    a.href = url;
    a.download = 'di-cung-personal-profile.json';
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <section
      className="page account-page account-hub"
      aria-label={t('Không gian của bạn', 'Your space')}
    >
      <div className="account-layout">
        <aside className="account-sidebar">
          <div className="account-identity">
            {profile ? (
              <Avatar profile={profile} size="large" />
            ) : (
              <span className="guest-avatar">
                <Icon name="user" size={28} />
              </span>
            )}
            <div>
              <span className="eyebrow">{t('KHÔNG GIAN CỦA BẠN', 'YOUR SPACE')}</span>
              <h1>{profile?.name || t('Khách ghé thăm', 'Welcome, traveler')}</h1>
              <p>{profile?.username || t('Phiên ẩn danh', 'Anonymous session')}</p>
            </div>
          </div>
          <nav className="account-nav" aria-label={t('Mục tài khoản', 'Account sections')}>
            {views
              .filter((v) => profile || ['overview', 'settings'].includes(v))
              .map((v) => (
                <button
                  key={v}
                  aria-current={view === v ? 'page' : undefined}
                  onClick={() => select(v)}
                >
                  <Icon name={icons[v]} />
                  <span>{labels[v]}</span>
                  <Icon name="arrow" size={16} />
                </button>
              ))}
          </nav>
          <div className="account-sidebar-actions">
            <button className="text-action" onClick={onContinue}>
              <Icon name="left" />
              {t('Về phiên tìm tour', 'Back to tour search')}
            </button>
            {profile ? (
              <button className="text-action" disabled={busy} onClick={() => void logout()}>
                <Icon name="logout" />
                {t('Đăng xuất', 'Sign out')}
              </button>
            ) : (
              <button className="btn" onClick={onSignIn}>
                {t('Đăng nhập', 'Sign in')}
              </button>
            )}
          </div>
        </aside>
        <div className="account-content">
          {error && (
            <p className="notice notice-error" role="alert">
              {error}
            </p>
          )}
          {profile && (
            <div hidden={view !== 'profile'}>
              <ProfileEditor
                key={profile.id}
                profile={profile}
                onChanged={(p) => {
                  setProfile(p);
                  onProfileChanged?.(p);
                }}
              />
            </div>
          )}
          <div hidden={view !== 'settings'} className="account-panel account-settings">
            <div className="panel-heading">
              <span className="eyebrow">{t('THEO CÁCH CỦA BẠN', 'YOUR WAY')}</span>
              <h2>{t('Cài đặt tài khoản', 'Account settings')}</h2>
              <p>
                {t(
                  'Cách đăng nhập, hiển thị và dữ liệu bạn đã lưu.',
                  'Sign-in, appearance and the data you keep.',
                )}
              </p>
            </div>
            {profile && (
              <section className="account-section">
                <h3>{t('Đăng nhập', 'Sign-in')}</h3>
                <div className="sign-in-status">
                  <Icon name="mail" />
                  <div>
                    <strong>{profile.username}</strong>
                    <small>
                      {profile.google_email
                        ? t('Đã kết nối Google', 'Connected with Google')
                        : t('Tài khoản email', 'Email account')}
                    </small>
                  </div>
                  <span className="status-pill">
                    <Icon name="check" />
                    {t('Đang đăng nhập', 'Signed in')}
                  </span>
                </div>
              </section>
            )}
            <section className="account-section settings-display">
              <div>
                <h3>{t('Ngôn ngữ & giao diện', 'Language & appearance')}</h3>
                <p className="form-hint">
                  {t('Lưu trên trình duyệt này.', 'Saved in this browser.')}
                </p>
              </div>
              <PreferencesControl />
            </section>
            {profile && (
              <section className="account-section">
                <h3>{t('Thông tin hồ sơ', 'Profile information')}</h3>
                <div className="data-action-row">
                  <p className="form-hint">
                    {t(
                      'Tải tên và thông tin cá nhân bạn đã điền. Chỉnh sửa hoặc xóa nội dung trong mục Hồ sơ.',
                      'Download your name and personal details. Edit or clear them in Profile.',
                    )}
                  </p>
                  <button className="btn" onClick={exportProfile}>
                    <Icon name="download" />
                    {t('Xuất hồ sơ', 'Export profile')}
                  </button>
                </div>
              </section>
            )}
            <section className="account-section">
              <h3>{t('Lịch sử tìm tour', 'Tour search history')}</h3>
              <p className="form-hint">
                {t(`${sessionCount} phiên đang hiển thị.`, `${sessionCount} searches shown.`)}{' '}
                {profile
                  ? t(
                      'Nhu cầu đã gửi được đồng bộ với tài khoản; bản nháp nằm trên trình duyệt.',
                      'Submitted searches sync with your account; drafts stay in this browser.',
                    )
                  : t(
                      'Phiên ẩn danh được lưu trên trình duyệt này.',
                      'Anonymous sessions stay in this browser.',
                    )}
              </p>
              <div className="button-row">
                <button
                  className="btn"
                  onClick={onExportHistory}
                  disabled={!onExportHistory || historyBusy}
                >
                  <Icon name="download" />
                  {t('Xuất lịch sử', 'Export history')}
                </button>
                <button
                  className="text-action danger-action"
                  disabled={!onDeleteHistory || historyBusy || !sessionCount}
                  onClick={() => setDeleteOpen(true)}
                >
                  {profile
                    ? t('Ẩn lịch sử tài khoản', 'Archive account history')
                    : t('Xóa lịch sử', 'Delete history')}
                </button>
              </div>
              {profile && onLinkGuestHistory && (
                <details className="account-import">
                  <summary>
                    {t('Chuyển lịch sử ẩn danh vào tài khoản', 'Import anonymous history')}
                  </summary>
                  <p className="form-hint">
                    {t(
                      'Chỉ nhập các phiên còn quyền truy cập trong tab này. Phiên đang chạy cần hoàn tất trước.',
                      'Import only sessions accessible in this tab. Active searches must finish first.',
                    )}
                  </p>
                  <button className="btn" disabled={historyBusy} onClick={onLinkGuestHistory}>
                    {t('Nhập lịch sử ẩn danh', 'Import anonymous history')}
                  </button>
                </details>
              )}
            </section>
          </div>
          <div
            hidden={view === 'profile'}
            className={view === 'settings' ? 'account-hub-data' : ''}
          >
            {view === 'settings' && !profile
              ? null
              : hub?.(view === 'settings' ? 'data' : view === 'profile' ? 'overview' : view)}
          </div>
        </div>
      </div>
      <Dialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        title={
          profile
            ? t('Ẩn lịch sử tìm tour?', 'Archive tour search history?')
            : t('Xóa lịch sử tìm tour?', 'Delete tour search history?')
        }
      >
        <p>
          {profile
            ? t(
                'Các phiên sẽ được ẩn khỏi lịch sử tài khoản. Bản nháp trên máy này được xóa; tác vụ và dữ kiện vẫn theo thời hạn lưu.',
                'Searches will be archived from account history. Local drafts are removed; jobs and evidence follow their retention policy.',
              )
            : t(
                'Các phiên trên trình duyệt này sẽ bị xóa.',
                'Sessions in this browser will be deleted.',
              )}
        </p>
        <div className="dialog-actions">
          <button className="btn" onClick={() => setDeleteOpen(false)}>
            {t('Giữ lịch sử', 'Keep history')}
          </button>
          <button
            className="btn btn-danger"
            disabled={historyBusy}
            onClick={() => {
              onDeleteHistory?.();
              setDeleteOpen(false);
            }}
          >
            {profile ? t('Ẩn lịch sử', 'Archive history') : t('Xóa lịch sử', 'Delete history')}
          </button>
        </div>
      </Dialog>
    </section>
  );
}
