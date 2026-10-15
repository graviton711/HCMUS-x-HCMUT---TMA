import type { MouseEvent } from 'react';
import { normalizeSearch } from '../lib/normalize';
import type { LocalSession } from '../model';
import { displaySessionTitle } from '../../../shared/lib';
import { usePreferences } from '../../../shared/preferences';
import { ActionMenu, Icon } from '../../../shared/ui';

export function SessionHistory({
  sessions,
  currentId,
  routePath,
  filter,
  suffix,
  searchId,
  onFilterChange,
  onLink,
  onPin,
  onRename,
  onRemove,
}: {
  sessions: LocalSession[];
  currentId?: string;
  routePath: string;
  filter: string;
  suffix: string;
  searchId: string;
  onFilterChange: (value: string) => void;
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
    terms.every((term) => normalizeSearch(displaySessionTitle(session.title, '')).includes(term)),
  );
  const fallbackName = t('Chuyến đi mới', 'New trip');
  const sessionName = (session: LocalSession) => displaySessionTitle(session.title, fallbackName);

  return (
    <div className="sidebar-content">
      <label className="sidebar-search" htmlFor={`${searchId}-${suffix}`}>
        <Icon name="search" size={15} />
        <span className="sr-only">{t('Tìm phiên', 'Search sessions')}</span>
        <input
          id={`${searchId}-${suffix}`}
          value={filter}
          onChange={(event) => onFilterChange(event.target.value)}
          placeholder={t('Tìm trong lịch sử', 'Search history')}
        />
      </label>

      <h2 className="session-group-label">{t('Phiên gần đây', 'Recent searches')}</h2>

      <nav aria-label={t('Lịch sử phiên', 'Session history')} className="session-list">
        {matching.length === 0 && (
          <p className="form-hint">
            {sessions.length
              ? t('Không tìm thấy phiên phù hợp.', 'No matching sessions.')
              : t('Chuyến đi đầu tiên đang chờ bạn.', 'Your first trip is waiting.')}
          </p>
        )}
        {matching.map((session) => {
          const selected =
            currentId === session.id && (routePath === '/tours' || routePath === '/');
          const target = `/?session=${session.id}`;
          return (
            <div key={session.id} className={`session-item ${selected ? 'selected' : ''}`}>
              <a
                href={target}
                onClick={onLink(target)}
                aria-current={selected ? 'page' : undefined}
              >
                <span className="session-name" title={sessionName(session)}>
                  {session.pinned && <Icon name="pin" size={13} />}
                  {sessionName(session)}
                </span>
                <small className="session-date">
                  {new Date(session.updatedAt).toLocaleDateString(
                    locale === 'vi' ? 'vi-VN' : 'en-GB',
                    { day: 'numeric', month: 'short' },
                  )}
                </small>
              </a>
              <div className="session-actions">
                <button
                  type="button"
                  className="icon-button"
                  aria-label={
                    session.pinned ? t('Bỏ ghim', 'Unpin') : t('Ghim phiên', 'Pin session')
                  }
                  aria-pressed={session.pinned}
                  onClick={() => onPin(session)}
                >
                  <Icon name="pin" size={14} />
                </button>
                <ActionMenu
                  label={t('Tùy chọn phiên', 'Session options')}
                  items={[
                    {
                      label: t('Đổi tên', 'Rename'),
                      icon: 'edit',
                      onSelect: () => onRename(session),
                    },
                    {
                      label: t('Xóa khỏi lịch sử', 'Remove from history'),
                      icon: 'trash',
                      destructive: true,
                      separatorBefore: true,
                      onSelect: () => onRemove(session),
                    },
                  ]}
                />
              </div>
            </div>
          );
        })}
      </nav>
    </div>
  );
}
