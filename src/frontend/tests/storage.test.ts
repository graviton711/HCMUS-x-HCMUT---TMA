// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getAccess,
  loadSessions,
  newSession,
  normalizeSearch,
  putAccess,
  saveSessions,
} from '../app/storage';

const now = Date.parse('2026-10-08T08:00:00Z');
beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  vi.spyOn(Date, 'now').mockReturnValue(now);
});
afterEach(() => vi.restoreAllMocks());

describe('browser history privacy', () => {
  it('migrates old drafts without losing saved dates, price caps or sessions', () => {
    const original = newSession();
    const draft = { ...original.draft, departureDate: '2026-11-10', budget: '35000000' };
    const { departureMonths: _months, budgetMin: _min, ...legacy } = draft;
    void _months;
    void _min;
    localStorage.setItem('di-cung:history:v1', JSON.stringify([{ ...original, draft: legacy }]));
    expect(loadSessions()[0]).toMatchObject({
      id: original.id,
      draft: {
        departureMonths: [],
        departureDate: '2026-11-10',
        budget: '35000000',
        budgetMin: '',
      },
    });
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
    [
      'reference URL objects in place of strings',
      { referenceUrls: [{ url: 'https://example.test/tour' }] },
    ],
    ['child ages restored as strings', { childAges: ['8'] }],
    ['child age outside the supported range', { childAges: [18] }],
    [
      'fractional preference level',
      { preferenceLevels: { cost: 3.5, comfort: 3, pace: 3, culture: 3 } },
    ],
    ['missing nested preference dimension', { preferenceLevels: { cost: 3, comfort: 3, pace: 3 } }],
    ['invalid condition strength', { strengths: { duration_days: 'unresolved' } }],
    ['invalid price basis', { budgetBasis: 'per_room' }],
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
