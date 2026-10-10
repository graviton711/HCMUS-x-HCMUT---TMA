import type { MouseEvent } from 'react';
import { normalizeSearch } from '../lib/normalize';
import type { AuthProfile, LocalSession } from '../model';
import { usePreferences } from '../../../shared/preferences';
import { Icon } from '../../../shared/ui';

export function SessionHistory({
  sessions,
  currentId,
  routePath,
  profile,
  filter,
  suffix,
  searchId,
  onFilterChange,
  onStart,
  onLink,
  onPin,
  onRename,
  onRemove,
}: {
  sessions: LocalSession[];
  currentId?: string;
  routePath: string;
  profile: AuthProfile | null;
  filter: string;
  suffix: string;
  searchId: string;
  onFilterChange: (value: string) => void;
  onStart: () => void;
  onLink: (url: string) => (event: MouseEvent<HTMLAnchorElement>) => void;
  onPin: (session: LocalSession) => void;
  onRename: (session: LocalSession) => void;
  onRemove: (session: LocalSession) => void;
}) {
  const { t, locale } = usePreferences();
  const sorted = [...sessions].sort(
    (a, b) =>
      Number(b.pinned) - Number(a.pinned) || Date.parse(b.updatedAt) - Date.parse(a.updatedAt),
  );
  const terms = normalizeSearch(filter).split(/\s+/u).filter(Boolean);
  const matching = sorted.filter((session) =>
    terms.every((term) => normalizeSearch(session.title).includes(term)),
  );
  const sessionName = (session: LocalSession) => session.title || t('Chuyến đi mới', 'New trip');

  return (
    <div className="sidebar-content">
      <div className="sidebar-heading">
        <button className="btn" onClick={onStart}>
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
          onChange={(event) => onFilterChange(event.target.value)}
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
        {matching.map((session, index) => {
          const today = new Date(session.updatedAt).toDateString() === new Date().toDateString();
          const previous = matching[index - 1];
          const groupLabel = session.pinned
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
          const selected = currentId === session.id && routePath === '/tours';
          const target = `/tours?session=${session.id}`;
          return (
            <div key={session.id}>
              {groupLabel !== previousGroup && (
                <h2 className="session-group-label">{groupLabel}</h2>
              )}
              <div className={`session-item ${selected ? 'selected' : ''}`}>
                <a
                  href={target}
                  onClick={onLink(target)}
                  aria-current={selected ? 'page' : undefined}
                >
                  <span title={sessionName(session)}>{sessionName(session)}</span>
                  <small>
                    {new Date(session.updatedAt).toLocaleDateString(
                      locale === 'vi' ? 'vi-VN' : 'en-GB',
                      { day: 'numeric', month: 'short' },
                    )}
                  </small>
                </a>
                <div className="session-actions">
                  <button
                    className="icon-button"
                    aria-label={
                      session.pinned ? t('Bỏ ghim', 'Unpin') : t('Ghim phiên', 'Pin session')
                    }
                    aria-pressed={session.pinned}
                    onClick={() => onPin(session)}
                  >
                    <Icon name="pin" size={15} />
                  </button>
                  <button
                    className="icon-button"
                    aria-label={t('Đổi tên phiên', 'Rename session')}
                    onClick={() => onRename(session)}
                  >
                    <Icon name="edit" size={15} />
                  </button>
                  <button
                    className="icon-button"
                    aria-label={t('Xóa phiên khỏi lịch sử', 'Remove session from history')}
                    onClick={() => onRemove(session)}
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
          onClick={onLink('/account')}
          aria-label={t('Tài khoản', 'Account')}
        >
          <Icon name="chevron" />
        </a>
      </div>
    </div>
  );
}
