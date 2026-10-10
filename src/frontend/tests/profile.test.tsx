// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, cleanup, waitFor } from '@testing-library/react';
import { PreferencesProvider } from '../app/preferences';
import { ProfileHub } from '../app/profile/ProfileHub';
import { preferenceDraft, templateDraft, templateFromDraft } from '../app/profile/apply';
import { defaultPreferences, validateHub, type HubState } from '../app/profile/contracts';
import { buildCreateRequirement, buildEdits, formFromRequirement } from '../api/form';
import type { Requirement } from '../api/types';
import { useHub } from '../app/profile/useHub';
import { saveAuth, clearAuth } from '../app/auth';

afterEach(() => {
  cleanup();
  clearAuth();
  vi.unstubAllGlobals();
  localStorage.clear();
  sessionStorage.clear();
});
const hubState = {
  schema_version: '1' as const,
  preferences: null,
  preferences_version: 0,
  saved_tours: [],
  templates: [],
};
function complete() {
  return {
    ...preferenceDraft(defaultPreferences),
    destinations: ['place:jp'],
    departureOrigin: 'place:vn:ho_chi_minh',
    departureMonths: ['2026-11'],
    adults: 1,
    budget: '40000000',
  };
}
describe('personal draft reuse', () => {
  it('creates only explicit soft preferences, leaving current trip hard inputs empty', () => {
    const d = preferenceDraft({
      ...defaultPreferences,
      hotel_stars: 4,
      duration_days: 7,
      shopping: 'few',
      prefer_lower_listed_price: true,
      levels: { cost: 5, comfort: 4, pace: 2, culture: 3 },
    });
    expect(d).toMatchObject({
      adults: 0,
      budget: '',
      destinations: [],
      departureMonths: [],
      departureDate: '',
      childAges: [],
      hotelStars: '4',
      durationDays: '7',
      shopping: 'few',
    });
    expect(d.strengths.hotel_stars_min).toBe('soft');
    d.preferenceLevels.cost = 1;
    expect(defaultPreferences.levels.cost).toBe(3);
  });
  it('clears old dates/prices/child ages/URLs/text when a template is reused', () => {
    const d = {
      ...complete(),
      departureDate: '2026-11-05',
      returnDate: '2026-11-12',
      text: 'old private text',
      childAges: [8],
      referenceUrls: ['https://example.test/tour'],
      notes: 'private note',
    };
    const template = templateFromDraft(d, 'Family');
    const next = templateDraft(template);
    expect(next).toMatchObject({
      adults: 1,
      childAges: [null],
      budget: '',
      departureMonths: [],
      departureDate: '',
      returnDate: '',
      text: '',
      notes: '',
      referenceUrls: [],
    });
    expect(JSON.stringify(template)).not.toContain('private');
    expect(d.childAges).toEqual([8]);
  });
  it('keeps price preference separate from hard cap and preserves it during budget edits', () => {
    const d = { ...complete(), preferLowerListedPrice: true };
    const body = buildCreateRequirement(d);
    if (body.input.kind !== 'structured') throw new Error();
    const cs = body.input.form.conditions!;
    expect(
      cs.filter((c) => c.field === 'estimated_cost').map((c) => [c.operator, c.strength]),
    ).toEqual([
      ['lte', 'hard'],
      ['prefer_low', 'soft'],
    ]);
    const r = {
      input_kind: 'structured',
      conditions: cs,
      party: { adults: 1, children: [] },
      reference_urls: [],
      notes: '',
      preference_levels: null,
      hard_tree: {
        kind: 'all',
        children: cs
          .filter((c) => c.strength === 'hard')
          .map((c) => ({ kind: 'predicate', condition_id: c.id })),
      },
      preference_tree: {
        kind: 'all',
        children: cs
          .filter((c) => c.strength === 'soft')
          .map((c) => ({ kind: 'predicate', condition_id: c.id })),
      },
    } as unknown as Requirement;
    const next = formFromRequirement(r);
    expect(next.budget).toBe('40000000');
    expect(next.strengths.estimated_cost).toBe('hard');
    const edits = buildEdits({ ...next, budget: '45000000' }, r);
    expect(
      edits.some(
        (e) =>
          e.op === 'upsert_condition' &&
          e.condition.id === 'condition_listed_price_preference' &&
          e.condition.value.kind === 'budget' &&
          e.condition.value.amount === 45000000,
      ),
    ).toBe(true);
  });
  it('rejects an unsafe bookmark URL before display', () => {
    expect(() =>
      validateHub({
        ...hubState,
        saved_tours: [
          {
            id: 's',
            kind: 'saved_tour',
            version: 1,
            updated_at: new Date().toISOString(),
            value: { title: 'Fake', url: 'javascript:alert(1)' },
          },
        ],
      }),
    ).toThrow();
  });
});
it('keeps unsaved preference edits on failed cloud write and applies only on explicit click', async () => {
  const onNew = vi.fn();
  const mutate = vi.fn().mockRejectedValue(new Error('offline'));
  const hub = { data: hubState, error: '', busy: false, mutate, remove: vi.fn(), reload: vi.fn() };
  render(
    <PreferencesProvider>
      <ProfileHub
        view="preferences"
        owner="user-a"
        hub={hub}
        sessions={[]}
        retention={7}
        historyBusy={false}
        onNew={onNew}
        onOpen={vi.fn()}
        onPin={vi.fn()}
        onArchive={vi.fn()}
        onSignIn={vi.fn()}
      />
    </PreferencesProvider>,
  );
  fireEvent.change(screen.getByLabelText('Khách sạn mong muốn'), { target: { value: '4' } });
  fireEvent.click(screen.getByText('Lưu sở thích'));
  await waitFor(() => expect(mutate).toHaveBeenCalled());
  expect(onNew).not.toHaveBeenCalled();
  expect((screen.getByLabelText('Khách sạn mong muốn') as HTMLSelectElement).value).toBe('4');
  fireEvent.click(screen.getByText('Dùng cho chuyến mới'));
  expect(onNew.mock.calls[0][0]).toMatchObject({ hotelStars: '4', budget: '', adults: 0 });
});
it('discards a delayed response when account changes and never persists hub documents', async () => {
  const session = (id: string) => ({
    access_token: `token-${id}`,
    refresh_token: `r-${id}`,
    expires_at: Date.now() / 1000 + 3600,
    user: { id, name: id, username: `${id}@example.test` },
  });
  saveAuth(session('a'));
  let release: (r: Response) => void = () => {};
  const fetcher = vi
    .fn()
    .mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          release = resolve;
        }),
    )
    .mockResolvedValue(
      new Response(
        JSON.stringify({ schema_version: '2.0-draft', request_id: 'r', data: hubState }),
        { status: 200 },
      ),
    );
  vi.stubGlobal('fetch', fetcher);
  function Harness({ owner }: { owner: string }) {
    const h = useHub(owner);
    return <span>{h.data?.preferences?.value.hotel_stars ?? 'empty'}</span>;
  }
  const view = render(<Harness owner="a" />);
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
  saveAuth(session('b'));
  view.rerender(<Harness owner="b" />);
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  await act(async () =>
    release(
      new Response(
        JSON.stringify({
          schema_version: '2.0-draft',
          request_id: 'r',
          data: {
            ...hubState,
            preferences_version: 1,
            preferences: {
              id: 'preferences',
              kind: 'preferences',
              version: 1,
              updated_at: new Date().toISOString(),
              value: { ...defaultPreferences, hotel_stars: 5 },
            },
          },
        }),
        { status: 200 },
      ),
    ),
  );
  expect(screen.getByText('empty')).toBeTruthy();
  expect(
    [...Array(localStorage.length)]
      .map((_, i) => localStorage.getItem(localStorage.key(i)!))
      .join(''),
  ).not.toContain('hotel_stars');
});

