import { useEffect, useRef, useState } from 'react';
import type { SearchDraft } from '../../../entities/search-draft';
import type { LocalSession } from '../../../features/session-history';
import {
  CurrentBackendClient,
  type CurrentCatalog,
  type CurrentComparison,
  type CurrentRequirement,
} from '../../../shared/api';
import { usePreferences } from '../../../shared/preferences';
import { accessFor } from '../lib/access';
import { currentForm } from '../lib/form';
export function useCurrentWorkspace(
  session: LocalSession,
  onChangeSession: (changes: Partial<LocalSession>) => void,
) {
  const { t } = usePreferences();
  const [client, setClient] = useState<CurrentBackendClient | null>(null);
  const [catalog, setCatalog] = useState<CurrentCatalog | null>(null);
  const [requirement, setRequirement] = useState<CurrentRequirement | null>(null);
  const [comparison, setComparison] = useState<CurrentComparison | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [stale, setStale] = useState(false);
  const [reload, setReload] = useState(0);
  const sessionRef = useRef(session);
  sessionRef.current = session;

  useEffect(() => {
    const target = sessionRef.current;
    let active = true;
    setClient(null);
    setCatalog(null);
    setRequirement(null);
    setComparison(null);
    setBusy(true);
    setError('');
    setStale(false);
    void (async () => {
      try {
        const access = await accessFor(target);
        const api = new CurrentBackendClient(access.token);
        const [loadedCatalog, health] = await Promise.all([api.catalog(), api.health()]);
        if (health.status !== 'ok') throw new Error('Backend is not ready. Try again shortly.');
        if (!active) return;
        setClient(api);
        setCatalog(loadedCatalog);
        if (target.requirementId) {
          const loaded = await api.requirement(target.requirementId);
          if (!active) return;
          setRequirement(loaded.requirement);
          if (target.comparisonId) {
            const previous = await api.comparison(target.comparisonId);
            if (!active) return;
            setComparison(previous.comparison);
          }
        }
      } catch (cause) {
        if (active)
          setError(cause instanceof Error ? cause.message : 'Could not connect to backend.');
      } finally {
        if (active) setBusy(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [session.id, reload]);

  const writeDraft = (changes: Partial<SearchDraft>) => {
    onChangeSession({
      draft: { ...session.draft, ...changes },
      ...(requirement
        ? {
            requirementId: null,
            comparisonId: null,
          }
        : {}),
    });
    if (requirement) {
      setRequirement(null);
      setComparison(null);
      setStale(true);
    }
  };

  const interpret = async () => {
    if (!client || !catalog) return;
    setBusy(true);
    setError('');
    setStale(false);
    try {
      const form = currentForm(session.draft, catalog);
      const result = await client.createRequirement(session.draft.text.trim(), form);
      setRequirement(result.requirement);
      setComparison(null);
      const title =
        session.draft.destinations[0] ||
        session.draft.text.trim().slice(0, 48) ||
        t('Nhu cầu mới', 'New trip');
      onChangeSession({ requirementId: result.requirement.id, comparisonId: null, title });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not interpret this trip.');
    } finally {
      setBusy(false);
    }
  };

  const search = async () => {
    if (!client || !requirement) return;
    setBusy(true);
    setError('');
    try {
      const result = await client.createComparison(requirement.id);
      setComparison(result.comparison);
      onChangeSession({ comparisonId: result.comparison.id });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not compare tours.');
    } finally {
      setBusy(false);
    }
  };

  return {
    catalog,
    requirement,
    comparison,
    busy,
    error,
    stale,
    retry: () => setReload((value) => value + 1),
    writeDraft,
    interpret,
    search,
  };
}
