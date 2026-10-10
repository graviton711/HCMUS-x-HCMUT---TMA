import { useCallback, useEffect, useId, useRef, useState, type MouseEvent } from 'react';
import { AccountPage, AuthPage, readAuthProfile, type AuthProfile } from './AuthPages';
import { ContactPage, LandingPage, SupportPage } from './PublicPages';
import { Footer } from './Footer';
import { PreferencesControl, usePreferences } from './preferences';
import {
  loadSessions,
  getAccess,
  newSession,
  normalizeSearch,
  removeAccess,
  saveSessions,
  type LocalSession,
} from './storage';
import { Dialog } from '../components/Dialog';
import { Icon } from '../components/Icon';
import { SessionSidebar } from '../components/SessionSidebar';
import { WorkspacePage } from '../features/workspace/WorkspacePage';
import { useWorkspace } from '../features/workspace/useWorkspace';
import { accountClient, allHistory, fromHistory } from './history';
import { ProfileHub } from './profile/ProfileHub';
import { Avatar } from './profile/Avatar';
import { useHub } from './profile/useHub';
import { templateFromDraft } from './profile/apply';
import { formFromRequirement, type FormValues } from '../api/form';

function locationState() {
  return {
    path: window.location.pathname.replace(/\/$/, '') || '/',
    search: window.location.search,
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
  const [profile, setProfile] = useState<AuthProfile | null>(readAuthProfile);
  const [drawer, setDrawer] = useState(false);
  const [filter, setFilter] = useState('');
  const [rename, setRename] = useState<LocalSession | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [remove, setRemove] = useState<LocalSession | null>(null);
  const [storageError, setStorageError] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const [historyBusy, setHistoryBusy] = useState(false);
  const [retention, setRetention] = useState<number | null>(null);
  const profileRef = useRef(profile);
  profileRef.current = profile;
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
  const workspace = useWorkspace(current, patchSession, profile?.id);
  const hub = useHub(profile?.id);
  const [hubMessage, setHubMessage] = useState('');
  const [templateCandidate, setTemplateCandidate] = useState<FormValues | null>(null);
  const [templateName, setTemplateName] = useState('');
  const [templateId, setTemplateId] = useState('');
  const reloadHistory = useCallback(async (signal?: AbortSignal) => {
    const owner = profileRef.current?.id;
    if (!owner) return;
    setHistoryBusy(true);
    setHistoryError('');
    try {
      const remote = await allHistory(accountClient(owner), signal);
      if (profileRef.current?.id !== owner || signal?.aborted) return;
      setRetention(remote.retention);
      setSessions((previous) => [
        ...previous.filter((s) => !s.requirementId),
        ...remote.items.map((item) => {
          const local = previous.find((s) => s.requirementId === item.requirement_id);
          if (local && (local.historyVersion ?? 0) > item.version) return local;
          return fromHistory(item, local);
        }),
      ]);
    } catch (cause) {
      if (!signal?.aborted && profileRef.current?.id === owner)
        setHistoryError(cause instanceof Error ? cause.message : 'Chưa tải được lịch sử.');
    } finally {
      if (!signal?.aborted && profileRef.current?.id === owner) setHistoryBusy(false);
    }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    if (profile?.id) void reloadHistory(controller.signal);
    else {
      setHistoryError('');
      setHistoryBusy(false);
      setRetention(null);
    }
    return () => controller.abort();
  }, [profile?.id, reloadHistory]);
  useEffect(() => {
    const changed = () => {
      const next = readAuthProfile();
      setProfile(next);
      if (!next) {
        setTemplateCandidate(null);
        setHubMessage('');
        setSessions(loadSessions());
      }
    };
    window.addEventListener('di-cung-auth', changed);
    return () => window.removeEventListener('di-cung-auth', changed);
  }, []);
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
    window.addEventListener('hashchange', back);
    return () => {
      window.removeEventListener('popstate', back);
      window.removeEventListener('hashchange', back);
    };
  }, []);
  useEffect(() => {
    document.title = `${route.path === '/tours' ? t('Tìm tour', 'Find tours') : route.path === '/auth' ? t('Tài khoản', 'Account') : 'Đi cùng'} · Đi cùng`;
  }, [route.path, t]);
  useEffect(() => {
    if (route.hash) {
      const target = document.getElementById(route.hash.slice(1));
      target?.focus({ preventScroll: true });
      target?.scrollIntoView({ block: 'start', behavior: 'instant' });
    }
  }, [route]);
  const navigate = (url: string) => {
    window.history.pushState(null, '', url);
    setRoute(locationState());
    setDrawer(false);
    if (locationState().path !== '/tours' && !locationState().hash)
      window.scrollTo({ top: 0, behavior: 'instant' });
  };
  const startSession = (draft?: FormValues, title?: string) => {
    const next = newSession();
    if (draft) next.draft = structuredClone(draft);
    if (title) next.title = title;
    setSessions((all) => [next, ...all]);
    navigate(`/tours?session=${next.id}`);
    setHubMessage(
      draft
        ? t(
            'Đã tạo bản nháp mới. Kiểm tra thông tin, chọn lại lịch/ngân sách và xác nhận trước khi tìm.',
            'New draft created. Review the details, set current dates/budget, and confirm before searching.',
          )
        : '',
    );
  };
  const continueTours = () => {
    if (sessions.length) navigate(`/tours?session=${sessions[0].id}`);
    else startSession();
  };
  const onStart = () => (profile ? continueTours() : navigate('/auth'));
  const changeProfile = (next: AuthProfile | null) => {
    setHubMessage('');
    setTemplateCandidate(null);
    setProfile(next);
    setSessions(loadSessions(next?.id));
    navigate(next ? '/tours' : '/auth');
  };
  const updateMetadata = async (
    session: LocalSession,
    changes: { title?: string; pinned?: boolean },
  ) => {
    const owner = profileRef.current?.id;
    try {
      if (owner && session.requirementId) {
        const result = await accountClient(owner).editHistory(session.requirementId, {
          expected_version: session.historyVersion ?? 0,
          ...changes,
        });
        if (profileRef.current?.id !== owner) return;
        patchSession(session.id, {
          title: result.title,
          pinned: result.pinned,
          historyVersion: result.version,
        });
      } else patchSession(session.id, changes);
    } catch (cause) {
      setHistoryError(cause instanceof Error ? cause.message : 'Chưa lưu được lịch sử.');
    }
  };
  const archive = async (session: LocalSession) => {
    const owner = profileRef.current?.id;
    if (owner && session.requirementId)
      await accountClient(owner).archiveHistory(session.requirementId, session.historyVersion ?? 0);
    if (profileRef.current?.id !== owner) return;
    setSessions((all) => all.filter((s) => s.id !== session.id));
    removeAccess(session.id);
  };
  const deleteHistory = async () => {
    setHistoryBusy(true);
    setHistoryError('');
    try {
      for (const session of sessions) await archive(session);
    } catch (cause) {
      setHistoryError(cause instanceof Error ? cause.message : 'Chưa ẩn hết lịch sử.');
    } finally {
      setHistoryBusy(false);
    }
  };
  const linkGuestHistory = async () => {
    const owner = profileRef.current?.id;
    if (!owner || historyBusy) return;
    setHistoryBusy(true);
    setHistoryError('');
    try {
      let guests = loadSessions();
      const missing = guests.some((s) => s.requirementId && !getAccess(s.id));
      for (const guest of guests.filter((s) => s.requirementId && getAccess(s.id))) {
        await accountClient(owner).linkHistory(getAccess(guest.id)!.token);
        if (profileRef.current?.id !== owner) return;
        const detail = await accountClient(owner).historyDetail(guest.requirementId!);
        await accountClient(owner).editHistory(guest.requirementId!, {
          expected_version: detail.version,
          title: guest.title,
          pinned: guest.pinned,
        });
        if (profileRef.current?.id !== owner) return;
        removeAccess(guest.id);
        guests = guests.filter((s) => s.id !== guest.id);
        saveSessions(guests);
      }
      await reloadHistory();
      if (missing)
        setHistoryError(
          'Một số phiên ẩn danh không còn token trong tab này hoặc đã hết hạn; bản lưu vẫn được giữ.',
        );
    } catch (cause) {
      setHistoryError(cause instanceof Error ? cause.message : 'Chưa nhập được phiên ẩn danh.');
    } finally {
      setHistoryBusy(false);
    }
  };
  const link = (url: string) => (event: MouseEvent<HTMLAnchorElement>) => {
    if (isLinkClick(event)) {
      event.preventDefault();
      navigate(url);
    }
  };
  const exportHistory = async () => {
    const owner = profileRef.current?.id;
    setHistoryBusy(true);
    setHistoryError('');
    try {
      const exported = owner
        ? await (async () => {
            const client = accountClient(owner);
            const remote = await allHistory(client);
            const details = [];
            for (const item of remote.items)
              details.push(await client.historyDetail(item.requirement_id));
            return {
              retention_days: remote.retention,
              conversations: details,
              unsent_drafts: sessions.filter((s) => !s.requirementId),
              limited: details.some((d) => d.transcript.limited || d.runs_limited),
            };
          })()
        : { sessions };
      if (profileRef.current?.id !== owner) return;
      const url = URL.createObjectURL(
        new Blob([JSON.stringify({ exportedAt: new Date().toISOString(), ...exported }, null, 2)], {
          type: 'application/json',
        }),
      );
      const a = document.createElement('a');
      a.href = url;
      a.download = 'di-cung-history.json';
      a.click();
      URL.revokeObjectURL(url);
      if ('limited' in exported && exported.limited)
        setHistoryError(
          'Đã xuất dữ liệu; một số hội thoại dài được giới hạn. File có đánh dấu limited.',
        );
    } catch (cause) {
      setHistoryError(cause instanceof Error ? cause.message : 'Chưa xuất được lịch sử.');
    } finally {
      setHistoryBusy(false);
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
        <button className="btn" onClick={() => startSession()}>
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
                    disabled={historyBusy}
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
        <>
          <button
            className="btn"
            disabled={historyBusy || workspace.state.busy}
            onClick={() => void reloadHistory()}
          >
            {t('Tải lại lịch sử tài khoản', 'Reload account history')}
          </button>
          {retention !== null && (
            <p className="form-hint">
              {t(
                `Hệ thống lưu lịch sử trong: ${retention} ngày. Bản nháp chưa gửi lưu trên máy này.`,
                `History retention: ${retention} days. Unsent drafts stay in this browser.`,
              )}
            </p>
          )}
        </>
      )}
      <div className="sidebar-foot">
        <Icon name="user" />
        <div>
          <strong>{profile?.name || t('Phiên ẩn danh', 'Anonymous session')}</strong>
          <p>
            {profile
              ? t('Lịch sử tài khoản', 'Account history')
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
      <Dialog
        open={templateCandidate !== null}
        onClose={() => {
          if (!hub.busy) setTemplateCandidate(null);
        }}
        title={t('Lưu mẫu nhu cầu', 'Save requirement template')}
      >
        <p>
          {t(
            'Mẫu giữ nơi đi/đến, số người và ưu tiên mềm. Lịch, ngân sách và tuổi trẻ em cần nhập lại cho chuyến mới.',
            'Templates keep places, party counts and soft preferences. Dates, budget and child ages must be entered again for a new trip.',
          )}
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!templateCandidate || !templateName.trim()) return;
            void hub
              .mutate('templates', {
                item_id: templateId,
                expected_version: 0,
                template: templateFromDraft(templateCandidate, templateName),
              })
              .then(() => {
                setTemplateCandidate(null);
                setHubMessage(t('Đã lưu mẫu vào Tài khoản.', 'Template saved to your account.'));
              })
              .catch(() => {});
          }}
        >
          <label className="field">
            {t('Tên mẫu', 'Template name')}
            <input
              required
              maxLength={80}
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
            />
          </label>
          {hub.error && (
            <p className="notice notice-error" role="alert">
              {hub.error}
            </p>
          )}
          <div className="button-row">
            <button
              type="button"
              className="btn"
              disabled={hub.busy}
              onClick={() => setTemplateCandidate(null)}
            >
              {t('Hủy', 'Cancel')}
            </button>
            <button className="btn btn-primary" disabled={hub.busy || !templateName.trim()}>
              {t('Lưu mẫu', 'Save template')}
            </button>
          </div>
        </form>
      </Dialog>
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
              className={`account-link ${profile ? 'account-avatar-link' : ''}`}
              aria-label={
                profile
                  ? t(`Tài khoản của ${profile.name}`, `Account for ${profile.name}`)
                  : t('Đăng nhập', 'Sign in')
              }
              title={profile?.name || t('Đăng nhập', 'Sign in')}
              href={profile ? '/account' : '/auth'}
              onClick={link(profile ? '/account' : '/auth')}
            >
              {profile ? (
                <Avatar profile={profile} />
              ) : (
                <>
                  <Icon name="user" />
                  <span>{t('Đăng nhập', 'Sign in')}</span>
                </>
              )}
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
          {historyBusy && (
            <p className="notice" role="status">
              {t('Đang đồng bộ lịch sử…', 'Syncing history…')}
            </p>
          )}
          {historyError && (
            <p className="notice notice-error" role="alert">
              {historyError}
            </p>
          )}
          {route.path === '/' && <LandingPage onStart={onStart} />}
          {route.path === '/auth' && (
            <AuthPage onContinue={continueTours} onAuthenticated={changeProfile} />
          )}
          {route.path === '/account' && (
            <AccountPage
              key={profile?.id ?? 'guest'}
              hub={(view) => (
                <ProfileHub
                  key={profile?.id ?? 'guest'}
                  owner={profile?.id}
                  view={view}
                  hub={hub}
                  sessions={sessions}
                  retention={retention}
                  historyBusy={historyBusy}
                  onNew={startSession}
                  onOpen={(id) => navigate(`/tours?session=${id}`)}
                  onPin={(s) => void updateMetadata(s, { pinned: !s.pinned })}
                  onArchive={setRemove}
                  onSignIn={() => navigate('/auth')}
                />
              )}
              onContinue={continueTours}
              onSignedOut={() => changeProfile(null)}
              onProfileChanged={setProfile}
              onSignIn={() => navigate('/auth')}
              onExportHistory={exportHistory}
              onDeleteHistory={deleteHistory}
              sessionCount={sessions.length}
              onLinkGuestHistory={() => void linkGuestHistory()}
              historyBusy={historyBusy}
            />
          )}
          {route.path === '/contact' && (
            <ContactPage requestedCategory={new URLSearchParams(route.search).get('category')} />
          )}
          {route.path === '/support' && <SupportPage onStart={continueTours} link={link} />}
          {route.path === '/tours' && (
            <>
              {hubMessage && (
                <p className="notice" role="status">
                  {hubMessage}
                </p>
              )}
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
                <WorkspacePage
                  personalBusy={hub.busy}
                  onSaveTour={
                    profile && hub.data
                      ? async (comparisonId, columnId, url) => {
                          setHubMessage('');
                          try {
                            const old = hub.data?.saved_tours.find((i) => i.value.url === url);
                            await hub.mutate('saved-tours', {
                              expected_version: old?.version ?? 0,
                              comparison_id: comparisonId,
                              column_id: columnId,
                            });
                            setHubMessage(
                              t(
                                'Đã lưu tour vào Tài khoản. Đây là dữ liệu tại lúc lưu, cần kiểm tra lại trước khi đặt.',
                                'Saved to your account. This is a historical snapshot; recheck before booking.',
                              ),
                            );
                          } catch (e) {
                            setHubMessage(
                              e instanceof Error
                                ? e.message
                                : t('Chưa lưu được tour.', 'Unable to save tour.'),
                            );
                          }
                        }
                      : undefined
                  }
                  onSaveTemplate={
                    profile && hub.data
                      ? () => {
                          if (!workspace.state.requirement) return;
                          setTemplateCandidate(formFromRequirement(workspace.state.requirement));
                          setTemplateId(crypto.randomUUID());
                          setTemplateName(current.title || t('Mẫu chuyến đi', 'Trip template'));
                        }
                      : undefined
                  }
                  session={current}
                  workspace={workspace}
                  onDraft={(draft) => patchSession(current.id, { draft })}
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
                  <button className="btn btn-primary" onClick={() => startSession()}>
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
      <Footer link={link} />
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
          {profile
            ? t('Ẩn khỏi lịch sử tài khoản', 'Archive from your account history')
            : t(
                'Xóa bản lưu trên trình duyệt của phiên',
                'Remove this browser’s saved session',
              )}{' '}
          “{remove ? sessionName(remove) : ''}”.{' '}
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
