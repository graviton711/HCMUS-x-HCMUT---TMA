import { useEffect, useLayoutEffect, useState } from 'react';
import {
  readAuthProfile,
  SessionHistoryPanel,
  useLocalSessions,
  useSidebarLayout,
  type AuthProfile,
  type LocalSession,
} from '../features/session-history';
import { PreferencesControl } from '../features/preferences';
import { SupportPage, UnavailablePage } from '../pages/public';
import { WorkspacePage } from '../pages/workspace';
import { ChatPage } from '../pages/chat';
import { usePreferences } from '../shared/preferences';
import { useNavigation } from './routing';
import { AppFooter, AppHeader, SessionBar } from './shell';
import { displaySessionTitle } from '../shared/lib';
import styles from './shell/AppShell.module.css';

const knownRoutes = new Set(['/', '/tours', '/auth', '/account', '/contact', '/support']);

function useIsDesktop() {
  const [desktop, setDesktop] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(min-width: 1001px)').matches,
  );
  useEffect(() => {
    const query = window.matchMedia('(min-width: 1001px)');
    const onChange = () => setDesktop(query.matches);
    query.addEventListener('change', onChange);
    return () => query.removeEventListener('change', onChange);
  }, []);
  return desktop;
}

export function App() {
  const { t } = usePreferences();
  const { route, navigate, link } = useNavigation();
  const [profile] = useState<AuthProfile | null>(readAuthProfile);
  const { sessions, storageError, createSession, updateSession, removeSession } = useLocalSessions(
    profile?.id,
  );
  const sidebar = useSidebarLayout();
  const isDesktop = useIsDesktop();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const current =
    sessions.find((session) => session.id === route.session) ||
    (route.path === '/' ? sessions[0] || null : null);
  const isWorkspace = route.path === '/' || route.path === '/tours';

  useEffect(() => setDrawerOpen(false), [route.path, route.session, route.hash]);

  useEffect(() => {
    const label =
      route.path === '/' || route.path === '/tours'
        ? t('Tìm tour', 'Find tours')
        : route.path === '/support'
          ? t('Hỗ trợ', 'Help')
          : route.path === '/auth' || route.path === '/account' || route.path === '/contact'
            ? t('Tài khoản & liên hệ', 'Account & contact')
            : t('Không tìm thấy', 'Not found');
    document.title = `${label} · TourLens`;
  }, [route.path, t]);

  useLayoutEffect(() => {
    if (route.hash) {
      document
        .getElementById(route.hash.slice(1))
        ?.scrollIntoView({ block: 'start', behavior: 'instant' });
      return;
    }
    window.scrollTo({ left: 0, top: 0, behavior: 'instant' });
  }, [route.path, route.session, route.hash]);

  function startSession(initialText?: string) {
    const next = createSession();
    if (initialText) updateSession(next.id, { draft: { ...next.draft, text: initialText } });
    navigate(`/?session=${next.id}`);
  }

  function continueTours() {
    if (sessions.length) navigate(`/?session=${sessions[0].id}`);
    else startSession();
  }

  function removeSavedSession(session: LocalSession) {
    removeSession(session);
    if (current?.id !== session.id) return;
    const remaining = sessions.filter((item) => item.id !== session.id);
    navigate(remaining.length ? `/?session=${remaining[0].id}` : '/');
  }

  /** One control point: collapse the sidebar on desktop, open the drawer on small screens. */
  function toggleSidebar() {
    if (isDesktop) sidebar.toggle();
    else setDrawerOpen((open) => !open);
  }

  const sessionBar = (
    <SessionBar
      title={displaySessionTitle(current?.title, t('Tìm tour mới', 'New search'))}
      sidebarOpen={isDesktop ? !sidebar.collapsed : drawerOpen}
      onToggleSidebar={toggleSidebar}
      onStart={() => startSession()}
    />
  );

  const page =
    route.path === '/' ? (
      <ChatPage session={current} onStart={startSession} onChangeSession={updateSession} />
    ) : route.path === '/support' ? (
      <SupportPage onStart={continueTours} />
    ) : route.path === '/tours' ? (
      <WorkspacePage session={current} onStart={startSession} onChangeSession={updateSession} />
    ) : route.path === '/auth' || route.path === '/account' || route.path === '/contact' ? (
      <UnavailablePage
        route={route.path.slice(1) as 'auth' | 'account' | 'contact'}
        onContinue={continueTours}
        onLink={link}
      />
    ) : !knownRoutes.has(route.path) ? (
      <UnavailablePage route="not-found" onContinue={continueTours} onLink={link} />
    ) : null;

  return (
    <div className={styles.root} data-workspace={isWorkspace || undefined}>
      <a className="skip-link" href="#main-content">
        {t('Đến nội dung chính', 'Skip to main content')}
      </a>
      <AppHeader onLink={link} />
      <div className={`app-shell ${isWorkspace ? 'workspace-open' : 'public-open'}`}>
        <SessionHistoryPanel
          sessions={sessions}
          currentId={current?.id}
          routePath={route.path}
          desktopVisible={isDesktop}
          profile={profile}
          mobileOpen={drawerOpen}
          onMobileClose={() => setDrawerOpen(false)}
          onStart={() => startSession()}
          sidebarCollapsed={sidebar.collapsed}
          sidebarWidth={sidebar.width}
          onSidebarWidthChange={sidebar.setWidth}
          onSidebarToggle={sidebar.toggle}
          onLink={link}
          onUpdate={updateSession}
          onRemove={removeSavedSession}
          controls={<PreferencesControl />}
          railControls={<PreferencesControl layout="column" localeMode="cycle" />}
        />
        <main id="main-content" className="canvas" tabIndex={-1}>
          {storageError && (
            <p className="notice notice-warning" role="status">
              {t(
                'Trình duyệt chưa lưu được lịch sử. Giữ tab này mở để tiếp tục phiên.',
                'History could not be saved. Keep this tab open to continue.',
              )}
            </p>
          )}
          {isWorkspace ? (
            <>
              {sessionBar}
              <div className="canvas-content">{page}</div>
            </>
          ) : (
            page
          )}
        </main>
      </div>
      {!isWorkspace && <AppFooter onLink={link} />}
    </div>
  );
}
