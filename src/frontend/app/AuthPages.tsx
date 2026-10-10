import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Icon } from '../components/Icon';
import { usePreferences } from './preferences';

import {
  authConfig,
  authRequest,
  currentProfile,
  finishGoogle,
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

export { AccountPage, type AccountPageProps } from './profile/AccountHub';
