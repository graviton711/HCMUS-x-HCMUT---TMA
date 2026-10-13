// @vitest-environment jsdom
import { useState } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { CurrentWorkspace } from './CurrentWorkspace';
import { newSession, type LocalSession } from '../../../features/session-history';
import { PreferencesProvider } from '../../../shared/preferences';

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function makeBackend() {
  return vi.fn<typeof fetch>(async (input, init) => {
    const path = new URL(String(input), 'http://local').pathname;
    const method = init?.method ?? 'GET';
    if (path === '/sessions' && method === 'POST')
      return response(
        {
          id: 'ses_guest',
          session_id: 'ses_guest',
          token: 'guest-secret',
          token_type: 'Bearer',
          expires_at: '2030-01-01T00:00:00+00:00',
        },
        201,
      );
    if (path === '/catalog') return response({ destinations: ['Đà Lạt'] });
    if (path === '/health') return response({ status: 'ok', version: 'test' });
    if (path === '/requirements' && method === 'POST')
      return response({
        requirement: {
          id: 'req_guest',
          conditions: [
            {
              id: 'h1',
              field: 'destination',
              operator: 'contains',
              value: 'Đà Lạt',
              strength: 'hard',
              quote: '',
            },
            {
              id: 'h2',
              field: 'budget_max',
              operator: 'lte',
              value: 8000000,
              strength: 'hard',
              quote: '',
            },
          ],
          missing: [],
          raw_text: 'Đà Lạt',
          travelers: 1,
        },
      });
    if (path === '/comparisons' && method === 'POST')
      return response({
        comparison: {
          id: 'cmp_guest',
          requirement: {
            id: 'req_guest',
            conditions: [],
            missing: [],
            raw_text: 'Đà Lạt',
            travelers: 1,
          },
          ranked: [{ tour_id: 'tour_guest', offer_id: 'offer_guest', score: 0 }],
          near_miss: [{ tour_id: 'tour_near', offer_id: 'offer_near', score: 0.5 }],
          tour_snapshots: [
            {
              id: 'tour_guest',
              supplier: 'Local Tours',
              name: 'Đà Lạt cuối tuần',
              url: 'https://example.test/tours/da-lat',
              destinations: ['Đà Lạt'],
              raw_destinations: ['Đà Lạt'],
              route: [],
              departure_city: 'TP.HCM',
              duration_days: 3,
              transport: 'bus',
              accommodation: 'Hotel',
              itinerary: '',
              inclusions: 'Xe đưa đón',
              exclusions: '',
              cancellation_policy: '',
              surcharges: '',
              child_policy: '',
              evidence: {
                url: 'https://example.test/tours/da-lat',
                method: 'database_record',
                observed_at: '',
                record_ref: '',
              },
              observed_at: '',
              verification: 'provider_claimed',
              offers: [
                {
                  id: 'offer_guest',
                  tour_id: 'tour_guest',
                  departure_date: '2026-12-01',
                  price: 5000000,
                  currency: 'VND',
                  price_basis: 'exact',
                  departure_freshness: 'fresh',
                  availability: 'unknown',
                  conditions: '',
                  evidence: {
                    url: 'https://example.test/tours/da-lat',
                    method: 'database_record',
                    observed_at: '',
                    record_ref: '',
                  },
                },
              ],
            },
            {
              id: 'tour_near',
              supplier: 'Nearby Tours',
              name: 'Đà Lạt tiết kiệm',
              url: 'https://example.test/tours/da-lat-budget',
              destinations: ['Đà Lạt'],
              raw_destinations: ['Đà Lạt'],
              route: [],
              departure_city: 'TP.HCM',
              duration_days: 3,
              transport: 'bus',
              accommodation: 'Hotel',
              itinerary: '',
              inclusions: '',
              exclusions: '',
              cancellation_policy: '',
              surcharges: '',
              child_policy: '',
              evidence: {
                url: 'https://example.test/tours/da-lat-budget',
                method: 'database_record',
                observed_at: '',
                record_ref: '',
              },
              observed_at: '',
              verification: 'provider_claimed',
              offers: [
                {
                  id: 'offer_near',
                  tour_id: 'tour_near',
                  departure_date: '2026-12-01',
                  price: 9000000,
                  currency: 'VND',
                  price_basis: 'exact',
                  departure_freshness: 'fresh',
                  availability: 'unknown',
                  conditions: '',
                  evidence: {
                    url: 'https://example.test/tours/da-lat-budget',
                    method: 'database_record',
                    observed_at: '',
                    record_ref: '',
                  },
                },
              ],
            },
          ],
          evaluations: [
            {
              offer_id: 'offer_guest',
              condition_id: 'h1',
              state: 'pass',
              quote: 'Đà Lạt 3 ngày 2 đêm',
              reason_code: '',
            },
            {
              offer_id: 'offer_near',
              condition_id: 'h1',
              state: 'pass',
              quote: '',
              reason_code: '',
            },
            {
              offer_id: 'offer_near',
              condition_id: 'h2',
              state: 'fail',
              quote: '',
              reason_code: 'PRICE_OVER_BUDGET',
            },
          ],
          analysis: {
            hidden_costs: ['Phụ thu phòng đơn 500.000 VND'],
            conditions: ['Hủy miễn phí trước 7 ngày'],
            risks: ['Giá có thể đổi khi lễ'],
            benefits: ['Đã gồm xe đưa đón'],
          },
          candidates_considered: 1,
        },
      });
    return response({ error: { code: 'NOT_FOUND', message: 'not found' } }, 404);
  });
}

