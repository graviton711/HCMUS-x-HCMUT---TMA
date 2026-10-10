import {
  getAccess,
  putAccess,
  type LocalSession,
  type SessionAccess,
} from '../../../features/session-history';
import { CurrentBackendClient } from '../../../shared/api';

const accessFlights = new Map<string, Promise<SessionAccess>>();

export async function accessFor(session: LocalSession): Promise<SessionAccess> {
  const saved = getAccess(session.id);
  if (saved) return saved;
  if (session.requirementId)
    throw new Error('Phiên backend đã hết hạn. Bản nháp vẫn còn; hãy tạo phiên mới để tìm tiếp.');
  const pending = accessFlights.get(session.id);
  if (pending) return pending;
  const request = new CurrentBackendClient()
    .createSession()
    .then((created) => {
      const access = {
        token: created.token,
        expiresAt: created.expires_at,
        backendId: created.session_id || created.id,
      };
      putAccess(session.id, access);
      return access;
    })
    .finally(() => accessFlights.delete(session.id));
  accessFlights.set(session.id, request);
  return request;
}
