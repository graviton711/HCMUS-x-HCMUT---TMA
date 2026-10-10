import { useEffect, useRef, useState, type FormEvent } from 'react';
import { authRequest, rememberProfile, type AuthProfile } from '../auth';
import { usePreferences } from '../preferences';
import { Avatar, prepareAvatar } from './Avatar';

export function ProfileEditor({
  profile,
  onChanged,
}: {
  profile: AuthProfile;
  onChanged: (p: AuthProfile) => void;
}) {
  const { t } = usePreferences();
  const [draft, setDraft] = useState(() => ({
    name: profile.name,
    phone: profile.phone ?? '',
    home_city: profile.home_city ?? '',
    bio: profile.bio ?? '',
  }));
  const [preview, setPreview] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const selection = useRef(0);
  const dirty = useRef(false);
  useEffect(() => {
    if (!dirty.current)
      setDraft({
        name: profile.name,
        phone: profile.phone ?? '',
        home_city: profile.home_city ?? '',
        bio: profile.bio ?? '',
      });
  }, [profile.name, profile.phone, profile.home_city, profile.bio]);
  useEffect(
    () => () => {
      selection.current++;
    },
    [],
  );
  const change = (key: keyof typeof draft, value: string) => {
    dirty.current = true;
    setDraft((d) => ({ ...d, [key]: value }));
    setMessage('');
    setError('');
  };
  async function save(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (!draft.name.trim()) {
      setError(t('Điền tên hiển thị của bạn.', 'Enter your display name.'));
      return;
    }
    if (!/^[0-9+().\s-]*$/.test(draft.phone)) {
      setError(
        t(
          'Số điện thoại chỉ gồm chữ số và dấu +, -, ngoặc hoặc khoảng trắng.',
          'Use digits, spaces, +, - or brackets for your phone number.',
        ),
      );
      return;
    }
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const next = rememberProfile(await authRequest('/auth/me', draft, 'PATCH'));
      dirty.current = false;
      setDraft({
        name: next.name,
        phone: next.phone ?? '',
        home_city: next.home_city ?? '',
        bio: next.bio ?? '',
      });
      onChanged(next);
      setMessage(t('Đã lưu hồ sơ.', 'Profile saved.'));
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : t('Chưa lưu được hồ sơ.', 'Unable to save your profile.'),
      );
    } finally {
      setBusy(false);
    }
  }
  async function photo(remove = false) {
    if (busy) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const result = remove
        ? await authRequest('/auth/me/avatar', undefined, 'DELETE')
        : await authRequest('/auth/me/avatar', { image: preview.split(',')[1] });
      onChanged(rememberProfile(result));
      setPreview('');
      setMessage(
        remove
          ? t('Đã gỡ ảnh đại diện.', 'Profile photo removed.')
          : t('Đã lưu ảnh đại diện.', 'Profile photo saved.'),
      );
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : t('Chưa lưu được ảnh.', 'Unable to save this photo.'),
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="account-panel profile-editor" aria-labelledby="profile-title">
      <div className="panel-heading">
        <span className="eyebrow">{t('MỘT CHÚT VỀ BẠN', 'A LITTLE ABOUT YOU')}</span>
        <h2 id="profile-title">{t('Hồ sơ cá nhân', 'Personal profile')}</h2>
        <p>{t('Để những chuyến đi có dấu ấn của bạn.', 'Make this space feel like yours.')}</p>
      </div>
      <div className="profile-photo-editor">
        <Avatar profile={profile} size="large" preview={preview} />
        <div>
          <h3>{t('Ảnh đại diện', 'Profile photo')}</h3>
          <p className="form-hint">
            {t(
              'JPG, PNG hoặc WebP · tối đa 5 MB. Ảnh được cắt vuông ở giữa.',
              'JPG, PNG or WebP · up to 5 MB. The center of your photo is cropped to a square.',
            )}
          </p>
          <div className="button-row">
            <label className="btn photo-picker">
              {t('Chọn ảnh', 'Choose photo')}
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                aria-label={t('Chọn ảnh đại diện', 'Choose profile photo')}
                disabled={busy}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  event.target.value = '';
                  const ticket = ++selection.current;
                  setError('');
                  setMessage('');
                  if (file) {
                    setBusy(true);
                    void prepareAvatar(file)
                      .then((url) => {
                        if (ticket === selection.current) setPreview(url);
                      })
                      .catch((cause: unknown) => {
                        if (ticket === selection.current)
                          setError(
                            cause instanceof Error
                              ? cause.message
                              : t('Ảnh không hợp lệ.', 'Invalid image.'),
                          );
                      })
                      .finally(() => {
                        if (ticket === selection.current) setBusy(false);
                      });
                  }
                }}
              />
            </label>
            {preview && (
              <>
                <button className="btn btn-primary" disabled={busy} onClick={() => void photo()}>
                  {t('Lưu ảnh', 'Save photo')}
                </button>
                <button
                  className="text-action"
                  disabled={busy}
                  onClick={() => {
                    selection.current++;
                    setPreview('');
                  }}
                >
                  {t('Hủy chọn', 'Cancel selection')}
                </button>
              </>
            )}
            {!preview &&
              profile.avatar_kind !== 'initials' &&
              (profile.avatar_url || profile.avatar_kind === 'uploaded') && (
                <button className="text-action" disabled={busy} onClick={() => void photo(true)}>
                  {t('Gỡ ảnh', 'Remove photo')}
                </button>
              )}
          </div>
        </div>
      </div>
      <form className="profile-form" onSubmit={(event) => void save(event)}>
        <div className="form-grid">
          <label className="field">
            {t('Tên hiển thị', 'Display name')}
            <input
              name="name"
              autoComplete="name"
              maxLength={80}
              required
              disabled={busy}
              value={draft.name}
              onChange={(e) => change('name', e.target.value)}
            />
          </label>
          <label className="field">
            {t('Email đăng nhập', 'Sign-in email')}
            <input
              type="email"
              aria-label={t('Email đăng nhập', 'Sign-in email')}
              readOnly
              value={profile.username}
            />
            <small>
              {t(
                'Email gắn với phương thức đăng nhập của bạn.',
                'This email belongs to your sign-in method.',
              )}
            </small>
          </label>
          <label className="field">
            {t('Số điện thoại', 'Phone number')}
            <input
              type="tel"
              autoComplete="tel"
              maxLength={25}
              disabled={busy}
              value={draft.phone}
              onChange={(e) => change('phone', e.target.value)}
              placeholder={t('Tùy chọn', 'Optional')}
            />
          </label>
          <label className="field">
            {t('Thành phố bạn sống', 'Home city')}
            <input
              autoComplete="address-level2"
              maxLength={80}
              disabled={busy}
              value={draft.home_city}
              onChange={(e) => change('home_city', e.target.value)}
              placeholder={t('Tùy chọn', 'Optional')}
            />
          </label>
        </div>
        <label className="field">
          {t('Giới thiệu ngắn', 'About you')}
          <textarea
            aria-label={t('Giới thiệu ngắn', 'About you')}
            rows={3}
            maxLength={280}
            disabled={busy}
            value={draft.bio}
            onChange={(e) => change('bio', e.target.value)}
            placeholder={t(
              'Một chút về bạn, những điều bạn thích…',
              'A little about you and what you enjoy…',
            )}
          />
          <small>
            {draft.bio.length}/280 · {t('Tùy chọn', 'Optional')}
          </small>
        </label>
        <div className="profile-form-footer">
          <p className="form-hint">
            {t(
              'Thông tin này không tự thay đổi nhu cầu tìm tour.',
              'These details do not automatically change your tour requirements.',
            )}
          </p>
          <button className="btn btn-primary" disabled={busy}>
            {busy ? t('Đang lưu…', 'Saving…') : t('Lưu hồ sơ', 'Save profile')}
          </button>
        </div>
      </form>
      {error && (
        <p className="notice notice-error" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="success-text" role="status">
          {message}
        </p>
      )}
    </section>
  );
}