function Harness({ initial }: { initial: LocalSession }) {
  const [session, setSession] = useState(initial);
  return (
    <PreferencesProvider>
      <CurrentWorkspace
        session={session}
        onChangeSession={(changes) => setSession((current) => ({ ...current, ...changes }))}
      />
    </PreferencesProvider>
  );
}

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe('CurrentWorkspace guest flow', () => {
  it('offers a new session for an expired guest and never retries the old session', async () => {
    const initial = newSession();
    initial.requirementId = 'req-expired';
    initial.draft.text = 'Đà Lạt 3 ngày';
    const onStart = vi.fn();
    render(
      <PreferencesProvider>
        <CurrentWorkspace session={initial} onStart={onStart} onChangeSession={() => {}} />
      </PreferencesProvider>,
    );

    expect((await screen.findByRole('alert')).textContent).toContain('Phiên khách đã hết hạn');
    expect(screen.queryByRole('button', { name: 'Thử lại' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Tạo phiên mới và gửi lại bản nháp' })).toBeTruthy();
    expect(screen.getByLabelText('Mô tả chuyến đi').matches(':disabled')).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Tạo phiên mới và gửi lại bản nháp' }));
    expect(onStart).toHaveBeenCalledWith('Đà Lạt 3 ngày');
  });

  it('interprets, searches and renders a persisted current-backend snapshot', async () => {
    const fetcher = makeBackend();
    vi.stubGlobal('fetch', fetcher);
    const initial = newSession();
    render(<Harness initial={initial} />);

    const description = await screen.findByLabelText('Mô tả chuyến đi');
    fireEvent.change(description, { target: { value: 'Đà Lạt' } });
    fireEvent.change(screen.getByLabelText('Điểm đến trong catalog'), {
      target: { value: 'Đà Lạt' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Diễn giải nhu cầu' }));

    expect(await screen.findByText('điểm đến')).toBeTruthy();
    expect(fetcher).toHaveBeenCalledWith(
      '/requirements',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer guest-secret' }),
      }),
    );
    fireEvent.click(screen.getByRole('button', { name: 'Tìm và so sánh tour' }));
    expect(await screen.findByText('Đà Lạt cuối tuần')).toBeTruthy();
    expect(screen.getByText(/5\.000\.000 VND/)).toBeTruthy();
    expect(screen.getByText('Đã gồm xe đưa đón')).toBeTruthy();
    expect(screen.getByText('Hủy miễn phí trước 7 ngày')).toBeTruthy();
    expect(screen.getByText('Gần đạt — thiếu ít điều kiện')).toBeTruthy();
    expect(screen.getByText('Đà Lạt tiết kiệm')).toBeTruthy();
    expect(screen.getByText('PRICE_OVER_BUDGET')).toBeTruthy();
    await waitFor(() => expect(fetcher).toHaveBeenCalledWith('/comparisons', expect.anything()));
  });

  it('ignores legacy draft keys instead of blocking the search', async () => {
    const fetcher = makeBackend();
    vi.stubGlobal('fetch', fetcher);
    const initial = newSession();
    initial.draft.text = 'Đà Lạt';
    initial.draft = { ...initial.draft, budgetMin: '3000000' } as typeof initial.draft;
    render(<Harness initial={initial} />);

    fireEvent.click(await screen.findByRole('button', { name: 'Diễn giải nhu cầu' }));
    expect(await screen.findByText('điểm đến')).toBeTruthy();
    expect(fetcher).toHaveBeenCalledWith('/requirements', expect.anything());
  });

  it('blocks multiple transport choices instead of silently dropping them', async () => {
    const fetcher = makeBackend();
    vi.stubGlobal('fetch', fetcher);
    const initial = newSession();
    initial.draft.text = 'Đà Lạt';
    initial.draft.transport = ['bus', 'flight'];
    render(<Harness initial={initial} />);

    fireEvent.click(await screen.findByRole('button', { name: 'Diễn giải nhu cầu' }));
    expect((await screen.findByRole('alert')).textContent).toContain('single transport');
    expect(fetcher).not.toHaveBeenCalledWith('/requirements', expect.anything());
  });
});
