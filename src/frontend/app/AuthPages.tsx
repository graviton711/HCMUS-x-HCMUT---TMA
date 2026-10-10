import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Dialog } from '../components/Dialog';
import { Icon } from '../components/Icon';
import { usePreferences } from './preferences';

import {
  authConfig,
  authRequest,
  clearAuth,
  currentProfile,
  finishGoogle,
  profileFrom,
  readAuthProfile,
  returnUrl,
  saveAuth,
  startGoogle,
  type AuthProfile,
} from './auth';
export { readAuthProfile, type AuthProfile } from './auth';
function GoogleSymbol() {
  return (
    <svg className="google-symbol" width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M21.6 12.2c0-.7-.1-1.4-.2-2.1H12v4h5.4a4.6 4.6 0 0 1-2 3v2.6h3.3c1.9-1.8 2.9-4.4 2.9-7.5Z"
      />
      <path
        fill="#34A853"
        d="M12 22c2.7 0 5-.9 6.7-2.4l-3.3-2.6c-.9.6-2 .9-3.4.9a6 6 0 0 1-5.6-4.1H3v2.6A10 10 0 0 0 12 22Z"
      />
      <path fill="#FBBC05" d="M6.4 13.8a6.1 6.1 0 0 1 0-3.6V7.6H3a10 10 0 0 0 0 8.8l3.4-2.6Z" />
      <path
        fill="#EA4335"
        d="M12 6.1c1.5 0 2.8.5 3.8 1.5l2.9-2.9A9.6 9.6 0 0 0 12 2a10 10 0 0 0-9 5.6l3.4 2.6A6 6 0 0 1 12 6.1Z"
      />
    </svg>
  );
}
function PasswordField({
  name,
  label,
  autoComplete,
  error,
  disabled,
}: {
  name: string;
  label: string;
  autoComplete: string;
  error?: string;
  disabled: boolean;
}) {
  const [visible, setVisible] = useState(false);
  const { t } = usePreferences();
  return (
    <label className="field" htmlFor={name}>
      {label}
      <span className="password-input">
        <input
          name={name}
          id={name}
          type={visible ? 'text' : 'password'}
          required
          minLength={autoComplete === 'current-password' ? 1 : 8}
          maxLength={128}
          autoComplete={autoComplete}
          disabled={disabled}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${name}-error` : undefined}
        />
        <button
          type="button"
          className="password-toggle"
          onClick={() => setVisible(!visible)}
          aria-label={
            visible ? t('Ẩn mật khẩu', 'Hide password') : t('Hiện mật khẩu', 'Show password')
          }
          aria-pressed={visible}
        >
          <Icon name="eye" />
        </button>
      </span>
      {error && (
        <span className="field-error" id={`${name}-error`}>
          {error}
        </span>
      )}
    </label>
  );
}

export function AuthPage({
  onContinue,
  onAuthenticated,
}: {
  onContinue: () => void;
  onAuthenticated?: (profile: AuthProfile) => void;
}) {
  const { t } = usePreferences();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [config, setConfig] = useState({
    enabled: false,
    email_enabled: false,
    google_enabled: false,
  });
  const [success, setSuccess] = useState('');
  const hasAuthConfiguration = config.enabled && config.email_enabled;
  const googleEnabled = config.enabled && config.google_enabled;
  const register = mode === 'register';
  const authenticatedCallback = useRef(onAuthenticated);
  useEffect(() => {
    authenticatedCallback.current = onAuthenticated;
  }, [onAuthenticated]);
  useEffect(() => {
    const controller = new AbortController();
    void authConfig(controller.signal)
      .then(setConfig)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted)
          setError(cause instanceof Error ? cause.message : 'Chưa tải được cấu hình tài khoản.');
      });
    void finishGoogle()
      .then(async (profile) => profile ?? (readAuthProfile() ? await currentProfile() : null))
      .then((profile) => {
        if (!controller.signal.aborted && profile) authenticatedCallback.current?.(profile);
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted)
          setError(cause instanceof Error ? cause.message : 'Chưa đăng nhập được.');
      });
    return () => controller.abort();
  }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!hasAuthConfiguration || busy) return;
    const form = event.currentTarget;
    const values = new FormData(form);
    const name = String(values.get('name') ?? '').trim();
    const username = String(values.get('username') ?? '').trim();
    const password = String(values.get('password') ?? '');
    const confirmation = String(values.get('password_confirmation') ?? '');
    const invalid: Record<string, string> = {};
    if (register && !name) invalid.name = t('Nhập họ và tên.', 'Enter your full name.');
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(username) || username.length > 254)
      invalid.username = t('Nhập địa chỉ email hợp lệ.', 'Enter a valid email address.');
    if (password.length < (register ? 8 : 1))
      invalid.password = t(
        'Mật khẩu cần ít nhất 8 ký tự.',
        'Use at least 8 characters for your password.',
      );
    if (register && password !== confirmation)
      invalid.password_confirmation = t(
        'Mật khẩu xác nhận chưa khớp.',
        'The passwords do not match.',
      );
    setErrors(invalid);
    setError('');
    if (Object.keys(invalid).length) {
      form.querySelector<HTMLInputElement>(`[name="${Object.keys(invalid)[0]}"]`)?.focus();
      return;
    }
    setBusy(true);
    try {
      const result = await authRequest(
        register ? '/auth/register' : '/auth/login',
        register
          ? {
              name,
              email: username,
              password,
              password_confirmation: confirmation,
              return_url: returnUrl(),
            }
          : { email: username, password },
      );
      if (
        result &&
        typeof result === 'object' &&
        'status' in result &&
        result.status === 'confirmation_required'
      ) {
        form.reset();
        setSuccess(
          t(
            'Kiểm tra email để xác nhận tài khoản, sau đó quay lại đăng nhập.',
            'Check your email to confirm your account, then sign in.',
          ),
        );
        return;
      }
      const profile = saveAuth(result);
      form.reset();
      if (onAuthenticated) onAuthenticated(profile);
      else onContinue();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : t('Chưa đăng nhập được. Vui lòng thử lại.', 'Sign-in failed. Please try again.'),
      );
    } finally {
      setBusy(false);
    }
  }
  async function google() {
    setBusy(true);
    setError('');
    try {
      await startGoogle();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : t('Chưa mở được đăng nhập Google.', 'Google sign-in could not be opened.'),
      );
      setBusy(false);
    }
  }
  return (
    <section className="page auth-page" aria-labelledby="auth-heading">
      <button className="text-action back-link" onClick={onContinue}>
        <Icon name="left" />
        {t('Tiếp tục tìm tour', 'Continue finding tours')}
      </button>
      <div className="auth-layout">
        <aside className="auth-story">
          <span className="eyebrow">
            {t('MỘT CHUYẾN ĐI. NHIỀU GÓC NHÌN.', 'ONE TRIP. MANY PERSPECTIVES.')}
          </span>
          <h2>
            {t('Mỗi chuyến đi,', 'Every journey,')}
            <br />
            <em>{t('đều có thể tiếp nối.', 'can continue.')}</em>
          </h2>
          <p>
            {t(
              'Lưu những điều bạn đã hỏi, những tour đã tìm. Khi trở lại, bạn bắt đầu từ nơi mình dừng.',
              'Keep the questions you have asked and the tours you have found. When you return, pick up where you left off.',
            )}
          </p>
          <figure>
            <img
              src={`${import.meta.env.BASE_URL}assets/kyoto.jpg`}
              alt={t(
                'Những cổng torii nối tiếp nhau tại Kyoto',
                'A path through torii gates in Kyoto',
              )}
              width="1000"
              height="667"
            />
            <figcaption>{t('Kyoto, Nhật Bản', 'Kyoto, Japan')}</figcaption>
          </figure>
        </aside>
        <div className="auth-form-panel">
          <div className="auth-tabs">
            <button
              aria-pressed={!register}
              onClick={() => {
                setMode('login');
                setErrors({});
                setError('');
              }}
              disabled={busy}
            >
              {t('Đăng nhập', 'Sign in')}
            </button>
            <button
              aria-pressed={register}
              onClick={() => {
                setMode('register');
                setErrors({});
                setError('');
              }}
              disabled={busy}
            >
              {t('Tạo tài khoản', 'Create account')}
            </button>
          </div>
          <h1 id="auth-heading">
            {register
              ? t('Chuyến đi của riêng bạn.', 'Your own journey.')
              : t('Chào bạn trở lại.', 'Welcome back.')}
          </h1>
          <p className="auth-intro">
            {register
              ? t(
                  'Chỉ cần một vài thông tin để giữ lại những cuộc trò chuyện và lượt tìm tour.',
                  'A few details to keep your conversations and tour searches.',
                )
              : t(
                  'Đăng nhập để tiếp tục những điều bạn đang cân nhắc cho chuyến đi.',
                  'Sign in to continue exploring the options for your trip.',
                )}
          </p>
          {!hasAuthConfiguration && (
            <p className="notice auth-availability">
              {t(
                'Đăng nhập tài khoản chưa khả dụng. Bạn vẫn có thể tìm tour bằng phiên ẩn danh.',
                'Account sign-in is currently unavailable. You can still find tours with an anonymous session.',
              )}
            </p>
          )}
          <button
            className="google-button"
            onClick={() => {
              void google();
            }}
            disabled={!googleEnabled || busy}
          >
            <GoogleSymbol />
            {t('Tiếp tục bằng Google', 'Continue with Google')}
          </button>
          {!googleEnabled && (
            <p className="form-hint">
              {t('Đăng nhập Google chưa khả dụng.', 'Google sign-in is currently unavailable.')}
            </p>
          )}
          <div className="auth-divider">{t('hoặc bằng tài khoản', 'or with an account')}</div>
          <form className="auth-form" onSubmit={submit} noValidate key={mode}>
            {register && (
              <label className="field" htmlFor="auth-name">
                {t('Họ và tên', 'Full name')}
                <input
                  id="auth-name"
                  name="name"
                  autoComplete="name"
                  maxLength={80}
                  required
                  disabled={!hasAuthConfiguration || busy}
                  aria-invalid={Boolean(errors.name)}
                />
                {errors.name && <span className="field-error">{errors.name}</span>}
              </label>
            )}
            <label className="field" htmlFor="auth-username">
              {t('Email', 'Email')}
              <input
                id="auth-username"
                name="username"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                minLength={3}
                maxLength={254}
                type="email"
                required
                disabled={!hasAuthConfiguration || busy}
                aria-invalid={Boolean(errors.username)}
              />
              {errors.username && <span className="field-error">{errors.username}</span>}
            </label>
            <PasswordField
              name="password"
              label={t('Mật khẩu', 'Password')}
              autoComplete={register ? 'new-password' : 'current-password'}
              error={errors.password}
              disabled={!hasAuthConfiguration || busy}
            />
            {register && (
              <PasswordField
                name="password_confirmation"
                label={t('Xác nhận mật khẩu', 'Confirm password')}
                autoComplete="new-password"
                error={errors.password_confirmation}
                disabled={!hasAuthConfiguration || busy}
              />
            )}
            {success && (
              <p className="success-text" role="status">
                {success}
              </p>
            )}
            {error && (
              <p className="notice notice-error" role="alert">
                {error}
              </p>
            )}
            <button
              className="btn btn-primary auth-submit"
              type="submit"
              disabled={!hasAuthConfiguration || busy}
            >
              {busy
                ? t('Đang xử lý…', 'Please wait…')
                : register
                  ? t('Tạo tài khoản', 'Create account')
                  : t('Đăng nhập', 'Sign in')}
              <Icon name="arrow" />
            </button>
          </form>
          <div className="auth-footnote">
            <button className="text-action" onClick={onContinue}>
              {t('Tiếp tục với phiên ẩn danh', 'Continue with an anonymous session')}
              <Icon name="arrow" />
            </button>
            <p>
              {t(
                'Lịch sử phiên ẩn danh được lưu trên trình duyệt này.',
                'Anonymous session history is kept in this browser.',
              )}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

export interface AccountPageProps {
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
  onContinue,
  onSignedOut,
  onProfileChanged,
  onSignIn,
  onExportHistory,
  onDeleteHistory,
  sessionCount,
  onLinkGuestHistory,
  historyBusy,
}: AccountPageProps) {
  const { t } = usePreferences();
  const [profile, setProfile] = useState<AuthProfile | null>(readAuthProfile);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [deleteOpen, setDeleteOpen] = useState(false);
  useEffect(() => {
    if (!readAuthProfile()) return;
    const controller = new AbortController();
    void currentProfile(controller.signal)
      .then(setProfile)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setProfile(null);
          setError(
            cause instanceof Error
              ? cause.message
              : t('Chưa tải được hồ sơ.', 'Your profile could not be loaded.'),
          );
        }
      });
    return () => controller.abort();
  }, [t]);
  async function update(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const values = new FormData(event.currentTarget);
    const name = String(values.get('name') ?? '').trim();
    if (!name) {
      setError(t('Kiểm tra họ tên và tên tài khoản.', 'Check your full name and username.'));
      return;
    }
    setBusy(true);
    setError('');
    setSuccess('');
    try {
      const next = profileFrom(await authRequest('/auth/me', { name }, 'PATCH'));
      await currentProfile();
      setProfile(next);
      onProfileChanged?.(next);
      setSuccess(t('Đã lưu thông tin cá nhân.', 'Your profile has been saved.'));
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : t('Chưa lưu được hồ sơ.', 'Your profile could not be saved.'),
      );
    } finally {
      setBusy(false);
    }
  }
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
  if (!profile)
    return (
      <section className="page account-page">
        <div className="service-heading">
          <span className="eyebrow">{t('KHÔNG GIAN CỦA BẠN', 'YOUR SPACE')}</span>
          <h1>{t('Tài khoản của tôi.', 'My account.')}</h1>
          <p>
            {t(
              'Bạn đang dùng phiên ẩn danh. Lịch sử tìm tour được giữ trên trình duyệt này.',
              'You are using an anonymous session. Tour history is kept in this browser.',
            )}
          </p>
        </div>
        {error && (
          <p className="notice notice-error" role="alert">
            {error}
          </p>
        )}
        <div className="button-row">
          {onSignIn && (
            <button className="btn btn-primary" onClick={onSignIn}>
              {t('Đăng nhập', 'Sign in')}
            </button>
          )}
          <button className="btn" onClick={onContinue}>
            {t('Về phiên tìm tour', 'Back to your tour session')}
            <Icon name="arrow" />
          </button>
        </div>
        <section className="account-section">
          <h2>{t('Dữ liệu của bạn', 'Your data')}</h2>
          <p>
            {t(
              'Xuất hoặc xóa những phiên đã lưu trên trình duyệt này.',
              'Export or delete the sessions kept in this browser.',
            )}
          </p>
          <HistoryActions
            onExportHistory={onExportHistory}
            onDeleteHistory={() => setDeleteOpen(true)}
            canDelete={Boolean(onDeleteHistory)}
          />
        </section>
        <Dialog
          open={deleteOpen}
          onClose={() => setDeleteOpen(false)}
          title={t('Xóa lịch sử tìm tour?', 'Delete tour search history?')}
        >
          <p>
            {t(
              'Thao tác này xóa các phiên đã lưu trên trình duyệt này.',
              'This removes the sessions kept in this browser.',
            )}
          </p>
          <div className="dialog-actions">
            <button className="btn" onClick={() => setDeleteOpen(false)}>
              {t('Giữ lịch sử', 'Keep history')}
            </button>
            <button
              className="btn btn-danger"
              onClick={() => {
                onDeleteHistory?.();
                setDeleteOpen(false);
              }}
            >
              {t('Xóa lịch sử', 'Delete history')}
            </button>
          </div>
        </Dialog>
      </section>
    );
  return (
    <section className="page account-page" aria-labelledby="account-heading">
      <header className="account-heading">
        <span className="account-avatar">
          {profile.name
            .trim()
            .split(/\s+/)
            .slice(-2)
            .map((part) => part[0])
            .join('')
            .toLocaleUpperCase()}
        </span>
        <div>
          <span className="eyebrow">{t('KHÔNG GIAN CỦA BẠN', 'YOUR SPACE')}</span>
          <h1 id="account-heading">{t('Tài khoản của tôi.', 'My account.')}</h1>
          <p>
            {t(
              'Hồ sơ, cách đăng nhập và những chuyến đi đã lưu.',
              'Your profile, sign-in methods and saved journeys.',
            )}
          </p>
        </div>
      </header>
      <div className="account-layout">
        <nav className="account-subnav" aria-label={t('Cài đặt tài khoản', 'Account settings')}>
          <a href="#account-profile">
            <Icon name="user" />
            {t('Hồ sơ', 'Profile')}
          </a>
          <a href="#account-google">
            <Icon name="mail" />
            {t('Đăng nhập & liên kết', 'Sign-in and connections')}
          </a>
          <a href="#account-data">
            <Icon name="history" />
            {t('Dữ liệu của bạn', 'Your data')}
          </a>
          <button className="text-action" onClick={onContinue}>
            <Icon name="left" />
            {t('Về phiên tìm tour', 'Back to your tour session')}
          </button>
          <button
            className="text-action"
            onClick={() => {
              void logout();
            }}
            disabled={busy}
          >
            <Icon name="logout" />
            {t('Đăng xuất', 'Sign out')}
          </button>
        </nav>
        <div>
          {error && (
            <p className="notice notice-error" role="alert">
              {error}
            </p>
          )}
          <section className="account-section" id="account-profile">
            <h2>{t('Thông tin cá nhân', 'Personal information')}</h2>
            <p>
              {t(
                'Bạn có thể đổi tên hiển thị. Email được dùng để đăng nhập.',
                'You can change your display name. Your email is used to sign in.',
              )}
            </p>
            <form
              className="profile-form"
              onSubmit={update}
              key={`${profile.id}:${profile.username}:${profile.name}`}
            >
              <div className="form-grid">
                <label className="field">
                  {t('Họ và tên', 'Full name')}
                  <input
                    name="name"
                    autoComplete="name"
                    required
                    maxLength={80}
                    defaultValue={profile.name}
                    disabled={busy}
                  />
                </label>
                <label className="field">
                  {t('Email', 'Email')}
                  <input
                    name="username"
                    autoComplete="username"
                    autoCapitalize="none"
                    required
                    minLength={3}
                    maxLength={254}
                    type="email"
                    defaultValue={profile.username}
                    readOnly
                  />
                </label>
              </div>
              <button className="btn btn-primary" type="submit" disabled={busy}>
                {t('Lưu thay đổi', 'Save changes')}
                <Icon name="check" />
              </button>
              {success && (
                <p className="success-text" role="status">
                  {success}
                </p>
              )}
            </form>
          </section>
          <section className="account-section" id="account-google">
            <h2>{t('Đăng nhập & liên kết', 'Sign-in and connections')}</h2>
            <p>
              {t(
                'Google có thể được dùng làm phương thức đăng nhập.',
                'Google can be used as a sign-in method.',
              )}
            </p>
            <div className="connection-row">
              <GoogleSymbol />
              <div>
                <strong>Google</strong>
                <small>{profile.google_email ?? t('Chưa liên kết', 'Not connected')}</small>
              </div>
              <button className="btn" disabled>
                {profile.google_email
                  ? t('Ngắt liên kết', 'Disconnect')
                  : t('Liên kết Google', 'Connect Google')}
              </button>
            </div>
            <p className="form-hint">
              {t(
                'Quản lý liên kết Google chưa khả dụng. Không yêu cầu quyền đọc Gmail.',
                'Managing Google connections is currently unavailable. No Gmail reading access is requested.',
              )}
            </p>
          </section>
          <section className="account-section" id="account-data">
            <h2>{t('Dữ liệu của bạn', 'Your data')}</h2>
            <p>
              {sessionCount === undefined
                ? t(
                    'Các phiên tìm tour trên trình duyệt này.',
                    'The tour sessions kept in this browser.',
                  )
                : t(`${sessionCount} phiên đang hiển thị.`, `${sessionCount} sessions shown.`)}{' '}
              {t(
                'Nhu cầu đã gửi và cuộc trò chuyện được đồng bộ với tài khoản; bản nháp chưa gửi nằm trên trình duyệt.',
                'Submitted requirements and conversations are synced with your account; unsent drafts stay in this browser.',
              )}
            </p>
            <HistoryActions
              onExportHistory={onExportHistory}
              onDeleteHistory={() => setDeleteOpen(true)}
              canDelete={Boolean(onDeleteHistory)}
              account
              busy={historyBusy}
            />
            {onLinkGuestHistory && (
              <>
                <p>
                  {t(
                    'Nhập các phiên ẩn danh còn quyền truy cập trong tab này vào tài khoản. Phiên đang chạy cần hoàn tất trước.',
                    'Import anonymous sessions accessible in this tab into your account. Active jobs must finish first.',
                  )}
                </p>
                <button className="btn" disabled={historyBusy} onClick={onLinkGuestHistory}>
                  {t('Nhập lịch sử ẩn danh vào tài khoản', 'Import anonymous history')}
                </button>
              </>
            )}
          </section>
        </div>
      </div>
      <Dialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        title={t('Xóa lịch sử tìm tour?', 'Delete tour search history?')}
      >
        <p>
          {t(
            'Các phiên hiển thị sẽ được ẩn khỏi lịch sử tài khoản. Tác vụ và dữ kiện vẫn theo thời hạn lưu của backend.',
            'Displayed sessions will be archived from your account history. Jobs and evidence follow backend retention.',
          )}
        </p>
        <div className="dialog-actions">
          <button className="btn" onClick={() => setDeleteOpen(false)}>
            {t('Giữ lịch sử', 'Keep history')}
          </button>
          <button
            className="btn btn-danger"
            onClick={() => {
              onDeleteHistory?.();
              setDeleteOpen(false);
            }}
          >
            {t('Xóa lịch sử', 'Delete history')}
          </button>
        </div>
      </Dialog>
    </section>
  );
}
function HistoryActions({
  onExportHistory,
  onDeleteHistory,
  canDelete,
  account = false,
  busy = false,
}: {
  onExportHistory?: () => void;
  onDeleteHistory: () => void;
  canDelete: boolean;
  account?: boolean;
  busy?: boolean;
}) {
  const { t } = usePreferences();
  return (
    <>
      <div className="data-action-row">
        <div>
          <h3>{t('Xuất lịch sử', 'Export history')}</h3>
          <p>
            {t(
              'Tải nhu cầu và cuộc trò chuyện đã lưu dưới dạng JSON.',
              'Download your saved requirements and conversations as JSON.',
            )}
          </p>
        </div>
        <button className="btn" onClick={onExportHistory} disabled={!onExportHistory || busy}>
          <Icon name="download" />
          {t('Xuất dữ liệu', 'Export data')}
        </button>
      </div>
      <div className="data-action-row">
        <div>
          <h3>
            {account
              ? t('Ẩn lịch sử tài khoản', 'Archive account history')
              : t('Xóa lịch sử tìm tour', 'Delete tour history')}
          </h3>
          <p>
            {t(
              account
                ? 'Ẩn các hội thoại khỏi danh sách trên mọi thiết bị. Bản nháp chưa gửi được xóa trên máy này.'
                : 'Xóa các phiên được lưu trên trình duyệt này.',
              account
                ? 'Hide conversations on all devices. Unsent drafts are removed from this browser.'
                : 'Remove the sessions saved in this browser.',
            )}
          </p>
        </div>
        <button
          className="text-action danger-action"
          onClick={onDeleteHistory}
          disabled={!canDelete || busy}
        >
          {t('Xóa lịch sử', 'Delete history')}
        </button>
      </div>
    </>
  );
}