it('rechecks saved URLs in a new draft and drops selections removed by another device', () => {
  const onNew = vi.fn();
  const time = new Date().toISOString();
  const data: HubState = {
    ...hubState,
    saved_tours: [
      {
        id: 'saved',
        kind: 'saved_tour',
        version: 1,
        updated_at: time,
        value: {
          title: 'Japan saved tour',
          supplier: 'Provider',
          url: 'https://example.test/tour',
          comparison_id: 'old-comparison',
          column_id: 'old-column',
          offer_snapshot_id: 'old-offer',
          departure_date: '2026-11-05',
          price_label: 'Từ 33999000 VND',
          evaluated_at: time,
          saved_at: time,
          status_at_save: 'recommended',
          note: '',
          collection: 'Family',
        },
      },
    ],
  };
  const hub = { data, error: '', busy: false, mutate: vi.fn(), remove: vi.fn(), reload: vi.fn() };
  const props = {
    view: 'saved' as const,
    owner: 'user-a',
    hub,
    sessions: [],
    retention: 7,
    historyBusy: false,
    onNew,
    onOpen: vi.fn(),
    onPin: vi.fn(),
    onArchive: vi.fn(),
    onSignIn: vi.fn(),
  };
  const view = render(
    <PreferencesProvider>
      <ProfileHub {...props} />
    </PreferencesProvider>,
  );
  expect(screen.getByText(/Dữ liệu lịch sử/)).toBeTruthy();
  fireEvent.click(screen.getByText('Kiểm tra lại', { exact: true }));
  expect(onNew.mock.calls[0][0]).toMatchObject({
    mode: 'urls',
    referenceUrls: ['https://example.test/tour'],
    budget: '',
    departureDate: '',
    departureMonths: [],
  });
  onNew.mockClear();
  fireEvent.click(screen.getByLabelText('Chọn để đối chiếu'));
  fireEvent.click(screen.getByText('Đối chiếu 1/5 tour'));
  expect(onNew).toHaveBeenCalledTimes(1);
  onNew.mockClear();
  view.rerender(
    <PreferencesProvider>
      <ProfileHub {...props} hub={{ ...hub, data: { ...data, saved_tours: [] } }} />
    </PreferencesProvider>,
  );
  expect((screen.getByText('Đối chiếu 0/5 tour') as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByText('Đối chiếu 0/5 tour'));
  expect(onNew).not.toHaveBeenCalled();
});

it('applies a cloud template only after the user chooses it, with fresh trip inputs', () => {
  const onNew = vi.fn();
  const template = templateFromDraft({ ...complete(), childAges: [8] }, 'Family');
  const data: HubState = {
    ...hubState,
    templates: [
      {
        id: 'template-a',
        kind: 'template',
        version: 1,
        updated_at: new Date().toISOString(),
        value: template,
      },
    ],
  };
  const hub = { data, error: '', busy: false, mutate: vi.fn(), remove: vi.fn(), reload: vi.fn() };
  render(
    <PreferencesProvider>
      <ProfileHub
        view="templates"
        owner="user-a"
        hub={hub}
        sessions={[]}
        retention={7}
        historyBusy={false}
        onNew={onNew}
        onOpen={vi.fn()}
        onPin={vi.fn()}
        onArchive={vi.fn()}
        onSignIn={vi.fn()}
      />
    </PreferencesProvider>,
  );
  expect(onNew).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText('Dùng mẫu', { exact: true }));
  expect(onNew.mock.calls[0]).toEqual([
    expect.objectContaining({
      destinations: ['place:jp'],
      departureOrigin: 'place:vn:ho_chi_minh',
      adults: 1,
      childAges: [null],
      budget: '',
      departureMonths: [],
      referenceUrls: [],
    }),
    'Family',
  ]);
});
