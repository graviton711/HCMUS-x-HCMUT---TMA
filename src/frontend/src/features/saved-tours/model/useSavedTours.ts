import { useCallback, useEffect, useRef, useState } from 'react';
import type { CurrentComparison } from '../../../shared/api';
import { savedTourFromComparison, savedTourId, type SavedTour } from './types';
import { loadSavedTours, saveSavedTours, savedToursStorageKey } from './storage';

export function useSavedTours(ownerId?: string) {
  const storageKey = savedToursStorageKey(ownerId);
  const [savedTours, setSavedTours] = useState(() => loadSavedTours(ownerId));
  const [storageError, setStorageError] = useState(false);
  const currentRef = useRef(savedTours);
  currentRef.current = savedTours;

  useEffect(() => {
    const next = loadSavedTours(ownerId);
    currentRef.current = next;
    setSavedTours(next);
    setStorageError(false);
  }, [ownerId]);

  useEffect(() => {
    const sync = (event: StorageEvent) => {
      if (event.key !== storageKey && event.key !== null) return;
      const next = loadSavedTours(ownerId);
      currentRef.current = next;
      setSavedTours(next);
    };
    window.addEventListener('storage', sync);
    return () => window.removeEventListener('storage', sync);
  }, [ownerId, storageKey]);

  const commit = useCallback(
    (next: SavedTour[]) => {
      currentRef.current = next;
      setSavedTours(next);
      setStorageError(!saveSavedTours(next, ownerId));
    },
    [ownerId],
  );

  const toggleFromComparison = useCallback(
    (comparison: CurrentComparison, tourId: string, offerId: string) => {
      const snapshot = savedTourFromComparison(comparison, tourId, offerId);
      if (!snapshot) return;
      const current = currentRef.current;
      commit(
        current.some((item) => item.id === snapshot.id)
          ? current.filter((item) => item.id !== snapshot.id)
          : [snapshot, ...current],
      );
    },
    [commit],
  );

  const remove = useCallback(
    (id: string) => commit(currentRef.current.filter((item) => item.id !== id)),
    [commit],
  );

  const isSaved = useCallback(
    (tourId: string, offerId: string) =>
      currentRef.current.some((item) => item.id === savedTourId(tourId, offerId)),
    [],
  );

  return { savedTours, storageError, toggleFromComparison, remove, isSaved };
}
