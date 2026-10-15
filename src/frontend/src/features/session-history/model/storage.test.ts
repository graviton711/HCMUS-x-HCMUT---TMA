// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { getAccess, loadSessions, newSession, putAccess, saveSessions } from './index';
import { normalizeSearch } from '../lib/normalize';

const now = Date.parse('2026-10-08T08:00:00Z');
beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  vi.spyOn(Date, 'now').mockReturnValue(now);
});
afterEach(() => vi.restoreAllMocks());

describe('browser history privacy', () => {
  it('restores per-brief weight confirmations alongside legacy drafts without editor metadata', () => {
    const session = newSession();
    const draft = {
      id: 'brief-weight', kind: 'decision_draft', status: 'draft',
      requirement: { id: 'req-weight', conditions: [], raw_text: '', travelers: 1, missing: [] },
    };
    session.messages = [draft, { ...draft, id: 'brief-confirmed', confirmedWeightIds: ['culture'] }];
    saveSessions([session]);
    const messages = loadSessions()[0]?.messages;
    expect(messages).toHaveLength(2);
    expect(messages?.[0]).not.toHaveProperty('confirmedWeightIds');
    expect(messages?.[1]).toMatchObject({ id: 'brief-confirmed', confirmedWeightIds: ['culture'] });
  });

  it('strips legacy draft and session keys without losing saved criteria or sessions', () => {
    const original = newSession();
    const legacyDraft = {
      ...original.draft,
      departureDate: '2026-11-10',
      budget: '35000000',
      mode: 'urls',
      departureMonths: ['2026-11'],
      budgetMin: '1000000',
      childAges: [8],
      referenceUrls: ['https://example.test/tour'],
      notes: 'legacy note',
      preferenceLevels: { cost: 1, comfort: 5, pace: 5, culture: 1 },
    };
    const legacySession = {
      ...original,
      draft: legacyDraft,
      proposalId: 'prop_legacy',
      jobId: 'job_legacy',
      runs: [{ id: 'cmp_legacy', revision: 1, createdAt: '2026-10-01T00:00:00Z' }],
      chat: [{ id: 'm1', role: 'user', text: 'hello' }],
    };
    localStorage.setItem('di-cung:history:v1', JSON.stringify([legacySession]));
    const restored = loadSessions();
    expect(restored).toHaveLength(1);
    expect(restored[0]).toMatchObject({
      id: original.id,
      requirementId: null,
      comparisonId: null,
      draft: {
        mode: 'structured',
        departureDate: '2026-11-10',
        budget: '35000000',
      },
    });
    expect(restored[0].draft).toEqual({ ...original.draft, departureDate: '2026-11-10', budget: '35000000' });
    expect(restored[0]).not.toHaveProperty('proposalId');
    expect(restored[0]).not.toHaveProperty('runs');
    expect(restored[0]).not.toHaveProperty('chat');
  });
  it('keeps anonymous and each account history separate without fallback to another owner', () => {
    const anonymous = { ...newSession(), title: 'Chuyến đi chưa đăng nhập' };
    const first = { ...newSession(), title: 'Lịch sử tài khoản thứ nhất' };
    const second = { ...newSession(), title: 'Lịch sử tài khoản thứ hai' };
    saveSessions([anonymous]);
    saveSessions([first], 'owner-a');
    saveSessions([second], 'owner-b');

    expect(loadSessions().map((session) => session.id)).toEqual([anonymous.id]);
    expect(loadSessions('owner-a').map((session) => session.id)).toEqual([first.id]);
    expect(loadSessions('owner-b').map((session) => session.id)).toEqual([second.id]);
    expect(loadSessions('never-signed-in')).toEqual([]);

    saveSessions([], 'owner-a');
    expect(loadSessions('owner-a')).toEqual([]);
    expect(loadSessions('owner-b').map((session) => session.id)).toEqual([second.id]);
    expect(loadSessions().map((session) => session.id)).toEqual([anonymous.id]);
  });

  it('stores bearer access outside history and exported history data', () => {
    const session = { ...newSession(), title: 'Phiên có quyền truy cập dịch vụ' };
    const bearer = 'test-only-private-bearer';
    putAccess(session.id, {
      token: bearer,
      backendId: 'backend-session-test',
      expiresAt: '2026-10-08T09:00:00Z',
    });
    saveSessions([session], 'owner-a');

    const exported = JSON.stringify({
      exportedAt: new Date(now).toISOString(),
      sessions: loadSessions('owner-a'),
    });
    expect(exported).not.toContain(bearer);
    expect(exported).not.toContain('backend-session-test');
    expect(exported).not.toContain('"token"');
    for (let index = 0; index < localStorage.length; index += 1) {
      expect(localStorage.getItem(localStorage.key(index)!)).not.toContain(bearer);
    }
    expect(getAccess(session.id)?.token).toBe(bearer);
  });
});

