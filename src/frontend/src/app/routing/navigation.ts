import { useCallback, useEffect, useState, type MouseEvent } from 'react';

export interface AppRoute {
  path: string;
  session: string | null;
  hash: string;
}

function locationState(): AppRoute {
  return {
    path: window.location.pathname.replace(/\/$/u, '') || '/',
    session: new URLSearchParams(window.location.search).get('session'),
    hash: window.location.hash,
  };
}

export function isLinkClick(event: MouseEvent<HTMLAnchorElement>) {
  return event.button === 0 && !event.ctrlKey && !event.metaKey && !event.altKey && !event.shiftKey;
}

export function useNavigation() {
  const [route, setRoute] = useState(locationState);

  useEffect(() => {
    const back = () => setRoute(locationState());
    window.addEventListener('popstate', back);
    return () => window.removeEventListener('popstate', back);
  }, []);

  const navigate = useCallback((url: string) => {
    window.history.pushState(null, '', url);
    setRoute(locationState());
  }, []);

  const replace = useCallback((url: string) => {
    window.history.replaceState(null, '', url);
    setRoute(locationState());
  }, []);

  const link = useCallback(
    (url: string) => (event: MouseEvent<HTMLAnchorElement>) => {
      if (isLinkClick(event)) {
        event.preventDefault();
        navigate(url);
      }
    },
    [navigate],
  );

  return { route, navigate, replace, link };
}
