import { useCallback, useEffect, useState } from 'react';
import { removeAccess } from './access';
import { loadSessions, newSession, saveSessions } from './history';
import type { LocalSession } from './types';

export function useLocalSessions(ownerId?: string) {
  const [sessions, setSessions] = useState(() => loadSessions(ownerId));
  const [storageError, setStorageError] = useState(false);

  useEffect(() => {
    setStorageError(!saveSessions(sessions, ownerId));
  }, [sessions, ownerId]);

  const updateSession = useCallback(
    (
      id: string,
      update: Partial<LocalSession> | ((session: LocalSession) => Partial<LocalSession>),
    ) => {
      setSessions((all) =>
        all.map((session) =>
          session.id === id
            ? {
                ...session,
                ...(typeof update === 'function' ? update(session) : update),
                updatedAt: new Date().toISOString(),
              }
            : session,
        ),
      );
    },
    [],
  );

  const createSession = useCallback(() => {
    const session = newSession();
    setSessions((all) => [session, ...all]);
    return session;
  }, []);

  const removeSession = useCallback((session: LocalSession) => {
    setSessions((all) => all.filter((item) => item.id !== session.id));
    removeAccess(session.id);
  }, []);

  return { sessions, storageError, createSession, updateSession, removeSession };
}
