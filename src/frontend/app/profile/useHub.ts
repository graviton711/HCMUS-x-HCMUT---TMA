import { useCallback, useEffect, useRef, useState } from 'react';
import { accountClient } from '../history';
import type { HubState, HubKind } from './contracts';

export function useHub(owner: string | undefined) {
  const [state, setState] = useState<{ owner: string; data: HubState } | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const ownerRef = useRef(owner);
  ownerRef.current = owner;
  const writing = useRef(false);
  const clear = useCallback(() => {
    setState(null);
    setError('');
    setBusy(false);
  }, []);
  const reload = useCallback(async (signal?: AbortSignal) => {
    const current = ownerRef.current;
    if (!current) return;
    setBusy(true);
    setError('');
    try {
      const data = await accountClient(current).profileHub({ signal });
      if (!signal?.aborted && ownerRef.current === current) setState({ owner: current, data });
    } catch (e) {
      if (!signal?.aborted && ownerRef.current === current)
        setError(e instanceof Error ? e.message : 'Chưa tải được hồ sơ.');
    } finally {
      if (!signal?.aborted && ownerRef.current === current) setBusy(false);
    }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    clear();
    if (owner) void reload(controller.signal);
    return () => controller.abort();
  }, [owner, reload, clear]);
  const data = state && state.owner === owner ? state.data : null;
  const mutate = useCallback(
    async (path: string, body: unknown) => {
      const current = ownerRef.current;
      if (!current) throw new Error('Đăng nhập để lưu dữ liệu cá nhân.');
      if (writing.current) throw new Error('Chờ mục đang lưu hoàn tất.');
      writing.current = true;
      setBusy(true);
      setError('');
      try {
        const result = await accountClient(current).mutateHub(path, body);
        if (ownerRef.current !== current) throw new Error('Tài khoản đã thay đổi.');
        setState((old) => {
          if (!old || old.owner !== current) return old;
          const next = structuredClone(old.data);
          if (result.deleted) {
            next.saved_tours = next.saved_tours.filter((i) => i.id !== result.id);
            next.templates = next.templates.filter((i) => i.id !== result.id);
            if (result.id === 'preferences') {
              next.preferences = null;
              next.preferences_version = result.version;
            }
          } else {
            const item = result.item;
            if (item.kind === 'preferences') {
              next.preferences = item as HubState['preferences'];
              next.preferences_version = item.version;
            } else if (item.kind === 'saved_tour')
              next.saved_tours = [
                item as HubState['saved_tours'][number],
                ...next.saved_tours.filter((i) => i.id !== item.id),
              ];
            else
              next.templates = [
                item as HubState['templates'][number],
                ...next.templates.filter((i) => i.id !== item.id),
              ];
          }
          return { owner: current, data: next };
        });
        // A completed write remains successful even if the subsequent refresh is unavailable.
        await reload();
      } catch (e) {
        if (ownerRef.current === current)
          setError(e instanceof Error ? e.message : 'Chưa lưu được hồ sơ.');
        throw e;
      } finally {
        writing.current = false;
        if (ownerRef.current === current) setBusy(false);
      }
    },
    [reload],
  );
  const remove = (kind: HubKind, id: string, version: number) =>
    mutate('items/delete', { kind, item_id: id, expected_version: version });
  return { data, error: owner ? error : '', busy: owner ? busy : false, reload, mutate, remove };
}
export type Hub = ReturnType<typeof useHub>;