describe('corrupt saved draft recovery', () => {
  const malformedDrafts: [string, Record<string, unknown>][] = [
    ['destination objects in place of IDs', { destinations: [{ id: 'place-test' }] }],
    ['transport values with a nested object', { transport: ['air', { id: 'bus' }] }],
    ['non-string accommodation', { accommodation: { stars: 5 } }],
  ];
  it.each(malformedDrafts)('rejects %s while preserving healthy sessions', (_name, patch) => {
    const healthy = { ...newSession(), title: 'Draft hợp lệ vẫn được giữ' };
    const corrupt = { ...newSession(), draft: { ...newSession().draft, ...patch } };
    saveSessions([healthy], 'owner-a');
    const key = localStorage.key(0)!;
    localStorage.setItem(key, JSON.stringify([corrupt, healthy]));

    const restored = loadSessions('owner-a');
    expect(restored).toHaveLength(1);
    expect(restored[0].id).toBe(healthy.id);
    expect(restored[0].draft).toEqual(healthy.draft);
  });

  it('recovers from malformed JSON without loading another owner history', () => {
    const healthy = newSession();
    saveSessions([healthy], 'owner-b');
    saveSessions([], 'owner-a');
    const ownerAKey = Array.from({ length: localStorage.length }, (_, index) =>
      localStorage.key(index)!,
    ).find((key) => localStorage.getItem(key) === '[]')!;
    localStorage.setItem(ownerAKey, '{unfinished');

    expect(loadSessions('owner-a')).toEqual([]);
    expect(loadSessions('owner-b').map((session) => session.id)).toEqual([healthy.id]);
  });
});

describe('access lifetime and history search', () => {
  it('rejects expired, exactly expiring, or invalid expiry dates even when IDs remain saved', () => {
    const session = newSession();
    saveSessions([session], 'owner-a');
    for (const expiresAt of ['2026-10-08T07:59:59Z', '2026-10-08T08:00:00Z', 'not-a-date']) {
      putAccess(session.id, { token: 'test-only-access', backendId: 'backend-test', expiresAt });
      expect(getAccess(session.id)).toBeNull();
      expect(loadSessions('owner-a').map((saved) => saved.id)).toEqual([session.id]);
    }
  });

  it('matches a multi-word Đ/đ query independent of accents, case, and word order', () => {
    const titles = ['Đà Nẵng cùng gia đình', 'Chuyến ĐI Đà Lạt', 'Nhật Bản tháng mười'];
    const terms = normalizeSearch('  LAT đi  ').split(/\s+/).filter(Boolean);
    const matched = titles.filter((title) =>
      terms.every((term) => normalizeSearch(title).includes(term)),
    );
    expect(matched).toEqual(['Chuyến ĐI Đà Lạt']);
    expect(normalizeSearch('Đà Nẵng')).toBe('da nang');
    expect(normalizeSearch('đi cùng')).toBe('di cung');
  });
});
