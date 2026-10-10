import { useEffect, useState } from 'react';
import {
  readAuthProfile,
  SessionHistoryPanel,
  useLocalSessions,
  type AuthProfile,
  type LocalSession,
} from '../features/session-history';
import { LandingPage, SupportPage, UnavailablePage } from '../pages/public';
import { WorkspacePage } from '../pages/workspace';
import { usePreferences } from '../shared/preferences';
import { useNavigation } from './routing';
import { AppFooter, AppHeader } from './shell';
import styles from './shell/AppShell.module.css';

const knownRoutes = new Set(['/', '/tours', '/auth', '/account', '/contact', '/support']);

export function App() {
  const { t } = usePreferences();
  const { route, navigate, link } = useNavigation();
  const [profile] = useState<AuthProfile | null>(readAuthProfile);
  const { sessions, storageError, createSession, updateSession, removeSession } = useLocalSessions(
    profile?.id,
  );
  const [historyOpen, setHistoryOpen] = useState(false);
  const current =
    sessions.find((session) => session.id === route.session) ||
    (route.path === '/tours' ? sessions[0] || null : null);

  useEffect(() => setHistoryOpen(false), [route.path, route.session, route.hash]);

  useEffect(() => {
    document.title = `${route.path === '/tours' ? t('Tìm tour', 'Find tours') : route.path === '/auth' ? t('Tài khoản', 'Account') : 'Đi cùng'} · Đi cùng`;
  }, [route.path, t]);

  useEffect(() => {
    if (route.hash)
      document
        .getElementById(route.hash.slice(1))
        ?.scrollIntoView({ block: 'start', behavior: 'instant' });
  }, [route.path, route.hash]);

  function startSession() {
    const next = createSession();
    navigate(`/tours?session=${next.id}`);
  }

  function continueTours() {
    if (sessions.length) navigate(`/tours?session=${sessions[0].id}`);
    else startSession();
  }

  function removeSavedSession(session: LocalSession) {
    removeSession(session);
    if (current?.id === session.id) navigate('/tours');
  }

  const page =
    route.path === '/' ? (
      <LandingPage onStart={continueTours} />
    ) : route.path === '/support' ? (
      <SupportPage onStart={continueTours} />
    ) : route.path === '/tours' ? (
      <WorkspacePage
        session={current}
        profile={profile}
        onStart={startSession}
        onChangeSession={updateSession}
        onOpenHistory={() => setHistoryOpen(true)}
        historyOpen={historyOpen}
      />
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
    <div className={styles.root}>
      <a className="skip-link" href="#main-content">
        {t('Đến nội dung chính', 'Skip to main content')}
      </a>
      <AppHeader
        routePath={route.path}
        profile={profile}
        onContinueTours={continueTours}
        onLink={link}
      />
      <div className={`app-shell ${route.path === '/tours' ? 'workspace-open' : ''}`}>
        <SessionHistoryPanel
          sessions={sessions}
          currentId={current?.id}
          routePath={route.path}
          profile={profile}
          mobileOpen={historyOpen}
          onMobileClose={() => setHistoryOpen(false)}
          onStart={startSession}
          onLink={link}
          onUpdate={updateSession}
          onRemove={removeSavedSession}
        />
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
          {page}
        </main>
      </div>
      <AppFooter onLink={link} />
    </div>
  );
}
